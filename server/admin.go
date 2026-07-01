package main

import (
	"crypto/subtle"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

var safeFilename = regexp.MustCompile(`^[a-zA-Z0-9._-]+\.txt$`)

// Basic Auth для маршрутов /admin (ADMIN_USER / ADMIN_PASSWORD).
func adminBasicAuth(cfg *Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		if cfg.AdminPassword == "" {
			c.AbortWithStatusJSON(http.StatusServiceUnavailable, gin.H{
				"success": false,
				"error":   "Админка отключена: задайте ADMIN_PASSWORD в .env",
			})
			return
		}
		user, pass, ok := c.Request.BasicAuth()
		userOK := subtle.ConstantTimeCompare([]byte(user), []byte(cfg.AdminUser)) == 1
		passOK := subtle.ConstantTimeCompare([]byte(pass), []byte(cfg.AdminPassword)) == 1
		if !ok || !userOK || !passOK {
			c.Header("WWW-Authenticate", `Basic realm="Garden Admin"`)
			c.AbortWithStatus(http.StatusUnauthorized)
			return
		}
		c.Next()
	}
}

// Регистрирует админские маршруты: статьи, upload, reindex RAG.
func registerAdminRoutes(router *gin.Engine, cfg *Config) {
	auth := adminBasicAuth(cfg)
	g := router.Group("/admin")
	g.Use(auth)
	g.GET("/status", handleAdminStatus)
	g.GET("/articles", handleAdminListArticles)
	g.GET("/feedback", handleAdminFeedback)
	g.POST("/upload", handleAdminUpload)
	g.POST("/reindex", handleAdminReindex)

	api := router.Group("/api/admin")
	api.Use(auth)
	api.GET("/status", handleAdminStatus)
	api.GET("/articles", handleAdminListArticles)
	api.GET("/feedback", handleAdminFeedback)
	api.POST("/upload", handleAdminUpload)
	api.POST("/reindex", handleAdminReindex)
}

// GET /admin/status: краткая информация о data_dir и числе культур.
func handleAdminStatus(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"success":  true,
		"data_dir": config.DataDir,
		"crops":    len(cropCatalog.Crops),
	})
}

// GET /admin/feedback?rating=-1&limit=50 — оценки ответов с вопросом и текстом ответа.
func handleAdminFeedback(c *gin.Context) {
	if chatStore == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"success": false, "error": "База данных недоступна"})
		return
	}
	ratingFilter := 0
	if r := strings.TrimSpace(c.Query("rating")); r != "" {
		switch r {
		case "1", "-1":
			if _, err := fmt.Sscanf(r, "%d", &ratingFilter); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "rating: 1, -1 или пусто"})
				return
			}
		default:
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "rating: 1, -1 или пусто"})
			return
		}
	}
	limit := 50
	if l := strings.TrimSpace(c.Query("limit")); l != "" {
		if _, err := fmt.Sscanf(l, "%d", &limit); err != nil || limit < 1 {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "limit: число 1–200"})
			return
		}
	}
	items, summary, err := chatStore.ListFeedbackReport(c.Request.Context(), ratingFilter, limit)
	if err != nil {
		log.Printf("Admin feedback list: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Не удалось загрузить оценки"})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"summary": summary,
		"items":   items,
	})
}

// GET /admin/articles: список .txt статей для crop_id.
func handleAdminListArticles(c *gin.Context) {
	cropID, err := normalizeCropID(c.Query("crop_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}
	dir := filepath.Join(config.DataDir, cropID)
	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			c.JSON(http.StatusOK, gin.H{"success": true, "crop_id": cropID, "files": []string{}})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": err.Error()})
		return
	}
	var files []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(strings.ToLower(e.Name()), ".txt") {
			files = append(files, e.Name())
		}
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "crop_id": cropID, "files": files})
}

// POST /admin/upload: загрузка .txt статьи в data/{crop_id}/.
func handleAdminUpload(c *gin.Context) {
	cropID, err := normalizeCropID(c.PostForm("crop_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}
	fh, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Нужен файл .txt"})
		return
	}
	name := filepath.Base(fh.Filename)
	if !safeFilename.MatchString(name) {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Имя файла: латиница, цифры, .txt"})
		return
	}
	if fh.Size > 2*1024*1024 {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Макс. размер файла 2 МБ"})
		return
	}
	dir := filepath.Join(config.DataDir, cropID)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": err.Error()})
		return
	}
	dst := filepath.Join(dir, name)
	src, err := fh.Open()
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "error": err.Error()})
		return
	}
	defer src.Close()
	out, err := os.Create(dst)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": err.Error()})
		return
	}
	defer out.Close()
	if _, err := io.Copy(out, io.LimitReader(src, 2*1024*1024+1)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": err.Error()})
		return
	}
	log.Printf("Admin upload: %s -> %s", name, dst)
	c.JSON(http.StatusOK, gin.H{"success": true, "crop_id": cropID, "filename": name, "path": dst})
}

// POST /admin/reindex: запуск переиндексации Chroma в Python.
func handleAdminReindex(c *gin.Context) {
	if err := triggerRAGReindex(); err != nil {
		log.Printf("Admin reindex: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{"success": false, "error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Переиндексация RAG запущена"})
}

// Вызывает POST /admin/reindex на Python-сервисе с X-Admin-Secret.
func triggerRAGReindex() error {
	if config.AdminSecret == "" {
		return fmt.Errorf("ADMIN_SECRET не задан")
	}
	url := strings.TrimRight(config.PythonBaseURL, "/") + "/admin/reindex"
	req, err := http.NewRequest(http.MethodPost, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-Admin-Secret", config.AdminSecret)
	client := &http.Client{Timeout: 10 * time.Minute}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("python reindex HTTP %d: %s", resp.StatusCode, string(body))
	}
	return nil
}
