package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestCombinedAuthMiddleware_APIKey(t *testing.T) {
	gin.SetMode(gin.TestMode)
	apiKeyRegistry = map[string]apiKeyRecord{
		"test-key": {Label: "browser", Roles: []string{RoleChatOnly}},
	}
	cfg := &Config{TelegramAuthDisabled: false, TelegramBotToken: "x"}

	r := gin.New()
	r.GET("/protected", combinedAuthMiddleware(cfg), func(c *gin.Context) {
		u, err := ctxTelegramUser(c)
		if err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.JSON(http.StatusOK, gin.H{"id": u.ID, "username": u.Username})
	})

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set(headerAPIKey, "test-key")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
}

func TestCombinedAuthMiddleware_InvalidKey(t *testing.T) {
	gin.SetMode(gin.TestMode)
	apiKeyRegistry = map[string]apiKeyRecord{}
	cfg := &Config{TelegramAuthDisabled: false, TelegramBotToken: "x"}

	r := gin.New()
	r.GET("/protected", combinedAuthMiddleware(cfg), func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set(headerAPIKey, "bad")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status=%d", w.Code)
	}
}
