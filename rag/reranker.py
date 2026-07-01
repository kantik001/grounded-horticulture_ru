"""Cross-encoder reranker для финальной пересортировки кандидатов."""

from __future__ import annotations

import os
from typing import List, Optional

from langchain_core.documents import Document

RERANK_MODEL = os.environ.get("RAG_RERANK_MODEL", "BAAI/bge-reranker-base")
RERANK_TOP_N = int(os.environ.get("RAG_RERANK_TOP_N", "16"))

_cross_encoder = None
_load_failed = False


def _get_cross_encoder():
    global _cross_encoder, _load_failed
    if _load_failed:
        return None
    if _cross_encoder is not None:
        return _cross_encoder
    try:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(RERANK_MODEL, max_length=512)
        print(f"Reranker загружен: {RERANK_MODEL}")
        return _cross_encoder
    except Exception as exc:
        _load_failed = True
        print(f"Reranker недоступен ({exc}), поиск без пересортировки")
        return None


def rerank_documents(
    query: str,
    documents: List[Document],
    limit: Optional[int] = None,
) -> List[Document]:
    if not documents:
        return []
    model = _get_cross_encoder()
    if model is None:
        return documents[: limit or len(documents)]

    pairs = [(query, doc.page_content) for doc in documents]
    scores = model.predict(pairs)
    ranked = sorted(range(len(documents)), key=lambda i: float(scores[i]), reverse=True)
    out = [documents[i] for i in ranked]
    if limit is not None:
        out = out[:limit]
    return out
