package main

import (
	"context"
	"encoding/json"
	"time"
)

// FeedbackReportItem — одна оценка ответа с контекстом диалога.
type FeedbackReportItem struct {
	FeedbackAt  time.Time       `json:"feedback_at"`
	Rating      int             `json:"rating"`
	MessageID   int64           `json:"message_id"`
	SessionID   string          `json:"session_id"`
	CropID      string          `json:"crop_id"`
	TelegramID  int64           `json:"telegram_id"`
	Question    string          `json:"question"`
	Answer      string          `json:"answer"`
	RAG         *FeedbackRAGMeta `json:"rag,omitempty"`
}

// FeedbackRAGMeta — метрики RAG из analytics_events (event_type rag_answer).
type FeedbackRAGMeta struct {
	Category      string `json:"category,omitempty"`
	FragmentCount int    `json:"fragments,omitempty"`
	VerifyPass    bool   `json:"verify_pass"`
	VerifyReason  string `json:"verify_reason,omitempty"`
	SoftFail      bool   `json:"soft_fail"`
	RetrievalMs   int64  `json:"retrieval_ms,omitempty"`
	LLMMs         int64  `json:"llm_ms,omitempty"`
	TotalMs       int64  `json:"total_ms,omitempty"`
}

// FeedbackSummary — сводка 👍/👎.
type FeedbackSummary struct {
	Likes    int `json:"likes"`
	Dislikes int `json:"dislikes"`
}

// ListFeedbackReport возвращает оценки с парой вопрос/ответ (последний user перед assistant).
// ratingFilter: 0 — все, 1 или -1 — только этот рейтинг.
func (st *ChatStore) ListFeedbackReport(ctx context.Context, ratingFilter, limit int) ([]FeedbackReportItem, FeedbackSummary, error) {
	if limit <= 0 || limit > 200 {
		limit = 50
	}
	summary, err := st.feedbackSummary(ctx)
	if err != nil {
		return nil, summary, err
	}
	ratingClause := ""
	args := []any{limit}
	if ratingFilter == 1 || ratingFilter == -1 {
		ratingClause = " AND mf.rating = $2 "
		args = []any{limit, ratingFilter}
	}
	query := `
		SELECT mf.created_at, mf.rating, mf.message_id, m_assist.session_id, cs.crop_id,
		       u.telegram_id, m_assist.content,
		       COALESCE((
		           SELECT m2.content
		           FROM messages m2
		           WHERE m2.session_id = m_assist.session_id
		             AND m2.role = 'user'
		             AND m2.id < m_assist.id
		           ORDER BY m2.id DESC
		           LIMIT 1
		       ), '') AS question,
		       COALESCE((
		           SELECT ae.payload
		           FROM analytics_events ae
		           WHERE ae.event_type = 'rag_answer'
		             AND (ae.payload->>'message_id')::bigint = mf.message_id
		           ORDER BY ae.created_at DESC
		           LIMIT 1
		       ), '{}'::jsonb) AS rag_payload
		FROM message_feedback mf
		JOIN messages m_assist ON m_assist.id = mf.message_id AND m_assist.role = 'assistant'
		JOIN chat_sessions cs ON cs.id = m_assist.session_id
		JOIN users u ON u.id = mf.user_id
		WHERE 1=1` + ratingClause + `
		ORDER BY mf.created_at DESC
		LIMIT $1`
	rows, err := st.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, summary, err
	}
	defer rows.Close()
	var items []FeedbackReportItem
	for rows.Next() {
		var it FeedbackReportItem
		var ragPayload []byte
		if err := rows.Scan(
			&it.FeedbackAt, &it.Rating, &it.MessageID, &it.SessionID, &it.CropID,
			&it.TelegramID, &it.Answer, &it.Question, &ragPayload,
		); err != nil {
			return nil, summary, err
		}
		it.RAG = parseFeedbackRAGMeta(ragPayload)
		items = append(items, it)
	}
	if items == nil {
		items = []FeedbackReportItem{}
	}
	return items, summary, rows.Err()
}

func (st *ChatStore) feedbackSummary(ctx context.Context) (FeedbackSummary, error) {
	var s FeedbackSummary
	err := st.pool.QueryRow(ctx, `
		SELECT
			COALESCE(SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END), 0)::int,
			COALESCE(SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END), 0)::int
		FROM message_feedback`,
	).Scan(&s.Likes, &s.Dislikes)
	return s, err
}

func parseFeedbackRAGMeta(raw []byte) *FeedbackRAGMeta {
	if len(raw) == 0 {
		return nil
	}
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil || len(payload) == 0 {
		return nil
	}
	meta := &FeedbackRAGMeta{}
	if v, ok := payload["category"].(string); ok {
		meta.Category = v
	}
	if v, ok := payload["verify_pass"].(bool); ok {
		meta.VerifyPass = v
	}
	if v, ok := payload["soft_fail"].(bool); ok {
		meta.SoftFail = v
	}
	if v, ok := payload["verify_reason"].(string); ok {
		meta.VerifyReason = v
	}
	meta.FragmentCount = int(jsonNumber(payload["fragments"]))
	meta.RetrievalMs = jsonNumber(payload["retrieval_ms"])
	meta.LLMMs = jsonNumber(payload["llm_ms"])
	meta.TotalMs = jsonNumber(payload["total_ms"])
	if meta.Category == "" && !meta.VerifyPass && meta.VerifyReason == "" && meta.FragmentCount == 0 {
		return nil
	}
	return meta
}

func jsonNumber(v any) int64 {
	switch n := v.(type) {
	case float64:
		return int64(n)
	case int64:
		return n
	case int:
		return int64(n)
	default:
		return 0
	}
}
