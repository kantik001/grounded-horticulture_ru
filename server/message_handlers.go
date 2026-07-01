package main

import (
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

type jsonMessageRequest struct {
	SessionID string `json:"session_id"`
	Text      string `json:"text"`
	CropID    string `json:"crop_id"`
}

// handleMessage — единая точка: текст (RAG+LLM) и/или фото (классификация+LLM).
func handleMessage(c *gin.Context) {
	ct := c.GetHeader("Content-Type")
	var sessionID string
	var text string
	var cropIDRaw string
	var imageData []byte
	var err error

	if strings.HasPrefix(ct, "multipart/form-data") {
		if err := c.Request.ParseMultipartForm(int64(maxUploadImageBytes + 512*1024)); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Некорректный multipart"})
			return
		}
		sessionID = strings.TrimSpace(c.PostForm("session_id"))
		text = strings.TrimSpace(c.PostForm("text"))
		cropIDRaw = strings.TrimSpace(c.PostForm("crop_id"))
		imageData, err = readImageFromFormFile(c, "image")
		if err != nil {
			jsonError(c, http.StatusBadRequest, err)
			return
		}
	} else {
		var req jsonMessageRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Ожидается JSON: session_id, text"})
			return
		}
		sessionID = strings.TrimSpace(req.SessionID)
		text = strings.TrimSpace(req.Text)
		cropIDRaw = strings.TrimSpace(req.CropID)
	}

	if text == "" && len(imageData) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Нужен текст или изображение"})
		return
	}

	tgUser, err := ctxTelegramUser(c)
	if err != nil {
		jsonError(c, http.StatusUnauthorized, err)
		return
	}

	requestCropID, err := normalizeCropID(cropIDRaw)
	if err != nil {
		jsonError(c, http.StatusBadRequest, err)
		return
	}

	ctx := c.Request.Context()
	sid, sessionCrop, err := chatStore.GetOrCreateSession(ctx, sessionID, tgUser, requestCropID)
	if err != nil {
		log.Printf("GetOrCreateSession: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка сессии"})
		return
	}

	if len(imageData) > 0 {
		logAnalytics(c, "message_sent", map[string]any{"kind": "image", "crop_id": sessionCrop, "session_id": sid})
		handleImageMessage(c, sid, sessionCrop, tgUser.ID, text, imageData)
		return
	}
	logAnalytics(c, "message_sent", map[string]any{"kind": "text", "crop_id": sessionCrop, "session_id": sid})
	handleTextMessage(c, sid, sessionCrop, tgUser.ID, text)
}

// respondWithNewMessages отвечает JSON с новыми сообщениями (без повторной выгрузки всей истории).
func respondWithNewMessages(c *gin.Context, sid, cropID string, newMsgs []ChatMessage, extra gin.H, status int) {
	body := gin.H{
		"success":      true,
		"session_id":   sid,
		"crop_id":      cropID,
		"new_messages": newMsgs,
	}
	for k, v := range extra {
		body[k] = v
	}
	c.JSON(status, body)
}

// handleTextMessage: RAG+LLM, сохранение в БД, ответ с новыми сообщениями.
func handleTextMessage(c *gin.Context, sid, cropID string, telegramID int64, text string) {
	started := time.Now()
	ctx := c.Request.Context()

	historyStart := time.Now()
	prior, err := chatStore.HistoryForLLM(ctx, sid, telegramID, 0)
	historyMs := time.Since(historyStart).Milliseconds()
	if err != nil {
		log.Printf("HistoryForLLM: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка истории"})
		return
	}
	answer, ok, errMsg, ragSoft, trace := answerWithRAG(text, cropID, prior, sid)
	trace.HistoryMs = historyMs
	trace.SessionID = sid

	userMsg, err := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "user", Content: text, Kind: "text"})
	if err != nil {
		log.Printf("AppendMessage user: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка сохранения"})
		return
	}

	if ragSoft {
		asstMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: errMsg, Kind: "assistant"})
		logAnalytics(c, "rag_answer", map[string]any{"crop_id": cropID, "soft_fail": true})
		respondWithNewMessages(c, sid, cropID, []ChatMessage{userMsg, asstMsg}, gin.H{"error": errMsg}, http.StatusOK)
		return
	}
	if !ok {
		asstMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: "Ошибка: " + errMsg, Kind: "assistant"})
		status := http.StatusInternalServerError
		if strings.Contains(errMsg, "LLM_API_KEY") {
			status = http.StatusServiceUnavailable
		}
		respondWithNewMessages(c, sid, cropID, []ChatMessage{userMsg, asstMsg}, gin.H{"success": false, "error": errMsg}, status)
		return
	}

	asstMsg, err := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: answer, Kind: "assistant"})
	if err != nil {
		log.Printf("AppendMessage assistant: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка сохранения"})
		return
	}
	trace.MessageID = asstMsg.ID
	trace.TotalMs = time.Since(started).Milliseconds()
	logRAGTrace(trace)
	logAnalytics(c, "rag_answer", ragTraceAnalyticsPayload(trace, nil))
	respondWithNewMessages(c, sid, cropID, []ChatMessage{userMsg, asstMsg}, nil, http.StatusOK)
}

// handleImageMessage: CV, рекомендация LLM, сохранение token и истории.
func handleImageMessage(c *gin.Context, sid, cropID string, telegramID int64, caption string, imageData []byte) {
	ctx := c.Request.Context()
	prior, err := chatStore.HistoryForLLM(ctx, sid, telegramID, 0)
	if err != nil {
		log.Printf("HistoryForLLM: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка истории"})
		return
	}

	token, err := chatStore.SaveImage(imageData)
	if err != nil {
		log.Printf("SaveImage: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Не удалось сохранить фото"})
		return
	}

	result, clsErr := classifyAndRecommend(imageData, cropID, caption, prior)
	if clsErr != nil {
		errText := publicAPIError(clsErr)
		log.Printf("Messenger classify error: %v", clsErr)
		userMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{
			Role: "user", Content: caption, Kind: "image", ImageToken: token,
		})
		asstMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: errText, Kind: "assistant"})
		logAnalytics(c, "photo_classified", map[string]any{"crop_id": cropID, "success": false})
		respondWithNewMessages(c, sid, cropID, []ChatMessage{userMsg, asstMsg}, gin.H{"error": errText}, http.StatusOK)
		return
	}
	classification := result.Classification

	userMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{
		Role:            "user",
		Content:         caption,
		Kind:            "image",
		ImageToken:      token,
		ClassPrediction: classification.Prediction,
		ClassConfidence: classification.Confidence,
	})

	asstMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: result.Recommendation, Kind: "assistant"})
	logAnalytics(c, "photo_classified", map[string]any{
		"crop_id":    cropID,
		"success":    true,
		"prediction": classification.Prediction,
		"confidence": classification.Confidence,
	})
	respondWithNewMessages(c, sid, cropID, []ChatMessage{userMsg, asstMsg}, nil, http.StatusOK)
}
