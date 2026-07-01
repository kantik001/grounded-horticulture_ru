# План: Eval RAG (3B) и логи RAG (3C)

**Статус:** **реализовано** (2026-07-01) — eval-наборы **68 вопросов**, `run_rag_eval.py`, логи `[RAG]`, связка feedback↔RAG в `GET /admin/feedback`, `/metrics`.  
**Связь:** [../ROADMAP.md](../ROADMAP.md), [server-rag_chat.md](./server-rag_chat.md), [metrics-and-alerts.md](./metrics-and-alerts.md)

---

## Зачем это нужно

1. **Воспроизводимый eval** — набор вопросов + прогон после reindex / смены промпта.
2. **Наблюдаемость** — почему ответ плохой (чанки, verify, 👎, latency).

---

## Фаза 3B — Eval-набор

### Файлы (реализовано)

| Файл | Вопросов | `crop_id` |
|------|----------|-----------|
| `eval/rag_apple_baseline.jsonl` | **45** | apple |
| `eval/rag_pear_baseline.jsonl` | 8 | pear |
| `eval/rag_plum_baseline.jsonl` | 10 | plum |
| `eval/rag_demo_hr_baseline.jsonl` | 5 | demo_hr |
| **Итого** | **68** | |

Формат строки JSON:

```json
{
  "crop_id": "apple",
  "question": "Какие признаки парши на листьях?",
  "expect_contains": ["пятн", "парша"],
  "expect_context": true,
  "expect_out_of_scope": false,
  "category": "disease"
}
```

- `expect_contains` — подстроки в **контексте** retrieval (стемминг RU).
- `expect_contains_any` — достаточно одной из синонимов.
- `expect_out_of_scope: true` — вопрос вне KB.

### Метрики прогона

| Метрика | Как считать |
|---------|-------------|
| **retrieval pass** | `expect_contains` / out-of-scope в контексте |
| **verify pass rate** | доля ответов без ⚠️ verify (режим `--full` через Go) |
| **manual score 1–5** | выборочно 10 ответов (рекомендуется перед демо/пилотом) |

### Когда гонять

- после **reindex** с новыми статьями;
- после смены **`LLM_MODEL`** или `prompts.json`;
- перед **пилотом**, **демо для работодателя**, merge крупных PR по RAG.

### Запуск

```bash
# Локально (classifier на :5000)
python scripts/run_rag_eval.py --suite all --timeout 300

# Или in-process (без HTTP)
python scripts/run_rag_eval.py --suite apple --in-process --fast

# CI: GitHub Actions → workflow RAG Eval (ручной)
```

Отчёты: `eval/results/<timestamp>_<suite>.json`.  
См. [eval/README.md](../../eval/README.md).

**Целевой порог:** 100% retrieval pass (последний зафиксированный прогон — 68/68; переподтверждать после смен KB).

**В плане:** автоматический порог pass rate в CI на каждый PR (отклонено из-за времени; см. [github-ci.yml.md](./github-ci.yml.md)).

---

## Фаза 3C — Логи и аналитика RAG

### Stdout (`rag_log.go`)

На каждый текстовый ответ: `crop_id`, `session_id`, `fragments`, `verify_pass`, `verify_reason`, `soft_fail`.  
**Не логируется:** полный промпт и тело LLM.

### Prometheus (`server/metrics.go`)

`GET /metrics` — счётчики HTTP, LLM errors, RAG requests, verify pass/fail, latency sums.  
См. [metrics-and-alerts.md](./metrics-and-alerts.md).

### Feedback + RAG в админке

`GET /admin/feedback?rating=-1&limit=50` — для каждой оценки поле **`rag`** (если есть `rag_answer` в `analytics_events`):

- `category`, `fragments`, `verify_pass`, `retrieval_ms`, `llm_ms`

Разбор 👎: админка → негативные оценки → метрики RAG по сообщению.

### Postgres (опционально на будущее)

Отдельная таблица `rag_query_log` — не реализована; сейчас достаточно stdout + metrics + analytics_events.

---

## Чеклист «готово к пилоту / демо» (качество)

- [x] Корпус ПВЮР (~344 apple, ~42 pear, ~108 plum), reindex Chroma+BM25
- [x] Eval **68** вопросов, скрипт прогона
- [x] Retrieval baseline **100%** (переподтвердить на живом индексе)
- [ ] Verify pass rate известен (выборочно `--full` или ручной чат)
- [x] Логи `[RAG]` + `/metrics`
- [x] Feedback ↔ RAG в админ-отчёте
- [ ] 5–10 ручных вопросов перед демо работодателю

---

## Краткий итог

**3B Eval** — 68 эталонных вопросов, регрессия retrieval. **3C** — логи, метрики, связка с feedback. Полный eval в CI — только вручную (**RAG Eval** workflow).
