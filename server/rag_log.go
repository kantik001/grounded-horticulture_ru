package main

import (
	"log"
	"strings"
)

// RAGTrace — метрики одного текстового RAG-запроса (без тела LLM).
type RAGTrace struct {
	CropID        string
	SessionID     string
	MessageID     int64
	Question      string
	Category      string
	FragmentCount int
	VerifyPass    bool
	VerifyReason  string
	SoftFail      bool
	Stream        bool
	RetrievalMs   int64
	LLMMs         int64
	HistoryMs     int64
	TotalMs       int64
}

func truncateRAGQuestion(q string) string {
	q = strings.TrimSpace(q)
	runes := []rune(q)
	if len(runes) > 120 {
		return string(runes[:120]) + "…"
	}
	return q
}

// logRAGTrace пишет структурированную строку [RAG] для разбора качества и latency.
func logRAGTrace(t RAGTrace) {
	category := strings.TrimSpace(t.Category)
	if category == "" {
		category = "general"
	}
	log.Printf(
		"[RAG] crop_id=%s session_id=%s message_id=%d category=%s fragments=%d verify_pass=%v soft_fail=%v stream=%v retrieval_ms=%d llm_ms=%d history_ms=%d total_ms=%d reason=%q question=%q",
		t.CropID,
		t.SessionID,
		t.MessageID,
		category,
		t.FragmentCount,
		t.VerifyPass,
		t.SoftFail,
		t.Stream,
		t.RetrievalMs,
		t.LLMMs,
		t.HistoryMs,
		t.TotalMs,
		t.VerifyReason,
		truncateRAGQuestion(t.Question),
	)
	recordRAGTraceMetrics(t)
}

// ragTraceAnalyticsPayload — поля latency для analytics_events (event_type rag_answer).
func ragTraceAnalyticsPayload(t RAGTrace, extra map[string]any) map[string]any {
	payload := map[string]any{
		"crop_id":       t.CropID,
		"session_id":    t.SessionID,
		"message_id":    t.MessageID,
		"category":      t.Category,
		"fragments":     t.FragmentCount,
		"verify_pass":   t.VerifyPass,
		"soft_fail":     t.SoftFail,
		"stream":        t.Stream,
		"retrieval_ms":  t.RetrievalMs,
		"llm_ms":        t.LLMMs,
		"history_ms":    t.HistoryMs,
		"total_ms":      t.TotalMs,
		"verify_reason": t.VerifyReason,
	}
	for k, v := range extra {
		payload[k] = v
	}
	return payload
}
