package main

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestParseFeedbackRAGMeta(t *testing.T) {
	raw, _ := json.Marshal(map[string]any{
		"message_id":    float64(42),
		"category":      "disease",
		"fragments":     float64(8),
		"verify_pass":   false,
		"verify_reason": "Число(а) [72] не найдены",
		"retrieval_ms":  float64(1200),
		"llm_ms":        float64(800),
		"total_ms":      float64(2100),
		"soft_fail":     true,
	})
	meta := parseFeedbackRAGMeta(raw)
	if meta == nil {
		t.Fatal("expected meta")
	}
	if meta.Category != "disease" || meta.FragmentCount != 8 || meta.VerifyPass {
		t.Fatalf("unexpected meta: %+v", meta)
	}
	if meta.RetrievalMs != 1200 || meta.LLMMs != 800 {
		t.Fatalf("latency fields: %+v", meta)
	}
}

func TestHandleMetrics(t *testing.T) {
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	handleMetrics(c)
	if w.Code != 200 {
		t.Fatalf("status %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "garden_http_requests_total") {
		t.Fatalf("missing metrics: %s", body)
	}
}
