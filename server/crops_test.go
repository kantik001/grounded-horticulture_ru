package main

import (
	"os"
	"path/filepath"
	"testing"
)

func cropsConfigForTest(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	candidates := []string{
		filepath.Join(wd, "..", "config", "crops.json"),
		filepath.Join(wd, "config", "crops.json"),
	}
	if env := os.Getenv("CROPS_CONFIG_PATH"); env != "" {
		candidates = append([]string{env}, candidates...)
	}
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	t.Skip("config/crops.json not found")
	return ""
}

func TestNormalizeCropID(t *testing.T) {
	t.Setenv("CROPS_CONFIG_PATH", cropsConfigForTest(t))
	cropCatalog = cropsFile{}
	if err := loadCropCatalog(); err != nil {
		t.Fatalf("loadCropCatalog: %v", err)
	}

	id, err := normalizeCropID("apple")
	if err != nil || id != "apple" {
		t.Fatalf("apple: id=%q err=%v", id, err)
	}

	_, err = normalizeCropID("unknown_crop_xyz")
	if err == nil {
		t.Fatal("expected error for unknown crop")
	}
}
