#!/usr/bin/env python3
"""Переиндексация Chroma после добавления статей или смены структуры data/{crop}/."""

import os
import sys

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _root)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["FORCE_RAG_REINDEX"] = "true"

from rag.vector_store import create_vector_store  # noqa: E402

if __name__ == "__main__":
    try:
        create_vector_store()
        print("Переиндексация RAG завершена.")
    except Exception as e:
        err = str(e).lower()
        if "hnsw" in err or "compaction" in err:
            print(
                "Ошибка Chroma на Windows при большом индексе. "
                "Используйте: make docker-reindex && docker compose restart classifier",
                file=sys.stderr,
            )
        raise
