package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"
)

// CropInfo описывает одну культуру в продукте.
type CropInfo struct {
	ID         string `json:"-"`
	NameRU     string `json:"name_ru"`
	Emoji      string `json:"emoji"`
	CVEnabled  bool   `json:"cv_enabled"`
	RAGEnabled bool   `json:"rag_enabled"`
	UIHidden   bool   `json:"ui_hidden,omitempty"`
}

type cropsFile struct {
	DefaultCrop string              `json:"default_crop"`
	Crops       map[string]CropInfo `json:"crops"`
}

var cropCatalog cropsFile

// Загружает config/crops.json в память (cropCatalog).
func loadCropCatalog() error {
	path := cropsConfigPath()
	body, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read crops config %s: %w", path, err)
	}
	if err := json.Unmarshal(body, &cropCatalog); err != nil {
		return fmt.Errorf("parse crops config: %w", err)
	}
	for id, c := range cropCatalog.Crops {
		c.ID = id
		cropCatalog.Crops[id] = c
	}
	if cropCatalog.DefaultCrop == "" {
		cropCatalog.DefaultCrop = "apple"
	}
	return nil
}

// Возвращает путь к crops.json (env или поиск по типовым каталогам).
func cropsConfigPath() string {
	if p := os.Getenv("CROPS_CONFIG_PATH"); p != "" {
		return p
	}
	for _, candidate := range []string{
		"/config/crops.json",
		filepath.Join("..", "config", "crops.json"),
		filepath.Join("config", "crops.json"),
	} {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return filepath.Join("config", "crops.json")
}

// Нормализует crop_id и проверяет, что культура есть в каталоге.
func normalizeCropID(raw string) (string, error) {
	id := strings.TrimSpace(strings.ToLower(raw))
	if id == "" {
		id = cropCatalog.DefaultCrop
	}
	if _, ok := cropCatalog.Crops[id]; !ok {
		return "", fmt.Errorf("неизвестная культура: %s", raw)
	}
	return id, nil
}

// Возвращает культуру по умолчанию из каталога.
func defaultCropID() string {
	if cropCatalog.DefaultCrop != "" {
		return cropCatalog.DefaultCrop
	}
	return "apple"
}

// Возвращает описание культуры по id.
func cropInfo(cropID string) (CropInfo, bool) {
	c, ok := cropCatalog.Crops[cropID]
	return c, ok
}

type cropPrompts struct {
	RAGSystem      string `json:"rag_system"`
	RAGTaskIntro   string `json:"rag_task_intro"`
	PhotoSystem    string `json:"photo_system"`
	PhotoUserIntro string `json:"photo_user_intro"`
	PhotoUserBody  string `json:"photo_user_body"`
}

var promptCatalog map[string]cropPrompts

// Загружает config/prompts.json (системные промпты RAG и фото).
func loadPromptCatalog() error {
	path := promptsConfigPath()
	body, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read prompts config %s: %w", path, err)
	}
	if err := json.Unmarshal(body, &promptCatalog); err != nil {
		return fmt.Errorf("parse prompts config: %w", err)
	}
	return nil
}

// Возвращает путь к prompts.json.
func promptsConfigPath() string {
	if p := os.Getenv("PROMPTS_CONFIG_PATH"); p != "" {
		return p
	}
	for _, candidate := range []string{
		"/config/prompts.json",
		filepath.Join("..", "config", "prompts.json"),
		filepath.Join("config", "prompts.json"),
	} {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return filepath.Join("config", "prompts.json")
}

// Промпты для культуры; при отсутствии — из default_crop или встроенные строки.
func promptsForCrop(cropID string) cropPrompts {
	if p, ok := promptCatalog[cropID]; ok {
		return p
	}
	if p, ok := promptCatalog[defaultCropID()]; ok {
		return p
	}
	return cropPrompts{
		RAGSystem:      "Ты — грамотный агроном. Отвечай на русском.",
		RAGTaskIntro:   "Ты — грамотный агроном. Отвечай строго на основе контекста.",
		PhotoSystem:    "Ты — опытный садовод. Дай практичные советы на русском.",
		PhotoUserIntro: "Ты — опытный садовод.",
		PhotoUserBody:  "Результат анализа фото:\n- Класс: %s\n- Уверенность: %.2f%%\n- Топ-3: %v\n\nДай рекомендации по уходу на русском.",
	}
}

// GET /crops: список культур и флаги cv_enabled / rag_enabled.
func handleListCrops(c *gin.Context) {
	list := make([]gin.H, 0, len(cropCatalog.Crops))
	for id, cinfo := range cropCatalog.Crops {
		if cinfo.UIHidden {
			continue
		}
		list = append(list, gin.H{
			"id":          id,
			"name_ru":     cinfo.NameRU,
			"emoji":       cinfo.Emoji,
			"cv_enabled":  cinfo.CVEnabled,
			"rag_enabled": cinfo.RAGEnabled,
		})
	}
	c.JSON(http.StatusOK, gin.H{
		"success":      true,
		"default_crop": cropCatalog.DefaultCrop,
		"crops":        list,
	})
}
