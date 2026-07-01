# Case study: grounded RAG для садоводства

**Проект:** doctor_gardens_ai (grounded-horticulture)  
**Репозиторий:** публичное портфолио — исходный код + демо-данные; полный корпус ПВЮР в git не входит ([DATA_LICENSE.md](../DATA_LICENSE.md)).  
**Домен:** яблоня, груша, слива — научные статьи (полный корпус локально); в git — `demo_hr` + `sample_*.txt`
**Стек:** Go (оркестрация, LLM, verify) · Python (hybrid RAG, CV) · Telegram Mini App · браузер (`X-API-Key`)

English version: [AGRO_CASE_STUDY_EN.md](./AGRO_CASE_STUDY_EN.md)

---

## Проблема

Садоводам и агрономам нужны **ответы со ссылкой на источник**, а не «галлюцинации» LLM: подвои, посадка на склонах, питание, защита. База — **~500 статей** на русском, много доменных синонимов (СК-4 / СК 4, марссониоз / *Marssonina*).

## Решение

Production-style ассистент:

1. **Hybrid retrieval** — Chroma (`multilingual-e5-small`) + BM25 + RRF  
2. **Cross-encoder reranker** — `BAAI/bge-reranker-base` на top-32  
3. **Chunking** — 650 токенов / 80 overlap, секции, приоритет «Кратко для садовода»  
4. **Query expansion** — `config/agro_glossary.json`  
5. **Grounded generation** — Go собирает промпт, вызывает LLM, **verify чисел** против контекста  
6. **Доступ** — Telegram `initData` или браузер `X-API-Key`  
7. **Прогрев** — модели при старте classifier (~3 мин один раз, ~6 с на вопрос после)

**Фото (CV):** пайплайн есть, но модель **не обучена на болезнях** (бета, `photo_beta_notice`). Для демо работодателю — **текстовый RAG**.

## Масштаб

| Метрика | Значение |
|---------|----------|
| Статьи (apple / pear / plum) | ~344 / ~42 / ~108 |
| Чанков в индексе | **~14 554** |
| Eval-вопросов | **68** (45 apple + 8 pear + 10 plum + 5 demo_hr) |

## Качество retrieval (регрессия)

```bash
python scripts/run_rag_eval.py --suite all
```

| Suite | Вопросов | Цель |
|-------|----------|------|
| apple | 45 | 100% pass |
| pear | 8 | 100% |
| plum | 10 | 100% |
| demo_hr | 5 | 100% |

Проверка: ожидаемые подстроки в retrieved context; out-of-scope — без «выдуманного» KB.

В CI: быстрые unit-тесты на каждый PR; полный eval — **вручную** (GitHub Actions → **RAG Eval**).

## Архитектура

```
Browser / Telegram → Go (auth, sessions, LLM, verify)
                         ↓ POST /rag/context
                    Python (hybrid search, rerank)
                         ↓
                    Chroma + BM25 (~14.5k chunks)
```

Платформа клонируется под другой домен (sandbox `demo_hr`) — см. [ARCHITECTURE.md](./ARCHITECTURE.md).

## Что демонстрирует (для резюме / статей)

- **Domain RAG не на 5 PDF** — реальный корпус журнала  
- **Измеримое качество** — JSONL eval, 68 вопросов, отчёты в `eval/results/`  
- **Production-паттерны** — Docker, Postgres, rate limit, `/metrics`, verify, admin reindex  
- **Полный стек** — Go + Python microservices, Telegram Web App  

### Буллеты для резюме (копировать)

- Hybrid RAG: Chroma + BM25 + RRF + bge-reranker на **~14.5k** чанков (**~500** статей)  
- Go-оркестрация: auth (Telegram + API key), сессии Postgres, verify ответов, rate limit  
- Eval suite **68** вопросов, retrieval regression **100%** (переподтверждать после смен KB)  
- CI: Go + pytest (**45** tests) + Docker build; RAG eval — отдельный workflow  
- Domain pack: apple/pear/plum + sandbox `demo_hr` для переносимости платформы  

## Демо для собеседования (15 мин)

1. **Прогреть** `docker compose up` заранее (первый RAG-запрос долгий).  
2. Показать **2–3 вопроса** по яблоне (подвой, марссониоз, склон).  
3. Обратить внимание на **фрагменты из статей** и **дисклеймер**.  
4. Кратко: hybrid search, eval, verify — без углубления в CV.  
5. Опционально: `admin.html` → feedback с полем `rag` для 👎.

## Запуск локально

```bash
cp .env.example .env   # LLM_API_KEY, API_KEYS, HF_TOKEN
docker compose up -d --build
python scripts/run_rag_eval.py --suite all
```

Браузер: `http://localhost` (API key из `API_KEYS`) или Telegram Mini App.

## Связанные документы

- [PILOT_READINESS_AUDIT.md](./PILOT_READINESS_AUDIT.md) — чеклист перед пилотом  
- [IMPROVEMENT_BACKLOG.md](./IMPROVEMENT_BACKLOG.md) — что осталось в бэклоге  
- [knowledge-base/github-ci.yml.md](./knowledge-base/github-ci.yml.md) — CI и RAG Eval  
- [eval/README.md](../eval/README.md) — формат eval JSONL  

---

*Ответы ассистента носят справочный характер; агрономические решения требуют очного осмотра и соблюдения инструкций к препаратам.*
