package main

import (
	"strings"
	"testing"
)

func TestTruncateRAGQuestion(t *testing.T) {
	short := truncateRAGQuestion("  парша  ")
	if short != "парша" {
		t.Fatalf("got %q", short)
	}
	long := strings.Repeat("а", 130)
	out := truncateRAGQuestion(long)
	if len([]rune(out)) != 121 || !strings.HasSuffix(out, "…") {
		t.Fatalf("expected 121 runes with ellipsis, got runes=%d %q", len([]rune(out)), out)
	}
}

func TestRAGTraceAnalyticsPayload(t *testing.T) {
	p := ragTraceAnalyticsPayload(RAGTrace{
		CropID:        "apple",
		SessionID:     "abc",
		MessageID:     42,
		RetrievalMs:   100,
		LLMMs:         2000,
		TotalMs:       2200,
		FragmentCount: 8,
		VerifyPass:    true,
	}, map[string]any{"extra": true})
	if p["retrieval_ms"] != int64(100) || p["llm_ms"] != int64(2000) {
		t.Fatalf("unexpected payload: %v", p)
	}
	if p["extra"] != true {
		t.Fatal("expected extra field")
	}
}
