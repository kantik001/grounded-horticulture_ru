package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

var photoTemplateCatalog map[string]string

func loadPhotoTemplates() error {
	path := photoTemplatesConfigPath()
	body, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read photo templates %s: %w", path, err)
	}
	if err := json.Unmarshal(body, &photoTemplateCatalog); err != nil {
		return fmt.Errorf("parse photo templates: %w", err)
	}
	return nil
}

func photoTemplatesConfigPath() string {
	if p := os.Getenv("PHOTO_TEMPLATES_PATH"); p != "" {
		return p
	}
	for _, candidate := range []string{
		"/config/photo_templates.json",
		filepath.Join("..", "config", "photo_templates.json"),
		filepath.Join("config", "photo_templates.json"),
	} {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return filepath.Join("config", "photo_templates.json")
}
