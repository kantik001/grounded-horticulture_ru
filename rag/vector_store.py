# ----------------------------------------------------------------------
# Векторное хранилище Chroma: статьи по культурам data/{crop_id}/*.txt
# ----------------------------------------------------------------------
import glob
import os
import sys


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


_ensure_utf8_stdout()

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from rag.bm25_store import (
    bm25_search,
    build_bm25_indexes,
    get_chunk_document,
    load_bm25_indexes,
    remove_bm25_index,
    reset_bm25_store,
    save_bm25_indexes,
)
from rag.chunking import assign_chunk_ids, chunk_id_for, diversify_fragments, split_documents
from rag.crops_config import list_crops, normalize_crop_id
from rag.embeddings import get_embeddings
from rag.hybrid import hybrid_enabled, rerank_for_category, rrf_merge
from rag.query_expand import expand_query
from rag.reranker import RERANK_TOP_N, rerank_documents
from rag.titles import get_pretty_title

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
PERSIST_DIR = os.path.join(_PROJECT_ROOT, "chroma_db")

_vector_store = None

# Сколько кандидатов взять из Chroma/BM25 перед rerank и дедупликацией по статьям.
FETCH_K = int(os.environ.get("RAG_FETCH_K", "16"))
BM25_FETCH_K = int(os.environ.get("RAG_BM25_FETCH_K", str(FETCH_K)))


# Сбрасывает in-memory кэш Chroma и BM25 перед принудительной переиндексацией.
def reset_vector_store():
    global _vector_store
    _vector_store = None
    reset_bm25_store()


# Мета-файлы папок data/, которые не являются базой знаний и не индексируются.
_SKIP_FILENAMES = {"readme.txt"}


def _is_indexable(file_path: str) -> bool:
    return os.path.basename(file_path).lower() not in _SKIP_FILENAMES


# Собирает .txt из data/{crop}/ и устаревшие data/*.txt в корне (как apple).
def load_all_documents():
    all_docs = []
    crops = list_crops().get("crops", {}).keys()

    for crop_id in crops:
        crop_dir = os.path.join(DATA_DIR, crop_id)
        if not os.path.isdir(crop_dir):
            continue
        for file_path in glob.glob(os.path.join(crop_dir, "*.txt")):
            if not _is_indexable(file_path):
                continue
            all_docs.extend(_load_file(crop_id, file_path))

    for file_path in glob.glob(os.path.join(DATA_DIR, "*.txt")):
        if not _is_indexable(file_path):
            continue
        all_docs.extend(_load_file("apple", file_path))

    return all_docs


# Читает один .txt и проставляет metadata: filename, crop_id, source_file.
def _load_file(crop_id: str, file_path: str):
    filename = os.path.basename(file_path)
    pretty_title = get_pretty_title(crop_id, filename, file_path=file_path)
    print(f"Загружаю [{crop_id}] {filename} -> {pretty_title}")
    loader = TextLoader(file_path, encoding="utf-8")
    docs = loader.load()
    for doc in docs:
        if doc.metadata is None:
            doc.metadata = {}
        doc.metadata["filename"] = pretty_title
        doc.metadata["crop_id"] = crop_id
        doc.metadata["source_file"] = filename
    return docs


# Полная переиндексация: split → embeddings + BM25 → сохранение в chroma_db/ и bm25_db/.
def create_vector_store():
    print("Создаю новую векторную базу (мультикультура)...")
    documents = load_all_documents()
    if not documents:
        print("Нет статей для индексации.")
        return None
    chunks = assign_chunk_ids(split_documents(documents))
    print(f"Фрагментов: {len(chunks)}")
    embeddings = get_embeddings()
    store = Chroma.from_documents(chunks, embeddings, persist_directory=PERSIST_DIR)
    print(f"База сохранена в {PERSIST_DIR}")
    save_bm25_indexes(build_bm25_indexes(chunks))
    return store


# Открывает существующую Chroma или создаёт новую (с учётом FORCE_RAG_REINDEX).
def load_vector_store(force_reindex: bool = False):
    global _vector_store
    if _vector_store is not None and not force_reindex:
        return _vector_store

    force = force_reindex or os.environ.get("FORCE_RAG_REINDEX", "").lower() in (
        "1",
        "true",
        "yes",
    )
    embeddings = get_embeddings()

    if force and os.path.isdir(PERSIST_DIR):
        import shutil

        print("FORCE_RAG_REINDEX: удаляю старую chroma_db")
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)
        remove_bm25_index()

    if os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR):
        _vector_store = Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)
        load_bm25_indexes()
    else:
        _vector_store = create_vector_store()
    return _vector_store


def _chunk_key(doc: Document) -> str:
    return doc.metadata.get("chunk_id") or chunk_id_for(doc)


def _collect_candidates(
    merged_ids: list[str],
    doc_map: dict[str, Document],
    crop_id: str,
    limit: int,
) -> list[Document]:
    candidates: list[Document] = []
    seen: set[str] = set()
    for cid in merged_ids:
        if cid in seen:
            continue
        seen.add(cid)
        doc = doc_map.get(cid) or get_chunk_document(cid, crop_id)
        if doc is None:
            continue
        candidates.append(doc)
        if len(candidates) >= limit:
            break
    return candidates


# Гибридный поиск: vector + BM25 (RRF) → reranker (по категории) → diversify top-k.
def search(query: str, crop_id: str, k: int = 8, category: str | None = None):
    crop_id = normalize_crop_id(crop_id)
    store = load_vector_store()
    if store is None:
        return []

    search_query = expand_query(query)
    fetch_k = max(k * 3, FETCH_K)
    vector_docs = store.similarity_search(
        search_query,
        k=fetch_k,
        filter={"crop_id": crop_id},
    )
    if not vector_docs:
        return []

    doc_map = {_chunk_key(d): d for d in vector_docs}
    vector_ids = list(doc_map.keys())

    use_hybrid = hybrid_enabled() and load_bm25_indexes() is not None
    if use_hybrid:
        bm25_ids = bm25_search(search_query, crop_id, max(fetch_k, BM25_FETCH_K))
        merged_ids = rrf_merge([vector_ids, bm25_ids])
    else:
        merged_ids = vector_ids

    use_rerank = rerank_for_category(category)
    candidate_limit = max(fetch_k, RERANK_TOP_N) if use_rerank else fetch_k
    candidates = _collect_candidates(merged_ids, doc_map, crop_id, candidate_limit)

    if use_rerank and len(candidates) > 1:
        candidates = rerank_documents(search_query, candidates)

    return diversify_fragments(candidates, limit=k)
