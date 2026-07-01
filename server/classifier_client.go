package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
)

// ClassificationResult — ответ Python /classify.
type ClassificationResult struct {
	Success        bool                  `json:"success"`
	Prediction     string                `json:"prediction"`
	Confidence     float64               `json:"confidence"`
	TopPredictions []PredictionCandidate `json:"top_predictions"`
	Error          string                `json:"error,omitempty"`
}

// PredictionCandidate — один вариант из top-k классификации.
type PredictionCandidate struct {
	Label      string  `json:"label"`
	Confidence float64 `json:"confidence"`
}

// POST multipart с фото и crop_id в Python-сервис классификации.
func sendToClassifier(imageData []byte, cropID string) (*ClassificationResult, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile("image", "upload.jpg")
	if err != nil {
		return nil, fmt.Errorf("failed to create form file: %v", err)
	}

	if _, err = part.Write(imageData); err != nil {
		return nil, fmt.Errorf("failed to write image  %v", err)
	}
	_ = writer.WriteField("crop_id", cropID)

	if err = writer.Close(); err != nil {
		return nil, fmt.Errorf("failed to close writer: %v", err)
	}

	req, err := http.NewRequest("POST", config.PythonServiceURL, body)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := classifierHTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request to classifier: %v", err)
	}
	defer resp.Body.Close()

	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read classifier response: %v", err)
	}

	var result ClassificationResult
	if err = json.Unmarshal(responseBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse classifier response: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		if result.Error != "" {
			return &result, fmt.Errorf("classifier HTTP %d: %s", resp.StatusCode, result.Error)
		}
		return &result, fmt.Errorf("classifier HTTP %d: %s", resp.StatusCode, string(responseBody))
	}
	return &result, nil
}
