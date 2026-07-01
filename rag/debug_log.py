"""Условный debug-лог RAG (hot path). Включение: RAG_DEBUG=true."""

from __future__ import annotations

import os


def rag_debug_enabled() -> bool:
    return os.environ.get("RAG_DEBUG", "").lower() in ("1", "true", "yes", "on")


def rag_debug(msg: str) -> None:
    if rag_debug_enabled():
        print(msg, flush=True)
