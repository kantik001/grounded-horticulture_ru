# Бэклог улучшений doctor_gardens_ai

Создан по итогам аудита кода и документации.

**Принцип остановки:** пилот текстового RAG запускается после закрытия P0.
P1–P3 — пост-пилотный бэклог, не блокируют запуск. Признак перебора: задача не
влияет на решение «запускать пилот или нет» — значит, она за границей MVP.

Статусы: 🔲 не начато · 🔄 в работе · ✅ готово

См. также: [PILOT_READINESS_AUDIT.md](./PILOT_READINESS_AUDIT.md), [ROADMAP.md](./ROADMAP.md), [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## P0 — обязательно (дёшево, снижает риск / разблокирует пилот)

| # | Статус | Задача | Ветка | Файлы | Критерий готовности |
|---|--------|--------|-------|-------|---------------------|
| 1 | ✅ | Timing-safe сравнение секретов | `feat/post-audit-p0` | `server/admin.go`, `api/app.py` | `subtle.ConstantTimeCompare`/`hmac.Equal` (Go), `hmac.compare_digest` (Py); тесты зелёные |
| 2 | ✅ | Актуализировать аудит готовности | `feat/post-audit-p0` + синхр. 2026-07-01 | `docs/PILOT_READINESS_AUDIT.md` | Метрики/статусы соответствуют P0–P2 и 45 pytest |
| 3 | ✅ | Решение по фото-ветке (CV): помечено «бета» | `feat/post-audit-p0` | `config/branding.json`, `server/branding.go`, `server/classify_flow.go`, `webapp/*` | Дисклеймер добавляется к каждой рекомендации по фото + виден в UI при прикреплении. Обучение модели — пост-пилотная задача (нет датасета) |

## P1 — качество и чистота платформы

| # | Статус | Задача | Ветка | Детали |
|---|--------|--------|-------|--------|
| 4 | ✅ | Вынести доменные ключевые слова из ядра | `feat/p1-platform-quality` | `config/question_categories.json`, `rag/question_categories.py` | `classify_question` читает keywords из domain pack |
| 5 | ✅ | Контрактный тест verify (Go ↔ Python) | `feat/p1-platform-quality` | `tests/fixtures/rag_verify_contract.json`, `verify_contract_test.go`, `test_verify_contract.py` | 6 общих кейсов, оба прогона зелёные |
| 6 | ✅ | Документировать ограничения верификации | `feat/p1-platform-quality` | `docs/knowledge-base/rag-verify-limits.md` | Ограничения эвристики и расхождения Go/Python |
| 7 | 🔲 | OCR-починка PDF-текстов | `fix/ocr-corpus` | Отложено: нет пайплайна/датасета OCR в репо; влияет на recall по «битым» словам |

## P2 — эксплуатация и наблюдаемость

| # | Статус | Задача | Ветка | Детали |
|---|--------|--------|-------|--------|
| 8 | ✅ | GC устаревших ключей в rate-limiter | `feat/p2-ops-observability` | `gcStale` + удаление пустых ключей; тесты `ratelimit_test.go` |
| 9 | ✅ | RAG eval в CI | `feat/p2-ops-observability` | PR: быстрый `docker-build` (как раньше). Полный eval — workflow **RAG Eval** (`workflow_dispatch`) |
| 10 | ✅ | `/metrics` + базовые алерты | `feat/p2-ops-observability` | `server/metrics.go`, `docs/knowledge-base/metrics-and-alerts.md` |
| 11 | ✅ | Связка feedback ↔ RAG-логи в админ-отчёте | `feat/p2-ops-observability` | `GET /admin/feedback` → поле `rag` из `analytics_events` |
| 12 | ✅ | Документировать бэкапы volumes | `feat/p2-ops-observability` | `docs/BACKUPS.md` |

## P3 — тесты и устойчивость

| # | Статус | Задача | Ветка | Детали |
|---|--------|--------|-------|--------|
| 13 | 🔲 | HTTP-тесты Go-хендлеров | `test/http-handlers` | `httptest` для `/message`, auth, rate limit |
| 14 | 🔲 | Интеграционные тесты Postgres | `test/pg-integration` | testcontainers для `postgres_store.go` |
| 15 | 🔲 | Глобальный лимит размера JSON-тела | `fix/body-size-limit` | `MaxBytesReader` на не-multipart запросы |

---

## Определение «достаточно» (Definition of Done для пилота)

Останавливаемся, когда закрыт P0-чеклист из [PILOT_READINESS_AUDIT.md](./PILOT_READINESS_AUDIT.md)
плюс пункты 1–3 выше.
