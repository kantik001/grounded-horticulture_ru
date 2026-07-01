# RAG: BM25 hybrid + reranker

**Модули:** `rag/chunking.py`, `rag/bm25_store.py`, `rag/hybrid.py`, `rag/reranker.py`  
**Оркестрация:** `rag/vector_store.py` → `search()`  
**Хранилище BM25:** `bm25_db/` (в Docker — volume `bm25_data`)

См. также: [rag-vector_store.md](./rag-vector_store.md), [rag-retrieval.md](./rag-retrieval.md).

---

## Зачем

Чистый **vector search** (e5 embeddings) хорошо ловит смысл, но слабее на:

- кодах подвоев (**М9**, **СК-4**, **ПК СК-1**);
- редких терминах и фамилиях;
- точных названиях сортов в вопросе.

**BM25 hybrid** добавляет keyword-поиск и объединяет результаты с векторным через **RRF** (Reciprocal Rank Fusion).  
**Cross-encoder reranker** пересортировывает пары «вопрос ↔ фрагмент» перед отбором финальных 8 чанков.

---

## Пайплайн поиска

```mermaid
flowchart LR
    Q[Вопрос] --> V[Chroma vector FETCH_K]
    Q --> B[BM25 FETCH_K]
    V --> RRF[RRF по chunk_id]
    B --> RRF
    RRF --> CE[Cross-encoder до RERANK_TOP_N]
    CE --> D[diversify max 2/статья]
    D --> K[top 8 в контекст LLM]
```

| Этап | По умолчанию | Env |
|------|--------------|-----|
| Кандидаты vector | 24 | `RAG_FETCH_K` |
| Кандидаты BM25 | 24 | `RAG_BM25_FETCH_K` |
| RRF constant | 60 | `RAG_RRF_K` |
| Пул для rerank | 32 | `RAG_RERANK_TOP_N` |
| Финальный контекст | 8 | жёстко в `retrieval.py` |
| Max чанков с одной статьи | 2 | `RAG_MAX_CHUNKS_PER_SOURCE` |

---

## `rag/chunking.py`

Общее чанкование для Chroma и BM25 (одинаковые фрагменты):

- `chunk_size=650`, `chunk_overlap=80`;
- приоритетные разделители: «Кратко для садовода», «Практические выводы», таблицы;
- `chunk_id` в metadata: `{crop_id}:{source_file}:{md5(content)[:12]}`.

Без стабильного `chunk_id` RRF не сможет объединить vector и BM25.

---

## `rag/bm25_store.py`

- Индекс **по культурам** (`crop_id`), те же чанки, что в Chroma.
- При `create_vector_store()` → `save_bm25_indexes()` в `bm25_db/index.pkl` + `meta.json`.
- При `FORCE_RAG_REINDEX` папка `bm25_db/` удаляется вместе с `chroma_db/`.
- Токенизация: `\w+` с Unicode (русский + латиница + цифры).

Если BM25-индекса нет (старый деплой без reindex) — `search()` работает **vector-only**, reranker при этом может работать.

---

## `rag/hybrid.py`

- `tokenize()` — нормализация текста для BM25.
- `rrf_merge()` — объединение ранжированных списков `chunk_id`.
- `hybrid_enabled()` / `rerank_enabled()` — флаги из env.

---

## `rag/reranker.py`

- Модель по умолчанию: **`BAAI/bge-reranker-base`** (multilingual).
- Lazy-load при первом запросе (как e5 embeddings).
- При ошибке загрузки — поиск без пересортировки, без падения API.

Первый запрос после старта classifier может занять **дополнительные секунды** (скачивание reranker с HuggingFace).

---

## Переменные окружения

```env
RAG_HYBRID_ENABLED=true
RAG_RERANK_ENABLED=true
RAG_FETCH_K=24
RAG_BM25_FETCH_K=24
RAG_RRF_K=60
RAG_RERANK_TOP_N=32
RAG_RERANK_MODEL=BAAI/bge-reranker-base
RAG_MAX_CHUNKS_PER_SOURCE=2
```

См. `.env.example`.

---

## Docker

В `docker-compose.yml` для classifier:

- `chroma_data:/app/chroma_db`
- `bm25_data:/app/bm25_db`

После reindex **оба** индекса должны быть в volumes. Иначе после `restart` без reindex hybrid отключится (нет BM25 на диске).

Команда:

```bash
make docker-reindex-apply
```

---

## Зависимости

- `rank-bm25` — BM25Okapi (`cv/requirements.txt`, `tests/requirements-test.txt`);
- `sentence-transformers` — CrossEncoder (уже был для embeddings stack).

---

## Тесты

`tests/test_hybrid_search.py` — токенизация, RRF, BM25 на мини-корпусе (без Chroma/HF).

`tests/test_rag_retrieval.py` — категории вопросов, `diversify_fragments`.

---

## Краткий итог

Hybrid + reranker — **второй уровень** качества retrieval поверх e5 + chunking. Включается после переиндексации; настраивается через env без правки кода.
