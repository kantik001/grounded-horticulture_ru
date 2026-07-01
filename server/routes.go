package main

import (
	"github.com/gin-gonic/gin"
)

// registerPublicRoutes — health, crops, onboarding (с дублем /api для nginx).
func registerPublicRoutes(router *gin.Engine) {
	router.GET("/health", handleHealthCheck)
	router.GET("/api/health", handleHealthCheck)
	router.GET("/metrics", handleMetrics)
	router.GET("/api/metrics", handleMetrics)
	router.GET("/crops", handleListCrops)
	router.GET("/api/crops", handleListCrops)
	router.GET("/onboarding", handleOnboarding)
	router.GET("/api/onboarding", handleOnboarding)
	router.GET("/branding", handleBranding)
	router.GET("/api/branding", handleBranding)
	router.GET("/auth/info", handleAuthInfo)
	router.GET("/api/auth/info", handleAuthInfo)
}

// mountProtectedAPI регистрирует защищённые маршруты на одной группе маршрутов.
func mountProtectedAPI(r gin.IRoutes, auth, lim gin.HandlerFunc) {
	deprecated := deprecatedAPIMiddleware()
	r.POST("/classify", auth, lim, handleClassification)
	r.POST("/chat", auth, lim, deprecated, handleChat)
	r.POST("/session", auth, lim, handleNewSession)
	r.GET("/history", auth, lim, handleHistory)
	r.POST("/message", auth, lim, handleMessage)
	r.POST("/message/stream", auth, lim, handleMessageStream)
	r.POST("/feedback", auth, lim, handleFeedback)
	r.GET("/media/:token", auth, lim, handleMedia)
}

// registerProtectedRoutes — Telegram или API key, rate limit; дубль без префикса и с /api.
func registerProtectedRoutes(router *gin.Engine, cfg *Config, rl *rateLimiter) {
	auth := combinedAuthMiddleware(cfg)
	lim := rateLimitMiddleware(rl)
	mountProtectedAPI(router.Group(""), auth, lim)
	mountProtectedAPI(router.Group("/api"), auth, lim)
}

// deprecatedAPIMiddleware помечает устаревшие эндпоинты (POST /chat).
func deprecatedAPIMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Deprecation", "true")
		c.Header("Link", "</message>; rel=\"successor-version\"")
		c.Next()
	}
}
