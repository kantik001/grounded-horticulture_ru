# Архитектура: универсальная платформа grounded LLM

Репозиторий **doctor_gardens_ai** сейчас — **первый продуктовый пакет (агробот)** на общем каркасе.  
Цель: клонировать репозиторий, заменить domain pack и развернуть ассистента для другой отрасли (HR, образование, регламенты, KSA и т.д.) **без переписывания ядра**.

См. также: [DEPLOY.md](./DEPLOY.md), [ROADMAP.md](./ROADMAP.md), [knowledge-base/README.md](./knowledge-base/README.md).

---

## Три слоя

```
┌─────────────────────────────────────────────────────────┐
│  Platform core (копируем в новый проект как есть)       │
│  Go orchestration · Python RAG · verify · admin · CI    │
└───────────────────────────┬─────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
   Domain pack A      Domain pack B     Domain pack C
   (agro / apple)     (demo_hr)         (будущий клиент)
   data + config      data + config      data + config
```

| Слой | Папки / код | Меняется при клоне? |
|------|-------------|-------------------|
| **Core** | `server/` (кроме агро-формулировок в комментариях), `api/`, `rag/`, `migrations/`, `scripts/reindex_rag.py`, `scripts/run_rag_eval.py`, `docker-compose.yml`, `tests/`, `eval/` (механизм) | Нет |
| **Domain pack** | `data/{domain_id}/`, `config/crops.json`, `prompts.json`, `few_shot.json`, `question_categories.json`, `onboarding.json`, `photo_templates.json`, `cv_class_labels.json`, `config/branding.json`, тексты `webapp/` | **Да** |
| **Optional modules** | CV (`cv/`, `cv_enabled`), Telegram Web App | По задаче |

**`crop_id` в API** — идентификатор **домена знаний** (workspace). В новых проектах можно мысленно называть `domain_id`; переименование в коде — позже, с alias.

---

## Поток данных (текст)

1. Клиент → Go `POST /message` (сессия + auth).
2. Go → Python `POST /rag/context` (`question`, `crop_id`).
3. Python hybrid search (Chroma + BM25 + reranker) возвращает фрагменты + few-shot из `config/`.
4. Go собирает промпт → LLM → `cleanRAGAnswer` → `verifyRAGAnswer` → дисклеймер.
5. Ответ и метаданные → Postgres; структурированный лог RAG (`rag_log.go`).

Фото: `classifyAndRecommend` → Python CV (если `cv_enabled`) → LLM или `photo_templates.json`.

---

## Platform core (файлы)

| Компонент | Файлы | Роль |
|-----------|-------|------|
| API / auth | `middleware.go`, `auth_telegram.go`, `routes.go` | Telegram, CORS, rate limit, маршруты |
| Чат | `message_handlers.go`, `session_handlers.go`, `postgres_store.go` | Сессии, история, фото |
| RAG + LLM | `rag_chat.go`, `rag_verify.go`, `llm.go` | Retrieval orchestration, guardrails |
| Качество | `rag_log.go`, `eval/`, `scripts/run_rag_eval.py` | Наблюдаемость и регрессии |
| Конфиг runtime | `crops.go`, `config_reload.go`, `photo_templates.go`, `onboarding.go`, `branding.go` | JSON без rebuild |
| Admin | `admin.go` | Upload `.txt`, reindex |
| Python | `api/app.py`, `rag/*`, `cv/registry.py` | ML-сервис |

---

## Domain pack (агро сейчас)

| Файл | Содержание |
|------|------------|
| `data/apple/*.txt` | База знаний RAG |
| `config/crops.json` | `apple`, `demo_hr`, … + `cv_enabled` / `rag_enabled` |
| `config/prompts.json` | Системные промпты по домену |
| `config/few_shot.json` | Примеры тона ответа |
| `config/question_categories.json` | Ключевые слова для `classify_question` (few-shot / rerank) |
| `config/onboarding.json` | Чипы вопросов в UI |
| `config/photo_templates.json` | Шаблоны без LLM |
| `config/cv_class_labels.json` | Метки CV (только agro) |
| `config/branding.json` | Заголовок, дисклеймер UI |
| `webapp/` | Канал Telegram (можно заменить) |

**Sandbox `demo_hr`:** RAG без CV — проверка, что платформа не привязана к агро.

---

## Правило при разработке

Перед merge: **«Это core или domain pack?»**

- Универсальная логика → config / общий Go / `rag/`.
- Тексты про яблоню, болезни, «садовод» → `data/`, `config/`, `branding.json`.

---

## Чеклист: новый проект на базе платформы

1. `git clone` → новое имя репозитория.
2. Заменить `config/branding.json`, тексты `webapp` (или свой фронт).
3. Очистить / заменить `data/*`, добавить документы заказчика.
4. Обновить `crops.json` (домены), `prompts.json`, `few_shot.json`, `question_categories.json`, `onboarding.json`.
5. `cv_enabled: false` если CV не нужен.
6. `python scripts/reindex_rag.py` (или admin reindex).
7. Скопировать `eval/rag_*_baseline.jsonl` → свои вопросы; `python scripts/run_rag_eval.py`.
8. Deploy по [DEPLOY.md](./DEPLOY.md); пилот + feedback.

Оценка: **2–5 дней** на MVP при готовых документах и без CV.

---

## Дорожная карта платформы (после агро-пилота)

| Приоритет | Задача |
|-----------|--------|
| Сейчас | Eval, RAG-логи, ARCHITECTURE, sandbox `demo_hr` |
| Далее | `domain_id` alias в API, tenant в БД |
| По заказчику | i18n (AR/EN), SSO, ingest PDF/SharePoint |
| Опционально | Qdrant, multi-tenant SaaS |

Агробот остаётся **референсным пакетом** и полигоном качества, не единственным продуктом платформы.
