#!/usr/bin/env python3
"""Точечная чистка: только явно повреждённые файлы и мусор в блоках «Цифры»."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CORRUPT_MARK = re.compile(
    r"Краткодля|мероприятийпо|Влияниесорто|завязикак|Цифрыиз|имеющихген|"
    r"Краснодарскогокрая|сортоваяблон|площадивсех|продуктивностьюи",
    re.I,
)

HEADER_IN_LINE = re.compile(
    r"20\d{2};\d+\(\d+\):\d|Fruit growing and viticulture|journalkubansad\.ru/pdf/",
    re.I,
)

MID_BULLET = re.compile(
    r"^- (?:с|и|к|в|на|по|от|до|из|у|о|а|но|же|бы|ли|для|при|или|так|что|где|как|не|ни)\s",
    re.I,
)


def clean_supplement_bullets(text: str) -> tuple[str, int]:
    """Убрать обрывные пункты только в доп. блоках обогащения."""
    removed = 0
    lines = text.splitlines()
    in_block = False
    for i, line in enumerate(lines):
        if line.startswith(
            (
                "Цифры из таблиц",
                "Дополнение — цифры",
                "Аннотация из журнала",
            )
        ):
            in_block = True
            continue
        if in_block and line.startswith(
            (
                "Основные результаты",
                "Практика — дополнение",
                "Дисклеймер:",
                "Практика:",
                "Кратко",
                "Новое для",
                "Метаданные",
            )
        ):
            in_block = False
        if not in_block or not line.strip().startswith("- "):
            continue
        if HEADER_IN_LINE.search(line) or MID_BULLET.match(line.strip()):
            lines[i] = ""
            removed += 1
    return "\n".join(lines), removed


def main() -> int:
    changed = fixes = 0
    for crop in ("apple", "pear", "plum"):
        for p in sorted((DATA / crop).glob("article*.txt")):
            raw = p.read_text(encoding="utf-8", errors="ignore")
            if not CORRUPT_MARK.search(raw) and "Цифры из таблиц" not in raw:
                continue
            t, r = clean_supplement_bullets(raw)
            if t != raw:
                if not t.endswith("\n"):
                    t += "\n"
                p.write_text(t, encoding="utf-8")
                changed += 1
                fixes += r
    print(f"changed={changed} bullet_cleaned={fixes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
