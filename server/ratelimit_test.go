package main

import (
	"testing"
	"time"
)

func TestRateLimiterGCRemovesStaleKeys(t *testing.T) {
	rl := newRateLimiter(5, time.Minute)
	rl.allow("tg:1")
	rl.allow("tg:2")

	if len(rl.counters) != 2 {
		t.Fatalf("expected 2 keys, got %d", len(rl.counters))
	}

	stale := time.Now().Add(-2 * time.Minute)
	rl.counters["tg:stale"] = []time.Time{stale}
	rl.gcStale(time.Now())

	if _, ok := rl.counters["tg:stale"]; ok {
		t.Fatal("stale key should be removed")
	}
	if len(rl.counters) != 2 {
		t.Fatalf("expected 2 active keys after gc, got %d", len(rl.counters))
	}
}

func TestRateLimiterDeletesKeyWhenWindowEmpty(t *testing.T) {
	rl := newRateLimiter(1, 10*time.Millisecond)
	if !rl.allow("tg:1") {
		t.Fatal("first request should pass")
	}
	if rl.allow("tg:1") {
		t.Fatal("second request should be blocked within window")
	}

	time.Sleep(15 * time.Millisecond)
	if !rl.allow("tg:1") {
		t.Fatal("request after window should pass")
	}
	if len(rl.counters) != 1 {
		t.Fatalf("expected single active key, got %d", len(rl.counters))
	}
}

func TestRateLimiterEnforcesLimit(t *testing.T) {
	rl := newRateLimiter(2, time.Minute)
	if !rl.allow("tg:9") || !rl.allow("tg:9") {
		t.Fatal("first two requests should pass")
	}
	if rl.allow("tg:9") {
		t.Fatal("third request should be blocked")
	}
}
