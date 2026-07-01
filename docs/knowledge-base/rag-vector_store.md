# Разбор: `rag/vector_store.py`

**Исходный файл:** `rag/vector_store.py`  
**Данные:** `data/{crop_id}/*.txt`  
**Хранилища:** `chroma_db/` (вектор), `bm25_db/` (keyword) — в Docker volumes `chroma_data`, `bm25_data`  
**Кто вызывает:** `rag/retrieval.py` → `search()`, админка → `load_vector_store(force_reindex=True)`

**Подробнее про hybrid:** [rag-hybrid-search.md](./rag-hybrid-search.md)

---

## Зачем этот файл

Ядро **RAG retrieval**: превратить `.txt` статьи в индексы и искать релевантные фрагменты по вопросу.

LLM здесь **нет** — только индексация и поиск (vector + BM25 + rerank).

---

## Ключевые пути

| Переменная | Путь |
|------------|------|
| `DATA_DIR` | `{корень}/data` |
| `PERSIST_DIR` | `{корень}/chroma_db` |
| BM25 | `{корень}/bm25_db` (`rag/bm25_store.py`) |

---

## Пайплайн индексации

```mermaid
flowchart LR
    A[data/crop/*.txt] --> B[TextLoader + metadata]
    B --> C[chunking.py split 650/80]
    C --> D[chunk_id в metadata]
    D --> E[E5Embeddings passage:]
    E --> F[Chroma chroma_db]
    D --> G[BM25Okapi bm25_db]
```

### `load_all_documents()`

- Обходит все культуры из `crops.json`;
- для каждой — `data/{crop_id}/*.txt`;
- **legacy:** файлы прямо в `data/*.txt` считаются яблоней (`apple`).

Корпус (оценка): **~344** apple, **~42** pear, **~108** plum (после чистки miscategorized в `data/plum/`).

### `_load_file(crop_id, file_path)`

К каждому документу LangChain добавляет metadata:

| Поле | Пример |
|------|--------|
| `filename` | красивое имя из `article_titles.json` или имя файла |
| `crop_id` | `apple` |
| `source_file` | `article1.txt` |

### `create_vector_store()`

1. Загрузить все документы.
2. **Chunking** (`rag/chunking.py`): 650/80, секционные разделители.
3. **chunk_id** в metadata каждого чанка.
4. **Embeddings:** `intfloat/multilingual-e5-small` с префиксами `passage:` / `query:` (`rag/embeddings.py`).
5. **Chroma** → `chroma_db/`.
6. **BM25** → `bm25_db/` (`rag/bm25_store.py`).

Если статей нет → `None`, поиск пустой.

---

## Загрузка и переиндексация: `load_vector_store`

| Ситуация | Поведение |
|----------|-----------|
| Кэш `_vector_store` в памяти | вернуть его |
| `force_reindex=True` или `FORCE_RAG_REINDEX=true` | удалить `chroma_db` и `bm25_db`, пересоздать |
| `chroma_db` не пустая | открыть Chroma + загрузить BM25 с диска |
| иначе | `create_vector_store()` |

`reset_vector_store()` — сброс RAM-кэша Chroma и BM25 (перед admin reindex).

### Admin reindex (`api/app.py`)

```
reset_vector_store() → load_vector_store(force_reindex=True)
```

После upload новых `.txt` в `data/` — обязателен reindex, иначе индексы не видят файлы.

---

## Поиск: `search(query, crop_id, k=8)`

Не только `similarity_search` — полный pipeline:

1. **Vector:** `similarity_search`, `k=FETCH_K`, filter `crop_id`.
2. **BM25** (если `RAG_HYBRID_ENABLED` и есть `bm25_db`): top `BM25_FETCH_K`.
3. **RRF** по `chunk_id` из обоих списков.
4. **Reranker** (если `RAG_RERANK_ENABLED`): cross-encoder на пуле до `RERANK_TOP_N`.
5. **diversify_fragments:** max 2 чанка с одной статьи → **8** в контекст.

Первый вызов может **долго** тянуть e5 и reranker с HuggingFace.

---

## `article_titles.json`

Опционально: человекочитаемые названия для metadata `filename` (для логов и контекста LLM «Текст из статьи '…'»). Пользователю в чате названия статей не показываются (политика на Go).

---

## Docker

- `./data:/app/data:ro` — статьи;
- `chroma_data:/app/chroma_db` — векторный индекс;
- `bm25_data:/app/bm25_db` — BM25 индекс;
- `FORCE_RAG_REINDEX` — полная пересборка при старте.

После reindex в Docker: **`docker compose restart classifier`** (сброс in-memory кэша).

---

## Частые вопросы

### Добавил `article4.txt`, RAG не видит

Нужен **reindex** (`make docker-reindex-apply` или admin).

### Папки `chroma_db/` / `bm25_db/` в git?

Нет — генерируются локально / в Docker volumes (`.gitignore`).

### Hybrid не работает после restart

Проверьте volume `bm25_data` и что после смены `data/` был reindex.

### Qdrant в roadmap

При росте объёма возможна замена Chroma; интерфейс для `retrieval.py` тогда поменяется внутри `vector_store.py`.

---

## Что читать дальше

| Тема | Файл |
|------|------|
| BM25, RRF, reranker | [rag-hybrid-search.md](./rag-hybrid-search.md) |
| Сборка контекста для Go | [rag-retrieval.md](./rag-retrieval.md) |
| Культуры | [rag-crops_config.md](./rag-crops_config.md) |
| HTTP reindex | [python-api.md](./python-api.md) |

---

## Краткий итог

`vector_store.py` — **индексация** (Chroma + BM25) и **гибридный поиск** с reranker и diversify. Chunking вынесен в `rag/chunking.py`.
