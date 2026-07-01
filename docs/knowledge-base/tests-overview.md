# Разбор: папка `tests/` (Python) и тесты проекта

**Папка:** `tests/` — **только Python** (pytest)  
**Связанные тесты Go:** `server/*_test.go` (отдельная папка, тот же смысл «проверки»)  
**CI:** job `python-test` и `go-test` в [github-ci.yml.md](./github-ci.yml.md)

---

## Зачем тесты в этом проекте

Проверяют **логику без Docker, без LLM, без Chroma, без Telegram**:

- верно ли парсятся числа в ответе RAG;
- корректно ли читается `config/crops.json`;
- RRF, BM25, токенизация, категории вопросов, diversify чанков.

Это **unit-тесты** — быстрые, дешёвые, гоняются на каждый push в CI.

Не заменяют [smoke](scripts-overview.md), [eval](../../eval/README.md) и ручной чат в webapp.

---

## Файлы в `tests/`

| Файл | Назначение |
|------|------------|
| `conftest.py` | Общая настройка pytest: корень проекта в `PYTHONPATH` |
| `test_verifier.py` | Тесты `rag/verifier.py` |
| `test_crops_config.py` | Тесты `rag/crops_config.py` |
| `test_hybrid_search.py` | BM25, RRF, токенизация (`rag/hybrid.py`, `rag/bm25_store.py`) |
| `test_rag_retrieval.py` | `classify_question`, `diversify_fragments` |
| `test_question_categories.py` | `rag/question_categories.py`, override через `QUESTION_CATEGORIES_CONFIG_PATH` |
| `test_verify_contract.py` | контракт verify vs `tests/fixtures/rag_verify_contract.json` |
| `test_rag_eval_match.py` | стем-матчинг `expect_contains` в eval |
| `test_embeddings.py` | e5 префиксы `query:` / `passage:` |
| `test_vector_titles.py` | заголовки статей из metadata |
| `requirements-test.txt` | pytest + langchain-core + rank-bm25 (без PyTorch/Chroma) |

Папки `tests/__pycache__/` и `.pytest_cache/` — автогенерация, в git не нужны.

---

## `conftest.py`

```python
_ROOT = .../doctor_gardens_ai
sys.path.insert(0, _ROOT)
```

Чтобы `from rag.verifier import ...` работало при запуске из любой директории.

**Фикстур с БД нет** — тесты чисто функциональные.

---

## `requirements-test.txt`

```
pytest>=8.0.0
langchain-core>=0.3.0
rank-bm25>=0.2.2,<0.3
```

Намеренно **нет** `torch`, `langchain-chroma`, `flask`, `sentence-transformers` — CI и локальный `pytest` остаются лёгкими.

---

## `test_verifier.py` — что проверяет

Модуль: [rag-verifier.md](./rag-verifier.md) (в проде дубль на Go в `rag_chat.go`).

### `test_extract_numbers_decimal_comma`

- Вход: `"304,7 кг"`
- Ожидание: `[304.7]` — запятая как десятичный разделитель.

### `test_verify_passes_with_matching_number`

- Фрагмент: «Среднее 77.»
- Ответ: «Среднее 77.» + дисклеймер
- `verify_answer` → **успех** (число есть в контексте).

### `test_verify_fails_on_hallucinated_number`

- Фрагмент: без цифр
- Ответ: «Рентабельность 72%»
- `verify_answer` → **провал**, в reason есть «72» или «не найдены».

### `test_strip_source_attribution`

- Убирает строку `Источник: "Журнал"`, оставляет «Факт».

---

## `test_hybrid_search.py`

- `tokenize` — русский текст и коды (`СК-4`, `М9`);
- `rrf_merge` — объединение двух ранжированных списков;
- BM25 на мини-корпусе (3 документа — иначе IDF нулевой на 2 чанках).

---

## `test_rag_retrieval.py`

- категории: `rootstock`, `disease`, `relief`;
- `diversify_fragments` — лимит чанков с одной статьи, порядок релевантности.

---

## `test_crops_config.py` — что проверяет

Модуль: [rag-crops_config.md](./rag-crops_config.md).

### Фикстура `crops_config_path` (autouse)

Перед **каждым** тестом:

1. `monkeypatch.setenv("CROPS_CONFIG_PATH", .../config/crops.json)`
2. Сброс `rag.crops_config._CONFIG = None` — перечитать JSON заново.

### `test_normalize_crop_id_apple`

- `"apple"` и `" Apple "` → `"apple"`.

### `test_normalize_crop_id_unknown`

- `"banana_xyz"` → `ValueError` с текстом «Неизвестная».

### `test_list_crops_has_apple`

- `default_crop == "apple"`;
- в списке есть `apple`, `rag_enabled is True`.

---

## Как запустить локально

Из **корня** проекта:

```powershell
pip install -r tests/requirements-test.txt
$env:CROPS_CONFIG_PATH = "config/crops.json"
pytest tests/ -v --tb=short
```

Или:

```bash
make test-py
```

Ожидание: **45 passed** (verifier, crops, hybrid, retrieval, question_categories, verify_contract, eval match, embeddings, titles, query_expand, debug_log).

---

## Что **не** покрыто папкой `tests/`

| Не тестируется | Почему |
|----------------|--------|
| Chroma / e5 embeddings end-to-end | тяжело, медленно |
| Cross-encoder reranker | нужен HF + torch |
| `retrieval.py` + живой индекс | eval-набор вместо unit |
| LLM API | платно, недетерминировано |
| Flask `api/app.py` | нет HTTP-тестов |
| PostgreSQL | нет testcontainers |

Регрессии retrieval: `python scripts/run_rag_eval.py --suite all` (см. [quality-eval-and-rag-logs.md](./quality-eval-and-rag-logs.md)).

---

## Go-тесты (не в `tests/`, но часть той же стратегии)

Лежат в **`server/`**, запуск: `go test ./...` или `make test-go`.

| Файл | Что проверяет |
|------|----------------|
| `rag_chat_test.go` | числа, verify, дисклеймер, очистка ответа |
| `verify_contract_test.go` | контракт verify vs `tests/fixtures/rag_verify_contract.json` |
| `crops_test.go` | `normalizeCropID`, каталог культур |
| `admin_test.go` | `safeFilename`, админ-хелперы |
| `auth_telegram_test.go`, `auth_combined_test.go` | Telegram initData, API key |
| `api_keys_test.go` | заголовок `X-API-Key` |
| `ratelimit_test.go` | лимит запросов, `gcStale` |
| `feedback_report_test.go` | `GET /admin/feedback` + поле `rag` |
| `rag_log_test.go`, `llm_test.go` | вспомогательная логика |

---

## Краткий итог

`tests/` — быстрые unit-тесты RAG-логики и конфига. Hybrid BM25 — без Chroma; полный retrieval — через **`scripts/run_rag_eval.py`** локально или workflow **RAG Eval** в GitHub Actions.
