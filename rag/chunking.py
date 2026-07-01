"""Чанкование статей для Chroma и BM25 (одинаковые фрагменты)."""

import hashlib
import os
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 650
CHUNK_OVERLAP = 80

_SECTION_SEPARATORS = [
    "\n\nКратко для садовода:",
    "\n\nПрактические выводы:",
    "\n\nЦифры из текста и таблиц",
    "\n\n---\n\n",
    "\n\n",
    "\n",
    " ",
    "",
]


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_SECTION_SEPARATORS,
    )


def split_documents(documents: list[Document]) -> list[Document]:
    return get_text_splitter().split_documents(documents)


def chunk_id_for(doc: Document) -> str:
    crop = doc.metadata.get("crop_id", "")
    src = doc.metadata.get("source_file") or doc.metadata.get("filename") or ""
    digest = hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()[:12]
    return f"{crop}:{src}:{digest}"


def assign_chunk_ids(chunks: list[Document]) -> list[Document]:
    seen: dict[str, int] = {}
    for doc in chunks:
        base = chunk_id_for(doc)
        n = seen.get(base, 0)
        seen[base] = n + 1
        cid = base if n == 0 else f"{base}:{n}"
        if doc.metadata is None:
            doc.metadata = {}
        doc.metadata["chunk_id"] = cid
    return chunks


def slug_from_chunk_id(chunk_id: str) -> str:
    return re.sub(r"[^\w\-:.]", "_", chunk_id)


MAX_CHUNKS_PER_SOURCE = int(os.environ.get("RAG_MAX_CHUNKS_PER_SOURCE", "2"))


def diversify_fragments(docs, limit: int, max_per_source: int = MAX_CHUNKS_PER_SOURCE):
    """Не более max_per_source чанков с одной статьи; сохраняет порядок релевантности."""
    if max_per_source <= 0:
        return docs[:limit]
    picked = []
    counts: dict[str, int] = {}
    for doc in docs:
        src = doc.metadata.get("source_file") or doc.metadata.get("filename") or ""
        if counts.get(src, 0) >= max_per_source:
            continue
        picked.append(doc)
        counts[src] = counts.get(src, 0) + 1
        if len(picked) >= limit:
            break
    return picked
