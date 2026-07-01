package main

import (
	"fmt"
	"io"
	"mime/multipart"
	"strings"

	"github.com/gin-gonic/gin"
)

const maxUploadImageBytes = 10 * 1024 * 1024

// classifyAndRecommendResult — CV + текст рекомендации для одного фото.
type classifyAndRecommendResult struct {
	Classification   *ClassificationResult
	Recommendation   string
	UsedLLMTemplate bool
}

// readUploadImage читает файл из multipart с проверкой размера.
func readUploadImage(file multipart.File, size int64) ([]byte, error) {
	if size > maxUploadImageBytes {
		return nil, fmt.Errorf("изображение слишком большое (макс. 10 МБ)")
	}
	data, err := io.ReadAll(io.LimitReader(file, maxUploadImageBytes+1))
	if err != nil {
		return nil, fmt.Errorf("не удалось прочитать изображение: %w", err)
	}
	if len(data) > maxUploadImageBytes {
		return nil, fmt.Errorf("изображение слишком большое (макс. 10 МБ)")
	}
	return data, nil
}

// readImageFromFormFile читает поле multipart image через readUploadImage.
func readImageFromFormFile(c *gin.Context, field string) ([]byte, error) {
	fh, err := c.FormFile(field)
	if err != nil || fh == nil {
		return nil, nil
	}
	f, err := fh.Open()
	if err != nil {
		return nil, fmt.Errorf("не удалось открыть файл изображения")
	}
	defer f.Close()
	return readUploadImage(f, fh.Size)
}

// classifyAndRecommend: Python CV → рекомендация LLM или шаблон из config.
func classifyAndRecommend(imageData []byte, cropID, caption string, history []Message) (*classifyAndRecommendResult, error) {
	if err := requireCVEnabled(cropID); err != nil {
		return nil, err
	}
	classification, err := sendToClassifier(imageData, cropID)
	if err != nil {
		return nil, fmt.Errorf("ошибка классификации: %w", err)
	}
	if classification == nil || !classification.Success {
		msg := "ошибка классификации"
		if classification != nil && classification.Error != "" {
			msg = classification.Error
		}
		return nil, fmt.Errorf("%s", msg)
	}

	recommendation, recErr := generatePhotoRecommendation(classification, caption, history, cropID)
	usedTemplate := config.LLMAPIKey == "" || recErr != nil
	if recErr != nil {
		recommendation = generateTemplateRecommendation(classification)
	}
	recommendation = appendPhotoBetaNotice(recommendation)

	return &classifyAndRecommendResult{
		Classification:    classification,
		Recommendation:    recommendation,
		UsedLLMTemplate:   usedTemplate,
	}, nil
}

// appendPhotoBetaNotice добавляет бета-дисклеймер CV в конец рекомендации.
// Модель распознавания болезней ещё не обучена (ImageNet fallback), поэтому
// результат помечается как экспериментальный. Текст — из config/branding.json.
func appendPhotoBetaNotice(recommendation string) string {
	notice := strings.TrimSpace(brandingCatalog.PhotoBetaNotice)
	if notice == "" {
		return recommendation
	}
	body := strings.TrimSpace(recommendation)
	if body == "" {
		return notice
	}
	if strings.Contains(body, notice) {
		return body
	}
	return body + "\n\n" + notice
}

// parseClassifyForm читает image и crop_id из POST /classify.
func parseClassifyForm(c *gin.Context) (imageData []byte, cropID string, filename string, err error) {
	file, header, err := c.Request.FormFile("image")
	if err != nil {
		return nil, "", "", fmt.Errorf("не удалось получить файл image")
	}
	defer file.Close()

	imageData, err = readUploadImage(file, header.Size)
	if err != nil {
		return nil, "", "", err
	}

	cropID, err = normalizeCropID(c.PostForm("crop_id"))
	if err != nil {
		return nil, "", "", err
	}
	return imageData, cropID, header.Filename, nil
}
