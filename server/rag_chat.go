package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// RAGFragment — фрагмент статьи из Python.
type RAGFragment struct {
	Filename string `json:"filename"`
	Content  string `json:"content"`
}

// pythonRAGContextResponse — ответ POST /rag/context.
type pythonRAGContextResponse struct {
	Success   bool          `json:"success"`
	Error     string        `json:"error,omitempty"`
	Context   string        `json:"context,omitempty"`
	FewShot   string        `json:"few_shot,omitempty"`
	Category  string        `json:"category,omitempty"`
	Fragments []RAGFragment `json:"fragments,omitempty"`
}

// POST в Python /rag/context: фрагменты статей и few-shot для промпта.
func fetchRAGContext(question, cropID string) (*pythonRAGContextResponse, error) {
	body := map[string]string{"question": question, "crop_id": cropID}
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("marshal RAG request: %w", err)
	}
	req, err := http.NewRequest("POST", config.PythonRAGURL, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("create RAG request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json; charset=utf-8")
	resp, err := pythonHTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("RAG request failed: %w", err)
	}
	defer resp.Body.Close()
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read RAG response: %w", err)
	}
	var out pythonRAGContextResponse
	if err := json.Unmarshal(responseBody, &out); err != nil {
		return nil, fmt.Errorf("parse RAG response: %w: %s", err, string(responseBody))
	}
	// 422 от Python = штатный «нет контекста» (success:false), не транспортная ошибка.
	if resp.StatusCode == http.StatusUnprocessableEntity && !out.Success {
		return &out, nil
	}
	if resp.StatusCode != http.StatusOK {
		if out.Error != "" {
			return &out, fmt.Errorf("%s", out.Error)
		}
		return &out, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(responseBody))
	}
	return &out, nil
}

const ragUserPromptTpl = `<system>%s</system>
<context>%s</context>
<examples>%s</examples>
<task>Ответь на вопрос пользователя чётко, по делу, грамотно.</task>
<constraints>
- НЕ ВЫДУМЫВАЙ. Если ответа нет в контексте — скажи: "В справочных материалах нет информации по вашему вопросу."
- Отвечай только на русском языке, литературно, без ошибок.
- НЕ используй слова "скорее всего", "вероятно", "возможно", "наверное".
- НЕ используй слова "аботчик", "Я думаю", "мне нужно ответить", "давайте посмотрим".
- Если в контексте есть конкретные цифры, дозировки, табличные данные — обязательно включи их в ответ.
- Ответ должен быть развёрнутым, полезным, содержать все детали из контекста.
- Завершай ответ полностью, не обрывай на полуслове.
- НЕ указывай названия статей, журналов, авторов и ссылки на публикации.
</constraints>
<output_format>
Ответ должен начинаться сразу с факта, без лишних вступлений. Будь подробным и грамотным.
</output_format>
Вопрос: %s
`

// Собирает user-промпт для LLM из контекста RAG и few-shot примеров.
func buildRAGUserPrompt(question, context, fewShot, taskIntro string) string {
	return fmt.Sprintf(ragUserPromptTpl, taskIntro, context, fewShot, question)
}

// ragAnswerDisclaimer — общий дисклеймер в конце ответа (без названий статей).
// ChatRequest — тело POST /chat (устаревший API; используйте POST /message).
type ChatRequest struct {
	Question string `json:"question"`
	CropID   string `json:"crop_id"`
}

// ragLLMInput — подготовленный RAG-контекст и сообщения для LLM.
type ragLLMInput struct {
	CropID      string
	Question    string
	Messages    []Message
	RAGOut      *pythonRAGContextResponse
	RetrievalMs int64
	Category    string
}

