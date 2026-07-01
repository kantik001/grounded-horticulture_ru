"""Расширение пользовательского запроса синонимами из agro_glossary.json для BM25/vector."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, List

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@lru_cache(maxsize=1)
def _load_glossary() -> Dict[str, List[str]]:
    path = os.environ.get(
        "AGRO_GLOSSARY_PATH",
        os.path.join(_PROJECT_ROOT, "config", "agro_glossary.json"),
    )
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except OSError:
        return {}
    out: Dict[str, List[str]] = {}
    for key, values in raw.items():
        k = str(key).strip().lower()
        if not k:
            continue
        syns = [str(v).strip() for v in values if str(v).strip()]
        if syns:
            out[k] = syns
    return out


def expand_query(query: str) -> str:
    """Добавляет к запросу синонимы, если в тексте есть ключ глоссария."""
    q = (query or "").strip()
    if not q:
        return q
    glossary = _load_glossary()
    if not glossary:
        return q

    q_lower = q.lower()
    extras: List[str] = []
    seen = {q_lower}
    for term, syns in glossary.items():
        if term not in q_lower:
            continue
        for syn in syns:
            s = syn.lower()
            if s not in seen and s not in q_lower:
                seen.add(s)
                extras.append(syn)
    if not extras:
        return q
    return f"{q} {' '.join(extras)}"
