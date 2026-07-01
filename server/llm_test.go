package main

import (
	"strings"
	"testing"
)

func TestParseLLMStreamData(t *testing.T) {
	content, err := parseLLMStreamData(`{"choices":[{"delta":{"content":"парша"}}]}`)
	if err != nil {
		t.Fatal(err)
	}
	if content != "парша" {
		t.Fatalf("got %q", content)
	}
}

func TestReadLLMStream(t *testing.T) {
	body := strings.NewReader(
		"data: {\"choices\":[{\"delta\":{\"content\":\"А\"}}]}\n\n" +
			"data: {\"choices\":[{\"delta\":{\"content\":\"Б\"}}]}\n\n" +
			"data: [DONE]\n\n",
	)
	var chunks []string
	full, err := readLLMStream(body, func(s string) error {
		chunks = append(chunks, s)
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if full != "АБ" {
		t.Fatalf("full=%q", full)
	}
	if len(chunks) != 2 {
		t.Fatalf("chunks=%v", chunks)
	}
}
