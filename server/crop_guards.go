package main

import "fmt"

// requireRAGEnabled проверяет флаг rag_enabled для культуры.
func requireRAGEnabled(cropID string) error {
	info, ok := cropInfo(cropID)
	if !ok {
		return fmt.Errorf("неизвестная культура: %s", cropID)
	}
	if !info.RAGEnabled {
		return fmt.Errorf("для культуры «%s» текстовый помощник пока недоступен", info.NameRU)
	}
	return nil
}

// requireCVEnabled проверяет флаг cv_enabled для культуры.
func requireCVEnabled(cropID string) error {
	info, ok := cropInfo(cropID)
	if !ok {
		return fmt.Errorf("неизвестная культура: %s", cropID)
	}
	if !info.CVEnabled {
		return fmt.Errorf("для культуры «%s» распознавание по фото пока недоступно", info.NameRU)
	}
	return nil
}
