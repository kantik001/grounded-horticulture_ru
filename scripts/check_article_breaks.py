#!/usr/bin/env python3
"""Проверка статей на обрывы строк, склейки PDF и мусор из колонтитулов."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Строка оборвана: нет .!?;:»)" в конце, но длинная и не заголовок/маркер
TRUNC_LINE = re.compile(
    r"^[-•]?\s*.{40,}[а-яёa-z0-9]$",
    re.I,
)

# Склейка PDF: пробел внутри слова (кириллица)
SPLIT_WORD = re.compile(r"[а-яё]{2,}\s+[а-яё]{2,}", re.I)

# Колонтитул журнала внутри абзаца
HEADER_JUNK = re.compile(
    r"20\d{2};\d+\(\d+\):\d+-\d+|Fruit growing and viticulture|journalkubansad\.ru/pdf/",
    re.I,
)

# Строка начинается с середины предложения (строчная после точки в предыдущей — грубая эвристика)
MID_SENT_START = re.compile(
    r"^[а-яё][а-яё\s]{10,}(?:ных|ными|ного|ной|ется|или|для)\s",
)


def check_file(path: Path) -> list[str]:
    issues: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s or len(s) < 25:
            continue
        if s.startswith(("Метаданные", "- Журнал", "- URL", "- DOI", "Кратко", "Цель", "Практика:")):
            continue
        if TRUNC_LINE.match(s) and not s.endswith((")", "]", "%", "°C", "°С")):
            issues.append(f"L{i}: обрыв строки: …{s[-55:]}")
        if HEADER_JUNK.search(s) and "URL:" not in s:
            issues.append(f"L{i}: колонтитул PDF в тексте")
        if re.search(r"\b[А-ЯЁ][а-яё]{1,3}\s+[а-яё]{3,}", s):
            # «В условиях» ок; «и воду» после обрыва — ниже
            pass

    # Склейки «сло во», «трансформиру ющихся»
    for m in SPLIT_WORD.finditer(text):
        frag = m.group(0)
        if len(frag) < 12 or frag.count(" ") > 1:
            continue
        a, b = frag.split()
        if len(a) >= 4 and len(b) >= 4 and a[-1].isalpha() and b[0].isalpha():
            pos = text.find(frag)
            line_no = text[:pos].count("\n") + 1
            issues.append(f"L{line_no}: разрыв слова «{frag}»")
            if len(issues) > 8:
                break

    # Обрыв в начале пункта «- с ними [10-16]»
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("- ") and MID_SENT_START.match(s[2:]):
            issues.append(f"L{i}: пункт с середины фразы: {s[:70]}…")

    return issues[:12]


def main() -> int:
    bad: list[tuple[str, list[str]]] = []
    for crop in ("apple", "pear", "plum"):
        d = DATA / crop
        if not d.is_dir():
            continue
        for p in sorted(d.glob("article*.txt")):
            issues = check_file(p)
            if issues:
                bad.append((str(p.relative_to(ROOT)), issues))

    print(f"Проверено файлов: {sum(1 for _ in DATA.rglob('article*.txt'))}")
    print(f"С замечаниями: {len(bad)}")
    for rel, issues in bad[:40]:
        print(f"\n{rel}")
        for x in issues:
            print(f"  {x}")
    if len(bad) > 40:
        print(f"\n… и ещё {len(bad) - 40} файлов")

    # Ручные статьи — отдельно
    manual_hints = []
    for rel, issues in bad:
        if any("колонтитул" in x or "середины фразы" in x for x in issues):
            manual_hints.append(rel)
    if manual_hints:
        print(f"\nПриоритет исправления (ручные/обогащённые): {len(manual_hints)}")

    return 1 if len(bad) > 50 else 0


if __name__ == "__main__":
    sys.exit(main())
