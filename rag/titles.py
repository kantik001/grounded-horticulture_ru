"""Человекочитаемые заголовки статей (без зависимости от Chroma)."""

import json
import os
import re

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_titles_cache = None


def _titles_map() -> dict:
    global _titles_cache
    if _titles_cache is not None:
        return _titles_cache
    path = os.path.join(_PROJECT_ROOT, "config", "article_titles.json")
    if not os.path.isfile(path):
        _titles_cache = {}
        return _titles_cache
    with open(path, encoding="utf-8") as f:
        _titles_cache = json.load(f)
    return _titles_cache


def title_from_slug(filename: str) -> str:
    stem = filename.replace(".txt", "")
    m = re.match(r"article\d+_(.+)", stem, re.I)
    if not m:
        return filename
    words = m.group(1).replace("_", " ").strip()
    if not words:
        return filename
    return words[0].upper() + words[1:]


def _title_from_file_metadata(file_path: str) -> str | None:
    try:
        with open(file_path, encoding="utf-8") as f:
            for _ in range(20):
                line = f.readline()
                if not line.startswith("- Заголовок:"):
                    continue
                title = line.split(":", 1)[1].strip()
                if len(title) >= 12 and not title.endswith("…"):
                    return title[:160]
    except OSError:
        pass
    return None


def get_pretty_title(crop_id: str, filename: str, file_path: str | None = None) -> str:
    mapped = _titles_map().get(crop_id, {}).get(filename)
    if mapped:
        return mapped
    if file_path:
        from_meta = _title_from_file_metadata(file_path)
        if from_meta:
            return from_meta
    if filename.endswith(".txt") and filename.startswith("article"):
        return title_from_slug(filename)
    return filename
