package main

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"

	"github.com/gin-gonic/gin"
)

var onboardingQuestions map[string][]string

// Загружает config/onboarding.json (подсказки-вопросы по культурам).
func loadOnboardingConfig() error {
	path := onboardingConfigPath()
	body, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(body, &onboardingQuestions)
}

// Возвращает путь к onboarding.json.
func onboardingConfigPath() string {
	if p := os.Getenv("ONBOARDING_CONFIG_PATH"); p != "" {
		return p
	}
	for _, candidate := range []string{
		"/config/onboarding.json",
		filepath.Join("..", "config", "onboarding.json"),
		filepath.Join("config", "onboarding.json"),
	} {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return filepath.Join("config", "onboarding.json")
}

// GET /onboarding: примеры вопросов для выбранной культуры.
func handleOnboarding(c *gin.Context) {
	cropID, err := normalizeCropID(c.Query("crop_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}
	questions := onboardingQuestions[cropID]
	if questions == nil {
		questions = []string{}
	}
	c.JSON(http.StatusOK, gin.H{
		"success":   true,
		"crop_id":   cropID,
		"questions": questions,
	})
}
