#!/usr/bin/env python3
"""Подставить человекочитаемые заголовки из config/article_titles.json в метаданные статей."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TITLES_PATH = ROOT / "config" / "article_titles.json"
CROPS = ("apple", "pear", "plum", "demo_hr")

TITLE_LINE_RE = re.compile(
    r"(^-\s*Заголовок:\s*)(.+?)(?=\n-\s|\n\n|$)",
    re.M | re.S,
)
STEM_TITLE_RE = re.compile(r"^article\d+_", re.I)
UDK_TITLE_RE = re.compile(r"^(?:УДК|UDC)\b", re.I)


def needs_replace(current: str) -> bool:
    t = current.strip()
    if not t:
        return True
    if STEM_TITLE_RE.match(t):
        return True
    if UDK_TITLE_RE.match(t):
        return True
    return len(t) < 12


def main() -> None:
    if not TITLES_PATH.exists():
        print("article_titles.json not found", file=sys.stderr)
        sys.exit(1)
    titles = json.loads(TITLES_PATH.read_text(encoding="utf-8"))
    updated = skipped = 0

    for crop in CROPS:
        crop_titles = titles.get(crop, {})
        crop_dir = DATA / crop
        if not crop_dir.is_dir():
            continue
        for path in sorted(crop_dir.glob("article*.txt")):
            pretty = crop_titles.get(path.name)
            if not pretty:
                skipped += 1
                continue
            text = path.read_text(encoding="utf-8")
            m = TITLE_LINE_RE.search(text)
            if not m:
                skipped += 1
                continue
            current = m.group(2).strip().split(" - URL:")[0].strip()
            if not needs_replace(current):
                skipped += 1
                continue
            new_text = TITLE_LINE_RE.sub(
                lambda mm: mm.group(1) + pretty,
                text,
                count=1,
            )
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                updated += 1
                print(f"ok {crop}/{path.name}")

    print(f"updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
