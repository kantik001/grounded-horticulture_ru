package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type verifyContractCase struct {
	ID                 string `json:"id"`
	Fragments          []struct {
		Content string `json:"content"`
	} `json:"fragments"`
	Answer             string `json:"answer"`
	ExpectPass         bool   `json:"expect_pass"`
	ExpectReasonSubstr string `json:"expect_reason_substr"`
}

type verifyContractFixture struct {
	Cases []verifyContractCase `json:"cases"`
}

func verifyContractFixturePath(t *testing.T) string {
	t.Helper()
	for _, p := range []string{
		filepath.Join("..", "tests", "fixtures", "rag_verify_contract.json"),
		filepath.Join("tests", "fixtures", "rag_verify_contract.json"),
	} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	t.Fatal("rag_verify_contract.json not found")
	return ""
}

func loadVerifyContractCases(t *testing.T) []verifyContractCase {
	t.Helper()
	body, err := os.ReadFile(verifyContractFixturePath(t))
	if err != nil {
		t.Fatalf("read contract fixture: %v", err)
	}
	var fix verifyContractFixture
	if err := json.Unmarshal(body, &fix); err != nil {
		t.Fatalf("parse contract fixture: %v", err)
	}
	if len(fix.Cases) == 0 {
		t.Fatal("contract fixture has no cases")
	}
	return fix.Cases
}

func TestVerifyRAGAnswer_ContractFixture(t *testing.T) {
	for _, tc := range loadVerifyContractCases(t) {
		tc := tc
		t.Run(tc.ID, func(t *testing.T) {
			fragments := make([]RAGFragment, 0, len(tc.Fragments))
			for _, fr := range tc.Fragments {
				fragments = append(fragments, RAGFragment{Filename: "test.txt", Content: fr.Content})
			}
			ok, reason := verifyRAGAnswer(tc.Answer, fragments)
			if ok != tc.ExpectPass {
				t.Fatalf("expected pass=%v, got %v, reason=%q", tc.ExpectPass, ok, reason)
			}
			if tc.ExpectReasonSubstr != "" && !ok && !strings.Contains(reason, tc.ExpectReasonSubstr) {
				t.Fatalf("reason %q should contain %q", reason, tc.ExpectReasonSubstr)
			}
		})
	}
}
