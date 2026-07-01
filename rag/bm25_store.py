"""BM25-индекс по культурам: строится вместе с Chroma при переиндексации."""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from rag.chunking import assign_chunk_ids, split_documents
from rag.hybrid import tokenize

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BM25_DIR = os.path.join(_PROJECT_ROOT, "bm25_db")
BM25_INDEX_PATH = os.path.join(BM25_DIR, "index.pkl")
BM25_VERSION = 1

_indexes: Dict[str, "CropBM25Index"] | None = None


@dataclass
class CropBM25Index:
    chunk_ids: List[str]
    records: Dict[str, Document]
    corpus_tokens: List[List[str]] = field(repr=False)
    bm25: BM25Okapi = field(repr=False)

    @classmethod
    def from_chunks(cls, chunks: List[Document]) -> "CropBM25Index":
        chunks = assign_chunk_ids(list(chunks))
        records: Dict[str, Document] = {}
        corpus_tokens: List[List[str]] = []
        chunk_ids: List[str] = []
        for doc in chunks:
            cid = doc.metadata.get("chunk_id", "")
            if not cid:
                continue
            records[cid] = doc
            chunk_ids.append(cid)
            corpus_tokens.append(tokenize(doc.page_content))
        bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None
        return cls(chunk_ids=chunk_ids, records=records, corpus_tokens=corpus_tokens, bm25=bm25)

    def search(self, query: str, k: int) -> List[str]:
        if not self.bm25 or not self.chunk_ids:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        n = min(max(k, 0), len(self.chunk_ids))
        if n == 0:
            return []
        top_token_lists = self.bm25.get_top_n(tokens, self.corpus_tokens, n=n)
        token_id_to_idx = {id(toks): i for i, toks in enumerate(self.corpus_tokens)}
        return [
            self.chunk_ids[token_id_to_idx[id(toks)]]
            for toks in top_token_lists
            if id(toks) in token_id_to_idx
        ]


def reset_bm25_store() -> None:
    global _indexes
    _indexes = None


def _serialize_crop(index: CropBM25Index) -> dict:
    return {
        "chunk_ids": index.chunk_ids,
        "corpus_tokens": index.corpus_tokens,
        "records": [
            {
                "chunk_id": cid,
                "page_content": index.records[cid].page_content,
                "metadata": index.records[cid].metadata or {},
            }
            for cid in index.chunk_ids
            if cid in index.records
        ],
    }


def _deserialize_crop(data: dict) -> CropBM25Index:
    records: Dict[str, Document] = {}
    chunk_ids: List[str] = list(data.get("chunk_ids") or [])
    for item in data.get("records") or []:
        cid = item["chunk_id"]
        records[cid] = Document(page_content=item["page_content"], metadata=item.get("metadata") or {})
    corpus_tokens = data.get("corpus_tokens") or [tokenize(records[cid].page_content) for cid in chunk_ids]
    bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None
    return CropBM25Index(chunk_ids=chunk_ids, records=records, corpus_tokens=corpus_tokens, bm25=bm25)


def build_bm25_indexes(chunks: List[Document]) -> Dict[str, CropBM25Index]:
    by_crop: Dict[str, List[Document]] = {}
    for doc in chunks:
        crop_id = doc.metadata.get("crop_id", "apple")
        by_crop.setdefault(crop_id, []).append(doc)
    return {crop_id: CropBM25Index.from_chunks(docs) for crop_id, docs in by_crop.items()}


def save_bm25_indexes(indexes: Dict[str, CropBM25Index]) -> None:
    os.makedirs(BM25_DIR, exist_ok=True)
    payload = {
        "version": BM25_VERSION,
        "crops": {crop_id: _serialize_crop(idx) for crop_id, idx in indexes.items()},
    }
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    meta_path = os.path.join(BM25_DIR, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": BM25_VERSION,
                "crops": {crop_id: len(idx.chunk_ids) for crop_id, idx in indexes.items()},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    global _indexes
    _indexes = indexes
    total = sum(len(idx.chunk_ids) for idx in indexes.values())
    print(f"BM25 индекс сохранён: {BM25_INDEX_PATH} ({total} фрагментов)")


def load_bm25_indexes() -> Optional[Dict[str, CropBM25Index]]:
    global _indexes
    if _indexes is not None:
        return _indexes
    if not os.path.isfile(BM25_INDEX_PATH):
        return None
    with open(BM25_INDEX_PATH, "rb") as f:
        payload = pickle.load(f)
    if payload.get("version") != BM25_VERSION:
        print("BM25: устаревшая версия индекса, нужна переиндексация")
        return None
    indexes = {
        crop_id: _deserialize_crop(data) for crop_id, data in (payload.get("crops") or {}).items()
    }
    _indexes = indexes
    return indexes


def get_crop_index(crop_id: str) -> Optional[CropBM25Index]:
    indexes = load_bm25_indexes()
    if not indexes:
        return None
    return indexes.get(crop_id)


def bm25_search(query: str, crop_id: str, k: int) -> List[str]:
    index = get_crop_index(crop_id)
    if index is None:
        return []
    return index.search(query, k)


def get_chunk_document(chunk_id: str, crop_id: str) -> Optional[Document]:
    index = get_crop_index(crop_id)
    if index is None:
        return None
    return index.records.get(chunk_id)


def rebuild_bm25_from_documents(documents: List[Document]) -> Dict[str, CropBM25Index]:
    chunks = assign_chunk_ids(split_documents(documents))
    indexes = build_bm25_indexes(chunks)
    save_bm25_indexes(indexes)
    return indexes


def remove_bm25_index() -> None:
    import shutil

    reset_bm25_store()
    if os.path.isdir(BM25_DIR):
        shutil.rmtree(BM25_DIR, ignore_errors=True)