// buildRAGLLMMessages выполняет retrieval и собирает промпт для LLM (без вызова LLM).
func buildRAGLLMMessages(q, cropID string, history []Message, sessionID string) (*ragLLMInput, string, bool, error) {
	q = strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(q, "\r", " "), "\n", " "))
	if q == "" {
		return nil, "Пустой вопрос", false, nil
	}

	cropID, err := normalizeCropID(cropID)
	if err != nil {
		return nil, publicAPIError(err), false, nil
	}
	if err := requireRAGEnabled(cropID); err != nil {
		return nil, publicAPIError(err), false, nil
	}

	retrievalStart := time.Now()
	ragOut, err := fetchRAGContext(q, cropID)
	retrievalMs := time.Since(retrievalStart).Milliseconds()
	if err != nil {
		log.Printf("RAG fetch error: %v", err)
		msg := publicAPIError(err)
		if ragOut != nil && ragOut.Error != "" {
			msg = ragOut.Error
		}
		return nil, msg, false, err
	}
	if !ragOut.Success {
		logRAGTrace(RAGTrace{
			CropID:        cropID,
			SessionID:     sessionID,
			Question:      q,
			Category:      ragOut.Category,
			FragmentCount: len(ragOut.Fragments),
			VerifyPass:    false,
			VerifyReason:  ragOut.Error,
			SoftFail:      true,
			RetrievalMs:   retrievalMs,
			TotalMs:       retrievalMs,
		})
		return nil, ragOut.Error, true, nil
	}
	if config.LLMAPIKey == "" {
		return nil, "Для текстового чата задайте LLM_API_KEY (OpenRouter / OpenAI-совместимый API).", false, nil
	}

	prompts := promptsForCrop(cropID)
	userPrompt := buildRAGUserPrompt(q, ragOut.Context, ragOut.FewShot, prompts.RAGTaskIntro)
	var msgs []Message
	msgs = append(msgs, Message{
		Role:    "system",
		Content: prompts.RAGSystem,
	})
	msgs = append(msgs, history...)
	msgs = append(msgs, Message{Role: "user", Content: userPrompt})

	return &ragLLMInput{
		CropID:      cropID,
		Question:    q,
		Messages:    msgs,
		RAGOut:      ragOut,
		RetrievalMs: retrievalMs,
		Category:    ragOut.Category,
	}, "", false, nil
}

// finalizeRAGAnswer очищает ответ LLM, добавляет дисклеймер и верифицирует по фрагментам.
func finalizeRAGAnswer(raw string, input *ragLLMInput, sessionID string) (answer string, ok bool, verifyPass bool, verifyReason string) {
	answer = cleanRAGAnswer(raw)
	answer = appendRAGDisclaimer(answer)
	verifyPass, verifyReason = verifyRAGAnswer(answer, input.RAGOut.Fragments)
	if !verifyPass {
		return fmt.Sprintf("⚠️ Система не смогла подтвердить ответ источниками. Сообщение администратору: %s\n\nРекомендуем обратиться к агроному.", verifyReason), true, false, verifyReason
	}
	return answer, true, true, verifyReason
}

// answerWithRAG выполняет RAG + LLM с опциональной историей диалога (роли user/assistant).
// sessionID — для логов RAG (может быть пустым для POST /chat).
func answerWithRAG(q, cropID string, history []Message, sessionID string) (answer string, success bool, errMsg string, ragSoftFail bool, trace RAGTrace) {
	input, errMsg, ragSoft, err := buildRAGLLMMessages(q, cropID, history, sessionID)
	if err != nil {
		return "", false, errMsg, false, trace
	}
	if ragSoft {
		return "", false, errMsg, true, trace
	}
	if errMsg != "" {
		return "", false, errMsg, false, trace
	}

	llmStart := time.Now()
	raw, err := callLLMCompletion(input.Messages)
	llmMs := time.Since(llmStart).Milliseconds()
	if err != nil {
		recordLLMError()
		log.Printf("LLM chat error: %v", err)
		return "", false, publicAPIError(err), false, trace
	}
	answer, ok, verifyPass, verifyReason := finalizeRAGAnswer(raw, input, sessionID)
	trace = RAGTrace{
		CropID:        input.CropID,
		SessionID:     sessionID,
		Question:      input.Question,
		Category:      input.Category,
		FragmentCount: len(input.RAGOut.Fragments),
		RetrievalMs:   input.RetrievalMs,
		LLMMs:         llmMs,
		VerifyPass:    verifyPass,
		VerifyReason:  verifyReason,
		SoftFail:      !verifyPass,
	}
	if !ok {
		return "", false, "Не удалось сформировать ответ", false, trace
	}
	return answer, true, "", false, trace
}

// POST /chat: RAG + LLM без сессии. Устарел: Web App использует POST /message.
func handleChat(c *gin.Context) {
	var req ChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error":   "Некорректный JSON (нужно поле question)",
		})
		return
	}
	q := strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(req.Question, "\r", " "), "\n", " "))
	if q == "" {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Пустой вопрос"})
		return
	}

	answer, ok, errMsg, ragSoft, trace := answerWithRAG(q, req.CropID, nil, "")
	if ragSoft {
		c.JSON(http.StatusOK, gin.H{"success": false, "error": errMsg})
		return
	}
	if errMsg != "" && !ok {
		if strings.Contains(errMsg, "LLM_API_KEY") {
			c.JSON(http.StatusServiceUnavailable, gin.H{"success": false, "error": errMsg})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": errMsg})
		return
	}
	if !ok {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": errMsg})
		return
	}
	trace.TotalMs = trace.RetrievalMs + trace.LLMMs
	logRAGTrace(trace)
	c.JSON(http.StatusOK, gin.H{"success": true, "answer": answer})
}
