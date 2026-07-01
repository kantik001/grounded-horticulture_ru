package main

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
)

// POST /classify: фото → Python CV → рекомендация LLM или шаблон (без сессии чата).
func handleClassification(c *gin.Context) {
	imageData, cropID, filename, err := parseClassifyForm(c)
	if err != nil {
		jsonError(c, http.StatusBadRequest, err)
		return
	}

	log.Printf("Получено изображение: %s (%d байт)", filename, len(imageData))

	result, err := classifyAndRecommend(imageData, cropID, "", nil)
	if err != nil {
		jsonError(c, http.StatusInternalServerError, err)
		return
	}
	if result.UsedLLMTemplate {
		log.Printf("Рекомендация по фото: использован шаблон (LLM недоступен или ошибка)")
	}

	c.JSON(http.StatusOK, RecommendationResponse{
		Success:              true,
		ClassificationResult: *result.Classification,
		Recommendation:       result.Recommendation,
	})
}
