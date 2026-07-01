package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

func handleAuthInfo(c *gin.Context) {
	telegram := !config.TelegramAuthDisabled && config.TelegramBotToken != ""
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"auth": gin.H{
			"telegram":    telegram,
			"web_api_key": apiKeyCount() > 0,
			"dev_mode":    config.TelegramAuthDisabled,
		},
	})
}
