package main

import (
	"fmt"
	"strings"
)

// RecommendationResponse — ответ POST /classify (CV + текст рекомендации).
type RecommendationResponse struct {
	Success bool `json:"success"`
	ClassificationResult
	Recommendation string `json:"recommendation,omitempty"`
	Error          string `json:"error,omitempty"`
}

// buildPhotoUserPrompt собирает user-промпт для LLM по результату CV.
func buildPhotoUserPrompt(classification *ClassificationResult, caption string, prompts cropPrompts) string {
	body := fmt.Sprintf(
		prompts.PhotoUserBody,
		classification.Prediction,
		classification.Confidence*100,
		classification.TopPredictions,
	)
	var b strings.Builder
	b.WriteString(prompts.PhotoUserIntro)
	b.WriteString("\n\n")
	b.WriteString(body)
	if t := strings.TrimSpace(caption); t != "" {
		b.WriteString("\n\nПодпись пользователя к фото: ")
		b.WriteString(t)
	}
	return b.String()
}

// generatePhotoRecommendation — единая точка: LLM с историей или без.
func generatePhotoRecommendation(
	classification *ClassificationResult,
	caption string,
	history []Message,
	cropID string,
) (string, error) {
	if config.LLMAPIKey == "" {
		return generateTemplateRecommendation(classification), nil
	}
	prompts := promptsForCrop(cropID)
	userPrompt := buildPhotoUserPrompt(classification, caption, prompts)
	msgs := make([]Message, 0, len(history)+2)
	msgs = append(msgs, Message{Role: "system", Content: prompts.PhotoSystem})
	msgs = append(msgs, history...)
	msgs = append(msgs, Message{Role: "user", Content: userPrompt})
	return callLLMCompletion(msgs)
}

// generateTemplateRecommendation — статичный текст, если LLM недоступен.
func generateTemplateRecommendation(classification *ClassificationResult) string {
	rec, exists := photoTemplateCatalog[classification.Prediction]
	if !exists {
		rec = photoTemplateCatalog["default"]
		rec = replacePlaceholder(rec, "{{PREDICTION}}", classification.Prediction)
		confStr := fmt.Sprintf("%.1f", classification.Confidence*100)
		rec = replacePlaceholder(rec, "{{CONFIDENCE}}", confStr)
	}
	return rec
}

func replacePlaceholder(str, placeholder, value string) string {
	return strings.ReplaceAll(str, placeholder, value)
}
