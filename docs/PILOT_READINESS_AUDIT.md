# Аудит готовности к пилоту

**Дата создания:** 2026-06-05 · **Обновлён:** 2026-07-01 (финальная синхронизация документации)  
**Продукт:** doctor_gardens_ai (Telegram Web App, агробот)  
**Цель пилота:** текстовый RAG по статьям ПВЮР + опционально фото (яблоня, бета)

Статусы: ✅ готово · ⚠️ частично / риск · ❌ блокер · 🔲 не начато

> **Обновление 2026-07-01.** Закрыты P0–P2 из [IMPROVEMENT_BACKLOG.md](./IMPROVEMENT_BACKLOG.md):
> timing-safe секреты, фото «бета», категории в `config/`, контракт verify, `/metrics`, feedback↔RAG,
> бэкапы, GC rate-limiter. Юнит-тесты: Go `ok`, Python **45 passed**.
> Eval retrieval — **100%** (68 вопросов); **переподтвердить** прогоном перед пилотом/демо (см. P0).

---

## Резюме

| Направление | Готовность | Комментарий |
|-------------|------------|-------------|
| **Текст RAG (яблоня)** | **~90%** | eval 45/45, hybrid+reranker, ~344 статьи |
| **Текст RAG (груша/слива)** | **~85%** | pear 8/8, plum 10/10; слива очищена от misc |
| **Фото CV** | **~25%** | Нет обученных `.pth` в репо — ImageNet fallback + UI «бета» |
| **Инфра / Docker** | **~90%** | Compose, volumes Chroma+BM25, CI (быстрый PR) |
| **Безопасность прод** | **~60%** | Нужны prod-секреты, `TELEGRAM_AUTH_DISABLED=false` |
| **Наблюдаемость / аналитика** | **~75%** | `/metrics`, feedback+RAG в админке, `[RAG]` логи |
| **Демо для трудоустройства** | **~85%** | Текстовый RAG + case study; см. [AGRO_CASE_STUDY_RU.md](./AGRO_CASE_STUDY_RU.md) |

**Вердикт:** пилот **текстового чата** (яблоня / груша / слива) и **портфолио-демо** — после чеклиста P0. Пилот **«фото → болезнь»** — только с дисклеймером «бета», не как основной сценарий.

---

## P0 — обязательно перед пилотом / живым демо

