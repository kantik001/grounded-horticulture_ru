package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// Точка входа: Postgres, миграции, каталоги культур, Gin-роутер и HTTP-сервер.
func main() {
	config = loadConfig()
	logStartup(config)

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	pool, err := waitForPostgres(ctx, config.DatabaseURL, 30)
	if err != nil {
		log.Fatalf("PostgreSQL: %v", err)
	}
	migDir, err := findMigrationsDir()
	if err != nil {
		log.Fatalf("Migrations: %v", err)
	}
	if err := runAllMigrations(ctx, pool, migDir); err != nil {
		log.Fatalf("Apply migrations: %v", err)
	}
	pool.Close()

	if err := loadCropCatalog(); err != nil {
		log.Fatalf("Crops config: %v", err)
	}
	if err := loadPromptCatalog(); err != nil {
		log.Fatalf("Prompts config: %v", err)
	}
	if err := loadOnboardingConfig(); err != nil {
		log.Fatalf("Onboarding config: %v", err)
	}
	if err := loadPhotoTemplates(); err != nil {
		log.Fatalf("Photo templates: %v", err)
	}
	if err := loadBrandingConfig(); err != nil {
		log.Fatalf("Branding config: %v", err)
	}
	loadAPIKeys(config)

	chatStore, err = newChatStore(context.Background(), config.DatabaseURL, config.UploadDir)
	if err != nil {
		log.Fatalf("ChatStore: %v", err)
	}
	defer chatStore.Close()
	log.Printf("PostgreSQL: connected, migrations from %s", migDir)
	log.Printf("Crops loaded: %d, default=%s", len(cropCatalog.Crops), cropCatalog.DefaultCrop)

	gin.SetMode(gin.ReleaseMode)

	router := gin.Default()
	router.Use(corsMiddleware(config.CORSAllowedOrigins))
	router.Use(metricsMiddleware())
	router.Use(func(c *gin.Context) {
		path := c.Request.URL.Path
		if strings.Contains(path, "/media/") || strings.HasSuffix(path, "/stream") || path == "/metrics" {
			c.Next()
			return
		}
		c.Writer.Header().Set("Content-Type", "application/json; charset=utf-8")
		c.Next()
	})

	rl := newRateLimiter(config.RateLimitPerMinute, time.Minute)

	registerPublicRoutes(router)
	registerAdminRoutes(router, config)
	registerProtectedRoutes(router, config, rl)
	startConfigReloadWatcher()

	serverAddr := fmt.Sprintf(":%s", config.ServerPort)
	log.Printf("Server starting on port %s", config.ServerPort)
	if err := router.Run(serverAddr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
