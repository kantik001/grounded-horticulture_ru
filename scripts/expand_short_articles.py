#!/usr/bin/env python3
"""Расширить короткие статьи (1–122) из PDF журнала — формат как у авто-ingest."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from journal_ingest import (  # noqa: E402
    build_article_body,
    download_pdf,
    extract_pdf_text,
    pdf_cache_path,
)
ROOT = _SCRIPTS.parent
DATA = ROOT / "data"
CATALOG = ROOT / "_tmp" / "journal_catalog.json"
TITLES_PATH = ROOT / "config" / "article_titles.json"
CROPS = ("apple", "pear", "plum")
MAX_NUM = 122
MAX_LEN = 9500
MAX_ISSUE_PDF = 26
PDF_PROBE_CACHE: dict[str, str] = {}
JOURNAL_URL_RE = re.compile(
    r"https?://journal(?:kubansad|\.kubansad)\.ru/pdf/[^\s\)\]]+",
    re.I,
)
JOURNAL_ISSUE_RE = re.compile(
    r"(\d{4})\s*;\s*(\d+)\s*\(\s*0*(\d+)\s*\)\s*:\s*(\d+)\s*-\s*(\d+)",
    re.I,
)
KW_STOP = {
    "кратко", "практика", "культура", "культуры", "регион", "авторы", "журнал",
    "метаданные", "источника", "яблоня", "груша", "слива", "статья", "данные",
    "результаты", "исследования", "условиях", "краснодар", "ставрополь",
}

# Проверенные соответствия короткая статья → PDF
MANUAL_PDF_OVERRIDES: dict[str, str] = {
    "article9_liberty_rootstocks_young_stavropol": "http://journalkubansad.ru/pdf/13/05/08.pdf",
    "article2_belarus_chelate_foliar": "http://journalkubansad.ru/pdf/13/05/15.pdf",
    "article85_annual_seedling_crowning": "http://journalkubansad.ru/pdf/10/04/04.pdf",
    "article10_mechanized_orchard_planting": "http://journalkubansad.ru/pdf/12/04/04.pdf",
    "article31_sunburn_protection_products": "http://journalkubansad.ru/pdf/14/04/10.pdf",
    "article90_in_vitro_antibiotics_sk": "http://journalkubansad.ru/pdf/19/06/09.pdf",
    "article23_stress_resistance_agrotech_prichko": "http://journalkubansad.ru/pdf/21/06/09.pdf",
    "article6_pear_winter_hardiness_slopes": "http://journalkubansad.ru/pdf/11/04/11.pdf",
    "article110_apple_adaptive_potential_krasnodar": "http://journalkubansad.ru/pdf/12/01/04.pdf",
}

WRONG_PDF_MARKERS = (
    "Попова Валентина Петровна",
    "РАЗРАБОТКА ПРИЕМОВ УПРАВЛЕНИЯ УСТОЙЧИВОСТЬЮ ПЛОДОВЫХ ЦЕНОЗОВ",
)


def norm_journal_url(url: str) -> str:
    return url.replace("journal.kubansad.ru", "journalkubansad.ru").rstrip(").,")


def norm_doi(text: str) -> str:
    m = re.search(r"10\.30679/2219-5335-[^\s\)\]]+", text)
    return m.group(0).rstrip(").,") if m else ""


def article_num(path: Path) -> int:
    m = re.search(r"article(\d+)", path.name)
    return int(m.group(1)) if m else 9999


def doi_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for crop in CROPS:
        for p in (DATA / crop).glob("article*.txt"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            url_m = JOURNAL_URL_RE.search(t)
            d = norm_doi(t)
            if url_m and d:
                m[d] = norm_journal_url(url_m.group(0))
    if CATALOG.exists():
        try:
            for it in json.loads(CATALOG.read_text(encoding="utf-8")):
                if it.get("doi") and it.get("pdf_url"):
                    m[it["doi"]] = it["pdf_url"]
        except Exception:
            pass
    return m


def parse_doi_issue(doi: str) -> tuple[str, str] | None:
    m = re.search(r"2219-5335-(\d{4})-(\d+)-", doi)
    if not m:
        return None
    year, issue = m.group(1), int(m.group(2))
    return f"{year[-2:]}", f"{issue:02d}"


def parse_doi_pages(doi: str) -> tuple[int, int] | None:
    m = re.search(r"2219-5335-\d{4}-\d+-\d+-(\d+)-(\d+)$", doi)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_journal_issue(text: str) -> tuple[str, str, int, int] | None:
    m = JOURNAL_ISSUE_RE.search(text)
    if not m:
        return None
    year, _vol, issue, p1, p2 = m.groups()
    return f"{int(year) % 100:02d}", f"{int(issue):02d}", int(p1), int(p2)


def pdf_text_has_doi(pdf_text: str, doi: str) -> bool:
    compact = re.sub(r"\s+", "", pdf_text)
    tail = doi.split("/")[-1]
    needles = {doi, tail, tail.replace("-", ""), doi.replace("-", "")}
    for n in needles:
        if n and n in compact:
            return True
    pages = parse_doi_pages(doi)
    if pages:
        a, b = pages
        if f"{a}-{b}" in pdf_text or f"{a}–{b}" in pdf_text:
            return True
    return False


def ensure_pdf(url: str, session: requests.Session) -> Path:
    path = pdf_cache_path(url)
    download_pdf(url, path, session)
    return path


def scan_issue_pdfs(
    yy: str,
    ii: str,
    session: requests.Session,
    matcher,
) -> str:
    for n in range(1, MAX_ISSUE_PDF):
        url = f"http://journalkubansad.ru/pdf/{yy}/{ii}/{n:02d}.pdf"
        try:
            path = ensure_pdf(url, session)
            if path.stat().st_size < 5000:
                continue
            if matcher(extract_pdf_text(path)):
                PDF_PROBE_CACHE[url] = url
                return url
        except Exception:
            continue
    return ""


def resolve_pdf_by_doi(doi: str, session: requests.Session, by: dict[str, str]) -> str:
    if doi in PDF_PROBE_CACHE:
        return PDF_PROBE_CACHE[doi]
    if doi in by:
        PDF_PROBE_CACHE[doi] = by[doi]
        return by[doi]
    issue = parse_doi_issue(doi)
    if not issue:
        return ""
    yy, ii = issue
    found = scan_issue_pdfs(
        yy,
        ii,
        session,
        lambda t: pdf_text_has_doi(t, doi),
    )
    if found:
        PDF_PROBE_CACHE[doi] = found
    return found


def kratko_keywords(text: str) -> list[str]:
    chunk = text
    for label in ("Кратко:", "Кратко для садовода"):
        if label in text:
            chunk = text.split(label, 1)[1]
            break
    chunk = chunk[:800]
    words = re.findall(r"[А-ЯЁа-яё]{5,}", chunk)
    out = []
    for w in words:
        low = w.lower()
        if low in KW_STOP:
            continue
        if low not in out:
            out.append(low)
        if len(out) >= 8:
            break
    return out


def author_surnames(meta: dict[str, str]) -> list[str]:
    authors = meta.get("Авторы", "")
    skip = {
        "краснодар", "ставрополь", "северо", "кабардино", "нальчик",
        "москва", "орел", "орёл", "астрахань", "беларусь",
    }
    out: list[str] = []
    for w in re.findall(r"[А-ЯЁ][а-яё]{3,}", authors):
        low = w.lower()
        if low in skip:
            continue
        if low not in out:
            out.append(low)
    return out[:4]


def pdf_matches_topic(pdf_text: str, text: str, meta: dict[str, str]) -> bool:
    low = pdf_text.lower()
    authors = author_surnames(meta)
    if authors and not any(a in low for a in authors):
        return False
    if any(m.lower() in low for m in WRONG_PDF_MARKERS):
        if authors and "попова" not in authors:
            return False
    kws = kratko_keywords(text)
    if len(kws) < 3:
        return True
    score = sum(1 for k in kws if k in low)
    return score >= max(3, len(kws) // 2)


def has_wrong_pdf_assignment(text: str, meta: dict[str, str]) -> bool:
    if not any(m in text for m in WRONG_PDF_MARKERS):
        return False
    authors = author_surnames(meta)
    return bool(authors) and "попова" not in authors


def resolve_from_corpus(
    path: Path,
    text: str,
    session: requests.Session,
    meta: dict[str, str],
) -> str:
    """Найти PDF по совпадению ключевых слов с уже расширенной статьёй той же культуры."""
    crop = path.parent.name
    kws = kratko_keywords(text)
    if len(kws) < 3:
        return ""
    best_url, best_score = "", 0
    for p in (DATA / crop).glob("article*.txt"):
        if p == path:
            continue
        other = p.read_text(encoding="utf-8", errors="ignore")
        if len(other) < MAX_LEN:
            continue
        if has_wrong_pdf_assignment(other, parse_meta(other)):
            continue
        url_m = JOURNAL_URL_RE.search(other)
        if not url_m:
            continue
        body_low = other.lower()
        score = sum(1 for k in kws if k in body_low)
        if score > best_score and score >= max(3, len(kws) // 2):
            url = norm_journal_url(url_m.group(0))
            try:
                pdf_path = ensure_pdf(url, session)
                pdf_text = extract_pdf_text(pdf_path)
            except Exception:
                continue
            if not pdf_matches_topic(pdf_text, text, meta):
                continue
            best_score = score
            best_url = url
    return best_url


def resolve_by_keywords(text: str, session: requests.Session) -> str:
    issue = parse_journal_issue(text)
    kws = kratko_keywords(text)
    if not issue or len(kws) < 3:
        return ""
    yy, ii, p1, p2 = issue
    page_hint = f"{p1}-{p2}"

    def matcher(pdf_text: str) -> bool:
        if page_hint in pdf_text or page_hint.replace("-", "–") in pdf_text:
            return True
        low = pdf_text.lower()
        return sum(1 for k in kws if k in low) >= max(3, len(kws) // 2)

    return scan_issue_pdfs(yy, ii, session, matcher)


def resolve_pdf_url(
    path: Path,
    text: str,
    session: requests.Session,
    by_doi: dict[str, str],
    meta: dict[str, str],
) -> str:
    stem = path.stem
    if stem in MANUAL_PDF_OVERRIDES:
        return MANUAL_PDF_OVERRIDES[stem]

    ignore_url = has_wrong_pdf_assignment(text, meta)

    url_m = JOURNAL_URL_RE.search(text)
    if url_m and not ignore_url:
        url = norm_journal_url(url_m.group(0))
        try:
            pdf_path = ensure_pdf(url, session)
            if pdf_matches_topic(extract_pdf_text(pdf_path), text, meta):
                return url
        except Exception:
            pass

    doi = norm_doi(text)
    if doi:
        found = resolve_pdf_by_doi(doi, session, by_doi)
        if found:
            try:
                pdf_path = ensure_pdf(found, session)
                if pdf_matches_topic(extract_pdf_text(pdf_path), text, meta):
                    return found
            except Exception:
                pass

    found = resolve_by_keywords(text, session)
    if found:
        try:
            pdf_path = ensure_pdf(found, session)
            if pdf_matches_topic(extract_pdf_text(pdf_path), text, meta):
                return found
        except Exception:
            pass

    return resolve_from_corpus(path, text, session, meta)


def is_ingest_expanded(text: str) -> bool:
    return (
        "Метаданные источника:" in text
        and JOURNAL_URL_RE.search(text)
        and "Основные результаты:" in text
        and len(text) > 5000
        and (
            "Цель и задачи:" in text
            or "Объекты, методы" in text
            or "Дополнение из ручной разметки" in text
        )
    )


def should_expand(path: Path, text: str, *, repair: bool = False) -> bool:
    if article_num(path) > MAX_NUM:
        return False
    meta = parse_meta(text)
    if repair:
        return has_wrong_pdf_assignment(text, meta)
    if "Кратко для садовода и ассистента:" in text and "Цель исследований:" in text:
        return False
    if is_ingest_expanded(text) and not has_wrong_pdf_assignment(text, meta):
        return False
    if (
        "Кратко для садовода" in text
        and "Цель и задачи:" in text
        and len(text) > MAX_LEN
        and not has_wrong_pdf_assignment(text, meta)
    ):
        return False
    if (
        len(text) > MAX_LEN
        and "Кратко:" not in text
        and not has_wrong_pdf_assignment(text, meta)
    ):
        return False
    return bool(
        re.search(r"Кратко(?:\s+для\s+садовода)?\s*:", text, re.I)
        or "Практика:" in text
        or "Новое для региона:" in text
        or has_wrong_pdf_assignment(text, meta)
    )


def parse_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for key in ("Авторы", "Журнал", "Регион", "Культура", "Культуры", "DOI"):
        m = re.search(rf"-\s*{key}:\s*(.+)", text, re.I)
        if m:
            meta[key] = m.group(1).strip()
    return meta


def extract_manual_extra(text: str) -> str:
    chunks: list[str] = []
    markers = (
        "Новое для региона:",
        "Практика:",
        "Примечание для бота:",
        "Связь с другими темами RAG:",
        "Цифры:",
    )
    for label in markers:
        if label not in text:
            continue
        part = text.split(label, 1)[1]
        stop = len(part)
        for end_m in (
            "Метаданные",
            "Кратко",
            "Цель",
            "Дисклеймер",
            "Аннотация",
            "Цифры из",
            "Основные результаты",
        ):
            i = part.find("\n\n" + end_m)
            if i != -1:
                stop = min(stop, i)
        body = part[:stop].strip()
        if len(body) > 40:
            chunks.append(f"{label}\n{body}")
    note = re.search(r"-\s*Примечание[^:\n]*:\s*(.+)", text, re.I)
    if note and "Примечание для бота" not in text:
        chunks.append("Примечание из метаданных:\n" + note.group(1).strip())
    return "\n\n".join(chunks)


def merge_body(pdf_body: str, manual_extra: str, meta: dict[str, str]) -> str:
    if not manual_extra:
        return pdf_body
    extra_lines = ["", "Дополнение из ручной разметки (сохранено при расширении):", manual_extra]
    if "Регион" in meta and meta["Регион"] not in pdf_body:
        extra_lines.insert(2, f"Регион (из метаданных): {meta['Регион']}")
    if pdf_body.rstrip().endswith("адаптации."):
        return pdf_body.rstrip()[:-1].rstrip() + "\n" + "\n".join(extra_lines) + "\n"
    return pdf_body.rstrip() + "\n" + "\n".join(extra_lines) + "\n"


def display_title(path: Path) -> str:
    if TITLES_PATH.exists():
        try:
            titles = json.loads(TITLES_PATH.read_text(encoding="utf-8"))
            crop = path.parent.name
            title = titles.get(crop, {}).get(path.name)
            if title:
                return title
        except Exception:
            pass
    return path.stem


def main() -> None:
    repair = "--repair" in sys.argv
    session = requests.Session()
    session.headers["User-Agent"] = "doctor_gardens_ai-kb-bot/1.0 (research; local)"
    by_doi = doi_map()
    done = skip = fail = 0

    for crop in CROPS:
        for path in sorted((DATA / crop).glob("article*.txt")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not should_expand(path, text, repair=repair):
                skip += 1
                continue

            meta = parse_meta(text)
            pdf_url = resolve_pdf_url(path, text, session, by_doi, meta)
            if not pdf_url:
                print(f"skip no pdf {crop}/{path.name}", flush=True)
                skip += 1
                continue

            manual_extra = extract_manual_extra(text)
            item = {
                "title": display_title(path),
                "pdf_url": pdf_url,
                "doi": norm_doi(text),
                "authors": meta.get("Авторы", ""),
                "abstract": "",
                "crop_id": crop,
            }
            try:
                pdf_path = ensure_pdf(pdf_url, session)
                body = merge_body(
                    build_article_body(item, extract_pdf_text(pdf_path)),
                    manual_extra,
                    meta,
                )
                path.write_text(body, encoding="utf-8")
                print(f"ok {crop}/{path.name} ({len(body)} chars) <- {pdf_url}", flush=True)
                done += 1
                time.sleep(0.15)
            except Exception as e:
                print(f"fail {path.name}: {e}", flush=True)
                fail += 1

    print(f"expanded={done} skipped={skip} failed={fail}")


if __name__ == "__main__":
    main()
