# Метрики и базовые алерты

Go-сервер отдаёт **Prometheus text exposition** на:

- `GET /metrics`
- `GET /api/metrics`

Эндпоинт **публичный** (без auth) — на продакшене ограничьте доступ сетью (firewall / internal scrape only).

---

## Метрики

| Имя | Тип | Описание |
|-----|-----|----------|
| `garden_http_requests_total` | counter | Все HTTP-запросы |
| `garden_http_responses_2xx_total` | counter | Ответы 2xx |
| `garden_http_responses_4xx_total` | counter | Ответы 4xx |
| `garden_http_responses_5xx_total` | counter | Ответы 5xx |
| `garden_llm_errors_total` | counter | Ошибки вызова LLM API |
| `garden_rag_requests_total` | counter | Завершённые RAG-ответы (по `logRAGTrace`) |
| `garden_rag_verify_pass_total` | counter | Ответы, прошедшие verify чисел |
| `garden_rag_verify_fail_total` | counter | Ответы с провалом verify |
| `garden_rag_soft_fail_total` | counter | Soft fail (нет контекста / verify) |
| `garden_rag_retrieval_ms_total` | counter | Сумма latency retrieval (мс) |
| `garden_rag_llm_ms_total` | counter | Сумма latency LLM (мс) |

Средняя latency retrieval (PromQL):

```promql
rate(garden_rag_retrieval_ms_total[5m]) / rate(garden_rag_requests_total[5m])
```

---

## Пример scrape (Prometheus)

```yaml
scrape_configs:
  - job_name: garden-server
    metrics_path: /metrics
    static_configs:
      - targets: ["server:8080"]
```

---

## Пример алертов (Alertmanager)

```yaml
groups:
  - name: garden-server
    rules:
      - alert: GardenHigh5xxRate
        expr: rate(garden_http_responses_5xx_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Garden server 5xx rate elevated"

      - alert: GardenLLMErrors
        expr: increase(garden_llm_errors_total[10m]) > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "LLM API errors in garden server"

      - alert: GardenRAGVerifyFailRate
        expr: |
          rate(garden_rag_verify_fail_total[15m])
          / rate(garden_rag_requests_total[15m]) > 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High RAG verify failure rate"

      - alert: GardenSlowRAGRetrieval
        expr: |
          rate(garden_rag_retrieval_ms_total[5m])
          / rate(garden_rag_requests_total[5m]) > 15000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "RAG retrieval avg > 15s"
```

Пороги подстройте под пилотную нагрузку.

---

## Feedback + RAG в админке

`GET /admin/feedback` возвращает поле `rag` у каждой оценки (если есть событие `rag_answer` в `analytics_events` с тем же `message_id`): category, fragments, verify_pass, latency.

---

## Связанные документы

- [quality-eval-and-rag-logs.md](./quality-eval-and-rag-logs.md)
- [server-admin-and-ux-api.md](./server-admin-and-ux-api.md)
