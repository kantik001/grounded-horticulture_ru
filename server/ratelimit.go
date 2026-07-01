package main

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

const rateLimitGCInterval = 256

// rateLimiter — простой in-memory лимитер (для одного инстанса Go).
// На продакшене с несколькими репликами заменим на Redis (фаза 1B).
type rateLimiter struct {
	mu       sync.Mutex
	limit    int
	window   time.Duration
	counters map[string][]time.Time
	ops      uint64
}

// Создаёт in-memory лимитер запросов на пользователя за окно времени.
func newRateLimiter(limit int, window time.Duration) *rateLimiter {
	return &rateLimiter{
		limit:    limit,
		window:   window,
		counters: make(map[string][]time.Time),
	}
}

// gcStale удаляет ключи без запросов в текущем окне (защита от утечки памяти).
func (rl *rateLimiter) gcStale(now time.Time) {
	cutoff := now.Add(-rl.window)
	for key, times := range rl.counters {
		var kept []time.Time
		for _, ts := range times {
			if ts.After(cutoff) {
				kept = append(kept, ts)
			}
		}
		if len(kept) == 0 {
			delete(rl.counters, key)
			continue
		}
		rl.counters[key] = kept
	}
}

// Проверяет, не превышен ли лимит для ключа (tg:… или api:…).
func (rl *rateLimiter) allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-rl.window)
	times := rl.counters[key]
	var kept []time.Time
	for _, ts := range times {
		if ts.After(cutoff) {
			kept = append(kept, ts)
		}
	}
	if rl.limit > 0 && len(kept) >= rl.limit {
		if len(kept) == 0 {
			delete(rl.counters, key)
		} else {
			rl.counters[key] = kept
		}
		return false
	}
	kept = append(kept, now)
	rl.counters[key] = kept

	rl.ops++
	if rl.ops%rateLimitGCInterval == 0 {
		rl.gcStale(now)
	}
	return true
}

// Gin-middleware: 429 при превышении лимита запросов в минуту.
func rateLimitMiddleware(rl *rateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		if rl == nil || rl.limit <= 0 {
			c.Next()
			return
		}
		key := rateLimitKey(c)
		if key == "anon" {
			c.Next()
			return
		}
		if !rl.allow(key) {
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"success": false,
				"error":   "Слишком много запросов. Подождите минуту и попробуйте снова.",
			})
			return
		}
		c.Next()
	}
}
