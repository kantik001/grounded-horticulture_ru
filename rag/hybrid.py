"""RRF-слияние векторного и BM25 ранжирования."""

import os
import re
from typing import FrozenSet, Iterable, List, Optional

RRF_K = int(os.environ.get("RAG_RRF_K", "60"))

_DEFAULT_RERANK_CATEGORIES = frozenset(
    {"rootstock", "disease", "variety", "fertilizer", "relief"}
)


def env_flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


def hybrid_enabled() -> bool:
    return env_flag("RAG_HYBRID_ENABLED", "true")


def rerank_enabled() -> bool:
    return env_flag("RAG_RERANK_ENABLED", "true")


def rerank_categories() -> FrozenSet[str]:
    raw = os.environ.get("RAG_RERANK_CATEGORIES", "")
    if raw.strip():
        return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())
    return _DEFAULT_RERANK_CATEGORIES


def rerank_for_category(category: Optional[str]) -> bool:
    """Reranker только для «сложных» категорий (коды, дозы, сорта); general/irrigation — быстрее."""
    if not rerank_enabled():
        return False
    if env_flag("RAG_RERANK_ALWAYS", "false"):
        return True
    if not env_flag("RAG_RERANK_CONDITIONAL", "true"):
        return True
    cat = (category or "general").strip().lower()
    return cat in rerank_categories()


_TOKEN_RE = re.compile(r"[\w\d]+", re.UNICODE)


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def rrf_merge(rankings: Iterable[Iterable[str]], k: int = RRF_K) -> List[str]:
    """Reciprocal Rank Fusion: объединяет несколько ранжированных списков chunk_id."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return [cid for cid, _ in sorted(scores.items(), key=lambda item: -item[1])]
