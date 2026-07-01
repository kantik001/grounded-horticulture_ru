package main

import (
	"log"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
)

// reloadRuntimeConfig перечитывает JSON-конфиги без перезапуска процесса.
func reloadRuntimeConfig() error {
	if err := loadCropCatalog(); err != nil {
		return err
	}
	if err := loadPromptCatalog(); err != nil {
		return err
	}
	if err := loadOnboardingConfig(); err != nil {
		return err
	}
	if err := loadPhotoTemplates(); err != nil {
		return err
	}
	if err := loadBrandingConfig(); err != nil {
		return err
	}
	log.Printf("Config reloaded: crops=%d", len(cropCatalog.Crops))
	return nil
}

// startConfigReloadWatcher: SIGHUP и опциональный опрос по интервалу (CONFIG_RELOAD_INTERVAL_SEC).
func startConfigReloadWatcher() {
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGHUP)
	go func() {
		for range sigCh {
			if err := reloadRuntimeConfig(); err != nil {
				log.Printf("SIGHUP config reload failed: %v", err)
			}
		}
	}()

	sec, _ := strconv.Atoi(os.Getenv("CONFIG_RELOAD_INTERVAL_SEC"))
	if sec <= 0 {
		return
	}
	go func() {
		ticker := time.NewTicker(time.Duration(sec) * time.Second)
		defer ticker.Stop()
		for range ticker.C {
			if err := reloadRuntimeConfig(); err != nil {
				log.Printf("periodic config reload failed: %v", err)
			}
		}
	}()
}
