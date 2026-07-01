#!/usr/bin/env python3
"""Скачивает HF-модели RAG (e5 + reranker) в HF_HOME. Используется при docker build."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)


def _apply_hf_token() -> None:
    token = (os.environ.get("HF_TOKEN") or "").strip()
    if token:
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token


def download_models() -> None:
    hf_home = os.environ.get("HF_HOME") or os.path.join(_ROOT, "hf_cache")
    os.makedirs(hf_home, exist_ok=True)
    os.environ["HF_HOME"] = hf_home
    _apply_hf_token()

    from huggingface_hub import snapshot_download
    from sentence_transformers import CrossEncoder

    from rag.embeddings import E5_MODEL
    from rag.reranker import RERANK_MODEL

    token = os.environ.get("HF_TOKEN") or None
    print(f"HF bake: HF_HOME={hf_home}")
    print(f"HF bake: e5 {E5_MODEL}")
    snapshot_download(repo_id=E5_MODEL, token=token)
    print(f"HF bake: reranker {RERANK_MODEL}")
    CrossEncoder(RERANK_MODEL, max_length=512)
    print("HF bake: готово")


def main() -> int:
    try:
        download_models()
        return 0
    except Exception as exc:
        print(f"HF bake: ошибка — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
