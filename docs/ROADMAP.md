# Дорожная карта doctor_gardens_ai

Актуальный план развития продукта. Отмечайте выполненное по мере работы.

## Аудит пилота

- [x] Чеклист готовности: [`docs/PILOT_READINESS_AUDIT.md`](PILOT_READINESS_AUDIT.md) (обновлён 2026-07-01)
- [x] Case study для портфолио: [`docs/AGRO_CASE_STUDY_EN.md`](AGRO_CASE_STUDY_EN.md), [`docs/AGRO_CASE_STUDY_RU.md`](AGRO_CASE_STUDY_RU.md)

## Фаза 0 — Подготовка
- [x] `.env.example`
- [x] README (актуальный flow)
- [x] `docs/ROADMAP.md`
- [x] `docs/ARCHITECTURE.md` — ядро платформы vs domain pack
- [x] `docs/DEPLOY.md` — развёртывание и клонирование

## Фаза 1 — Фундамент
### 1A Безопасность
- [x] Telegram `initData` validation (Go)
- [x] Web App передаёт `X-Telegram-Init-Data`
- [x] Защита API (кроме `/health`)
- [x] CORS whitelist
- [x] Rate limit (in-memory)
- [ ] Структурированные логи

### 1B Персистентность
- [x] PostgreSQL в docker-compose
- [x] Миграции `users`, `sessions`, `messages`
- [x] Store в Go, убрать in-memory сессии
- [x] Фото на volume, token в БД (не base64)

### 1C Прочее
- [x] Дисклеймер в UI
- [x] Не логировать тело LLM

## Фаза 2 — Мультикультура
- [x] `crop_id` в API и UI
- [x] `data/{crop}/`, RAG metadata
- [x] Модели CV по культуре (registry, apple)
- [x] Промпты/few-shot по культуре (config/)

## Фаза 3 — Качество RAG
- [x] База статей журнала ПВЮР (`data/apple/` ~344, `data/pear/` ~42, `data/plum/` ~108)
- [x] Чистка miscategorized статей в `data/plum/` (75 файлов удалено)
- [x] E5 префиксы, chunking 650/80, diversify top-k
- [x] BM25 hybrid + cross-encoder reranker (`rag/bm25_store.py`, `rag/reranker.py`)
- [x] Скрипт переиндексации (`scripts/reindex_rag.py`, admin reindex) — Chroma + BM25
- [x] Feedback 👍/👎
- [x] Sandbox-домен `demo_hr` (RAG без CV) — проверка универсальности
- [ ] Qdrant (при росте объёма)

### 3B — Eval
- [x] Набор **45 вопросов** по яблоне (`eval/rag_apple_baseline.jsonl`) + pear/plum/demo_hr (**68** всего)
- [x] `scripts/run_rag_eval.py` + `eval/results/`, `make eval-retrieval`
- [x] RAG eval в GitHub Actions — **ручной** workflow [`.github/workflows/rag-eval.yml`](../.github/workflows/rag-eval.yml) (не на каждый PR — скорость CI)
- [ ] Manual score 1–5 выборочно после пилота / перед демо работодателю
- Документация: [`docs/knowledge-base/quality-eval-and-rag-logs.md`](knowledge-base/quality-eval-and-rag-logs.md), [`eval/README.md`](../eval/README.md)

### 3C — Логи RAG
- [x] Структурированный лог `[RAG]` в Go (`rag_log.go`): crop_id, session_id, fragments, verify
- [x] Связка с **feedback** 👍/👎 в админ-отчёте (`GET /admin/feedback` → поле `rag`)
- [x] Без полного тела LLM в логах (политика 1C)

### Платформа (параллельно агро)
- [x] `config/branding.json` + `GET /branding` + загрузка в Web App
- [x] [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/DEPLOY.md`](DEPLOY.md)

## Фаза 4 — Vision
- [ ] Датасет и обучение `apple_classifier.pth`
- [ ] Метрики, порог confidence
- [ ] RAG + CV связка

## Фаза 5–10
См. обсуждение в чате: UX, админка, монетизация, тесты/CI, пилот, агрономы, IoT.

### Сессия 5 (UX + admin)
- [x] Онбординг (`config/onboarding.json`)
- [x] Feedback и analytics в Postgres
- [x] Admin upload + RAG reindex

### Сессия 6 (тесты + CI)
- [x] Go unit-тесты (RAG verify, crops, admin)
- [x] Python pytest (verifier, crops_config)
- [x] Smoke-скрипты
- [x] GitHub Actions CI + ручной RAG Eval workflow
