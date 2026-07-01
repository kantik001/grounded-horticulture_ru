package main

import (
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// handleMessageStream — текстовый RAG+LLM с SSE-стримингом токенов LLM.
func handleMessageStream(c *gin.Context) {
	var req jsonMessageRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Ожидается JSON: session_id, text"})
		return
	}
	text := strings.TrimSpace(req.Text)
	if text == "" {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Нужен текст"})
		return
	}

	tgUser, err := ctxTelegramUser(c)
	if err != nil {
		jsonError(c, http.StatusUnauthorized, err)
		return
	}

	requestCropID, err := normalizeCropID(strings.TrimSpace(req.CropID))
	if err != nil {
		jsonError(c, http.StatusBadRequest, err)
		return
	}

	ctx := c.Request.Context()
	sid, sessionCrop, err := chatStore.GetOrCreateSession(ctx, strings.TrimSpace(req.SessionID), tgUser, requestCropID)
	if err != nil {
		log.Printf("GetOrCreateSession: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка сессии"})
		return
	}

	logAnalytics(c, "message_sent", map[string]any{"kind": "text", "crop_id": sessionCrop, "session_id": sid, "stream": true})

	started := time.Now()
	historyStart := time.Now()
	prior, err := chatStore.HistoryForLLM(ctx, sid, tgUser.ID, 0)
	historyMs := time.Since(historyStart).Milliseconds()
	if err != nil {
		log.Printf("HistoryForLLM: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка истории"})
		return
	}

	input, errMsg, ragSoft, err := buildRAGLLMMessages(text, sessionCrop, prior, sid)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": publicAPIError(err)})
		return
	}

	userMsg, err := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "user", Content: text, Kind: "text"})
	if err != nil {
		log.Printf("AppendMessage user: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Ошибка сохранения"})
		return
	}

	if ragSoft {
		asstMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: errMsg, Kind: "assistant"})
		logAnalytics(c, "rag_answer", map[string]any{"crop_id": sessionCrop, "soft_fail": true, "stream": true})
		respondWithNewMessages(c, sid, sessionCrop, []ChatMessage{userMsg, asstMsg}, gin.H{"error": errMsg}, http.StatusOK)
		return
	}
	if errMsg != "" {
		asstMsg, _ := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: "Ошибка: " + errMsg, Kind: "assistant"})
		status := http.StatusInternalServerError
		if strings.Contains(errMsg, "LLM_API_KEY") {
			status = http.StatusServiceUnavailable
		}
		respondWithNewMessages(c, sid, sessionCrop, []ChatMessage{userMsg, asstMsg}, gin.H{"success": false, "error": errMsg}, status)
		return
	}

	beginSSEStream(c)
	if err := writeSSE(c, "meta", gin.H{
		"session_id":   sid,
		"crop_id":      sessionCrop,
		"user_message": userMsg,
	}); err != nil {
		log.Printf("SSE meta: %v", err)
		return
	}

	llmStart := time.Now()
	raw, err := callLLMCompletionStream(ctx, input.Messages, func(chunk string) error {
		return writeSSE(c, "delta", gin.H{"content": chunk})
	})
	llmMs := time.Since(llmStart).Milliseconds()
	if err != nil {
		recordLLMError()
		log.Printf("LLM stream error: %v", err)
		_ = writeSSE(c, "error", gin.H{"error": publicAPIError(err)})
		return
	}

	answer, ok, verifyPass, verifyReason := finalizeRAGAnswer(raw, input, sid)
	if !ok {
		_ = writeSSE(c, "error", gin.H{"error": "Не удалось сформировать ответ"})
		return
	}

	asstMsg, err := chatStore.AppendMessage(ctx, sid, ChatMessage{Role: "assistant", Content: answer, Kind: "assistant"})
	if err != nil {
		log.Printf("AppendMessage assistant: %v", err)
		_ = writeSSE(c, "error", gin.H{"error": "Ошибка сохранения"})
		return
	}

	trace := RAGTrace{
		CropID:        input.CropID,
		SessionID:     sid,
		MessageID:     asstMsg.ID,
		Question:      input.Question,
		Category:      input.Category,
		FragmentCount: len(input.RAGOut.Fragments),
		VerifyPass:    verifyPass,
		VerifyReason:  verifyReason,
		SoftFail:      !verifyPass,
		Stream:        true,
		RetrievalMs:   input.RetrievalMs,
		LLMMs:         llmMs,
		HistoryMs:     historyMs,
		TotalMs:       time.Since(started).Milliseconds(),
	}
	logRAGTrace(trace)
	logAnalytics(c, "rag_answer", ragTraceAnalyticsPayload(trace, nil))

	_ = writeSSE(c, "done", gin.H{
		"success":           true,
		"session_id":        sid,
		"crop_id":           sessionCrop,
		"assistant_message": asstMsg,
	})
}