| # | Пункт | Статус | Действие |
|---|--------|--------|----------|
| 1 | `LLM_API_KEY` задан и стабильная модель | ⚠️ | Для пилота/демо — платная/стабильная RU-модель |
| 2 | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_AUTH_DISABLED=false` | ❌ | В dev часто `true`; на проде обязательно выключить |
| 3 | `ADMIN_PASSWORD`, `ADMIN_SECRET`, `POSTGRES_PASSWORD` — сильные | ⚠️ | Заменить dev-значения перед публичным URL |
| 4 | RAG переиндексирован (Chroma + BM25) в Docker volumes | ✅ | 14 554 фрагментов; reindex при **остановленном** classifier |
| 5 | `HF_TOKEN` в `.env` для classifier | ✅ | Ускоряет загрузку e5 + `BAAI/bge-reranker-base` |
| 6 | Eval retrieval ≥ целевого порога | ✅ | **68/68 (100%)**; переподтвердить перед показом |
| 7 | `docker compose up` — все 4 сервиса healthy | ✅ | postgres, classifier, server, webapp |
| 8 | Smoke: `make smoke` или `scripts/smoke.ps1` | 🔲 | Прогнать после деплоя |
| 9 | Дисклеймер в UI и в ответах RAG | ✅ | `branding.json`, verifier, Go disclaimer |
| 10 | CORS / домен Telegram Web App | ⚠️ | Добавить prod URL в `CORS_ALLOWED_ORIGINS` |
| 11 | Прогреть classifier перед демо | 🔲 | Первый RAG-запрос ~1–3 мин (загрузка моделей) |

### Команды P0 (после смены `data/` или RAG-кода)

```powershell
docker compose -p union_ai_apple stop classifier
docker compose -p union_ai_apple run --rm -e FORCE_RAG_REINDEX=true classifier python scripts/reindex_rag.py
docker compose -p union_ai_apple start classifier
python scripts/run_rag_eval.py --suite all --timeout 300
```

**В CI:** полный eval — вручную: GitHub Actions → workflow **RAG Eval** (не на каждый PR).

---

## P1 — качество RAG (желательно до/в первую неделю пилота)

| # | Пункт | Статус | Детали |
|---|--------|--------|--------|
| 11 | Корпус apple ~344 статьи | ✅ | Журнал ПВЮР |
| 12 | Корпус plum очищен (misc удалены) | ✅ | 75 misc удалено → ~108 статей; 10 mixed остались |
| 13 | E5 префиксы `query:`/`passage:` | ✅ | `rag/embeddings.py` |
| 14 | Chunking 650/80 + секции | ✅ | `rag/chunking.py` |
| 15 | BM25 hybrid + RRF | ✅ | `rag/bm25_store.py`, `rag/hybrid.py` |
| 16 | Cross-encoder reranker | ✅ | `BAAI/bge-reranker-base`; первый запрос ~1–3 мин с HF_TOKEN |
| 17 | Diversity top-k (max 2/статья, k=8) | ✅ | `vector_store.diversify_fragments` |
| 18 | Few-shot по категориям | ✅ | rootstock, disease, relief, … |
| 19 | Категории вопросов в domain pack | ✅ | `config/question_categories.json` |
| 20 | Контракт verify Go ↔ Python | ✅ | `tests/fixtures/rag_verify_contract.json` |
| 21 | OCR-починка PDF-текстов | 🔲 | Отложено; влияет на recall по «битым» словам |
| 22 | Ручная выборочная оценка 10–20 ответов LLM | 🔲 | `--full` eval или чат с реальными садоводами |

---

## P2 — фото / CV (не блокер текстового пилота)

| # | Пункт | Статус | Детали |
|---|--------|--------|--------|
| 23 | `apple_classifier.pth` обучен на болезнях | ❌ | В репо нет `.pth`; CV = ImageNet backbone |
| 24 | Датасет фото болезней яблони | 🔲 | `cv/train_classifier.py`, структура `dataset/train/` |
| 25 | Порог confidence + шаблоны без LLM | ⚠️ | `photo_templates.json` есть; порог в roadmap |
| 26 | `cv_enabled: false` для pear/plum | ✅ | Только apple в UI для фото |
| 27 | Пометка фото «бета» + дисклеймер | ✅ | `photo_beta_notice` в `branding.json`, `classify_flow.go`, UI |

**Решение (2026-07-01):** фото-ветка включена с явным дисклеймером. Обучение `apple_classifier.pth` — пост-пилот (нужен датасет).

---

## P3 — платформа и эксплуатация

| # | Пункт | Статус | Детали |
|---|--------|--------|--------|
| 28 | PostgreSQL сессии и история | ✅ | migrations 001–003 |
| 29 | Rate limit + GC устаревших ключей | ✅ | in-memory, 30 req/min; `gcStale` в `ratelimit.go` |
| 30 | Admin: upload `.txt` + reindex | ✅ | `admin.html`, `/admin/reindex` |
| 31 | Feedback 👍/👎 в БД | ✅ | analytics в Postgres |
| 32 | RAG structured logs `[RAG]` | ✅ | `server/rag_log.go` |
| 33 | Связка feedback ↔ RAG в админ-отчёте | ✅ | `GET /admin/feedback` → поле `rag` |
| 34 | CI: pytest + go test + docker-build | ✅ | `.github/workflows/ci.yml` (~10–15 мин) |
| 35 | RAG eval в CI | ✅ | **Ручной** workflow `.github/workflows/rag-eval.yml` |
| 36 | Backup volumes | ✅ | [BACKUPS.md](./BACKUPS.md) |
| 37 | Мониторинг `/metrics` + алерты | ✅ | `server/metrics.go`, [metrics-and-alerts.md](./knowledge-base/metrics-and-alerts.md) |
| 38 | HTTP-тесты хендлеров, testcontainers | 🔲 | P3 в IMPROVEMENT_BACKLOG |

---

## P4 — продукт и UX

| # | Пункт | Статус | Детали |
|---|--------|--------|--------|
| 39 | Онбординг-чипы вопросов | ✅ | `config/onboarding.json` |
| 40 | Выбор культуры в UI | ✅ | apple / pear / plum |
| 41 | `demo_hr` скрыт (`ui_hidden`) | ✅ | Sandbox платформы |
| 42 | README / DEPLOY / knowledge-base актуальны | ✅ | Обновлено 2026-07-01 |
| 43 | Case study для портфолио | ✅ | [AGRO_CASE_STUDY_EN.md](./AGRO_CASE_STUDY_EN.md), [AGRO_CASE_STUDY_RU.md](./AGRO_CASE_STUDY_RU.md) |
| 44 | Пилотная группа 5–10 пользователей | 🔲 | Организационно |
| 45 | Сбор обратной связи раз в неделю | 🔲 | Процесс |

---

## Метрики на момент аудита

| Метрика | Значение |
|---------|----------|
| Статьи RAG | ~344 apple, ~42 pear, ~108 plum |
| Фрагментов в индексе | 14 554 |
| Eval retrieval (all) | **68/68 (100%)** — переподтвердить перед пилотом |
| apple / pear / plum / demo_hr | 45/45 · 8/8 · 10/10 · 5/5 |
| Unit-тесты Python | **45 passed** (2026-07-01) |
| Unit-тесты Go | `go test ./...` — ok (2026-07-01) |
| Misc plum (аудит) | 0 misc, 10 mixed |

---

## Минимальный чеклист «демо / пилот завтра»

- [ ] `.env` prod: `TELEGRAM_AUTH_DISABLED=false`, сильные пароли (или API key для browser-only демо)
- [ ] `CORS_ALLOWED_ORIGINS` с URL Web App
- [ ] `HF_TOKEN` в `.env` (не в git)
- [ ] Reindex + restart classifier (volumes не пустые)
- [ ] `python scripts/run_rag_eval.py --suite all` или Actions → **RAG Eval**
- [ ] `make smoke`
- [ ] Прогреть classifier (первый вопрос не на демо)
- [ ] 5–10 тестовых вопросов вручную (текст RAG; фото — только с оговоркой «бета»)

---

## Связанные документы

- [IMPROVEMENT_BACKLOG.md](./IMPROVEMENT_BACKLOG.md)
- [ROADMAP.md](./ROADMAP.md)
- [DEPLOY.md](./DEPLOY.md)
- [BACKUPS.md](./BACKUPS.md)
- [AGRO_CASE_STUDY_RU.md](./AGRO_CASE_STUDY_RU.md)
- [eval/README.md](../eval/README.md)
- [knowledge-base/rag-hybrid-search.md](./knowledge-base/rag-hybrid-search.md)
- [knowledge-base/metrics-and-alerts.md](./knowledge-base/metrics-and-alerts.md)

---

*Файл обновлять после каждого крупного изменения KB, RAG-пайплайна, CI или перед релизом пилота.*
