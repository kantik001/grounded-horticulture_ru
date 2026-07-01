package main

import (
	"net/http"
	"strconv"
	"strings"
	"sync/atomic"

	"github.com/gin-gonic/gin"
)

var (
	metricHTTPRequests atomic.Uint64
	metricHTTP2xx      atomic.Uint64
	metricHTTP4xx      atomic.Uint64
	metricHTTP5xx      atomic.Uint64
	metricLLMErrors    atomic.Uint64
	metricRAGRequests  atomic.Uint64
	metricRAGVerifyOK  atomic.Uint64
	metricRAGVerifyFail atomic.Uint64
	metricRAGSoftFail  atomic.Uint64
	metricRAGRetrievalMs atomic.Uint64
	metricRAGLLMMs       atomic.Uint64
)

func recordHTTPStatus(status int) {
	metricHTTPRequests.Add(1)
	switch {
	case status >= 500:
		metricHTTP5xx.Add(1)
	case status >= 400:
		metricHTTP4xx.Add(1)
	default:
		metricHTTP2xx.Add(1)
	}
}

func recordLLMError() {
	metricLLMErrors.Add(1)
}

func recordRAGTraceMetrics(t RAGTrace) {
	metricRAGRequests.Add(1)
	if t.VerifyPass {
		metricRAGVerifyOK.Add(1)
	} else {
		metricRAGVerifyFail.Add(1)
	}
	if t.SoftFail {
		metricRAGSoftFail.Add(1)
	}
	if t.RetrievalMs > 0 {
		metricRAGRetrievalMs.Add(uint64(t.RetrievalMs))
	}
	if t.LLMMs > 0 {
		metricRAGLLMMs.Add(uint64(t.LLMMs))
	}
}

func metricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.URL.Path == "/metrics" {
			c.Next()
			return
		}
		c.Next()
		recordHTTPStatus(c.Writer.Status())
	}
}

// handleMetrics exposes Prometheus text exposition (scrape from internal network).
func handleMetrics(c *gin.Context) {
	var b strings.Builder
	writeCounter := func(name, help string, value uint64) {
		b.WriteString("# HELP ")
		b.WriteString(name)
		b.WriteString(" ")
		b.WriteString(help)
		b.WriteString("\n# TYPE ")
		b.WriteString(name)
		b.WriteString(" counter\n")
		b.WriteString(name)
		b.WriteString(" ")
		b.WriteString(strconv.FormatUint(value, 10))
		b.WriteString("\n")
	}

	writeCounter("garden_http_requests_total", "Total HTTP requests handled by Go server", metricHTTPRequests.Load())
	writeCounter("garden_http_responses_2xx_total", "HTTP 2xx responses", metricHTTP2xx.Load())
	writeCounter("garden_http_responses_4xx_total", "HTTP 4xx responses", metricHTTP4xx.Load())
	writeCounter("garden_http_responses_5xx_total", "HTTP 5xx responses", metricHTTP5xx.Load())
	writeCounter("garden_llm_errors_total", "LLM API call failures", metricLLMErrors.Load())
	writeCounter("garden_rag_requests_total", "Completed RAG answer attempts", metricRAGRequests.Load())
	writeCounter("garden_rag_verify_pass_total", "RAG answers passing number verification", metricRAGVerifyOK.Load())
	writeCounter("garden_rag_verify_fail_total", "RAG answers failing number verification", metricRAGVerifyFail.Load())
	writeCounter("garden_rag_soft_fail_total", "RAG soft failures (no context or verify fail)", metricRAGSoftFail.Load())
	writeCounter("garden_rag_retrieval_ms_total", "Sum of RAG retrieval latency milliseconds", metricRAGRetrievalMs.Load())
	writeCounter("garden_rag_llm_ms_total", "Sum of RAG LLM latency milliseconds", metricRAGLLMMs.Load())

	c.Data(http.StatusOK, "text/plain; version=0.0.4; charset=utf-8", []byte(b.String()))
}
