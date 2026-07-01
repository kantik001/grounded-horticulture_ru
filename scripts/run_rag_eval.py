#!/usr/bin/env python3
"""
Прогон eval-набора RAG: POST /rag/context и проверка метрик.
Режим по умолчанию — retrieval (без LLM). Опционально --full через Go /chat (нужен LLM_API_KEY).

Ускорение:
  --in-process   вызов retrieve_rag_context() без HTTP (лучше внутри Docker classifier)
  --fast         без cross-encoder rerank (~15× быстрее, smoke-eval)
  --workers N    параллельные запросы (HTTP или in-process; оптимум ~2 на CPU)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests

_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = _ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"

SUITES = {
    "apple": EVAL_DIR / "rag_apple_baseline.jsonl",
    "pear": EVAL_DIR / "rag_pear_baseline.jsonl",
    "plum": EVAL_DIR / "rag_plum_baseline.jsonl",
    "demo_hr": EVAL_DIR / "rag_demo_hr_baseline.jsonl",
}

_retrieve_rag_context: Callable[..., Dict[str, Any]] | None = None


def _ensure_project_root_on_path() -> None:
    root = str(_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _get_retrieve_rag_context() -> Callable[..., Dict[str, Any]]:
    global _retrieve_rag_context
    if _retrieve_rag_context is None:
        _ensure_project_root_on_path()
        from rag.retrieval import retrieve_rag_context

        _retrieve_rag_context = retrieve_rag_context
    return _retrieve_rag_context


def apply_fast_mode(enabled: bool) -> None:
    if enabled:
        os.environ["RAG_RERANK_ENABLED"] = "false"


def context_contains(haystack: str, needle: str) -> bool:
    """Подстрока в контексте; для русского — укороченный стем (подвой ↔ подвои)."""
    h = haystack.lower()
    n = needle.lower()
    if n in h:
        return True
    if len(n) >= 5:
        stem = n[:-1]
        if len(stem) >= 4 and stem in h:
            return True
    if len(n) >= 4:
        stem4 = n[:4]
        if stem4 in h:
            return True
    return False


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cases.append(json.loads(line))
    return cases


def fetch_context(rag_url: str, question: str, crop_id: str, timeout: int) -> Dict[str, Any]:
    resp = requests.post(
        rag_url,
        json={"question": question, "crop_id": crop_id},
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=timeout,
    )
    try:
        body = resp.json()
    except Exception:
        body = {"success": False, "error": resp.text[:500]}
    return {"http_status": resp.status_code, **body}


def fetch_context_local(question: str, crop_id: str) -> Dict[str, Any]:
    payload = _get_retrieve_rag_context()(question, crop_id=crop_id)
    status = 200 if payload.get("success") else 422
    return {"http_status": status, **payload}


def check_retrieval(case: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    ok = ctx.get("success") is True and resp_status_ok(ctx)
    context_text = (ctx.get("context") or "").lower()
    fragments = ctx.get("fragments") or []

    if case.get("expect_out_of_scope"):
        # Допускаем soft fail от RAG или короткий контекст
        ok = ok or (not context_text.strip()) or "нет" in (ctx.get("error") or "").lower()
    else:
        if case.get("expect_context", True) and ok:
            ok = bool(context_text.strip()) or len(fragments) > 0

    missing = []
    for sub in case.get("expect_contains") or []:
        if not context_contains(context_text, sub):
            missing.append(sub)

    any_of = case.get("expect_contains_any") or []
    if any_of and not any(context_contains(context_text, sub) for sub in any_of):
        missing.append("any_of:" + "|".join(any_of))

    return {
        "passed": ok and not missing,
        "retrieval_ok": ctx.get("success"),
        "missing_in_context": missing,
        "fragment_count": len(fragments),
    }


def resp_status_ok(ctx: Dict[str, Any]) -> bool:
    status = int(ctx.get("http_status", 0))
    if 200 <= status < 300:
        return True
    # Python /rag/context: 422 = штатный «нет контекста», не сбой транспорта.
    return status == 422 and ctx.get("success") is False


def eval_case(
    index: int,
    case: Dict[str, Any],
    *,
    in_process: bool,
    rag_url: str,
    timeout: int,
) -> Dict[str, Any]:
    q = case["question"]
    crop_id = case.get("crop_id", "apple")
    if in_process:
        ctx = fetch_context_local(q, crop_id)
    else:
        ctx = fetch_context(rag_url, q, crop_id, timeout)
    check = check_retrieval(case, ctx)
    return {
        "index": index,
        "category": case.get("category"),
        "question": q,
        "crop_id": crop_id,
        "check": check,
        "rag_error": ctx.get("error"),
    }


def run_suite(
    suite_name: str,
    path: Path,
    rag_url: str,
    timeout: int,
    *,
    in_process: bool = False,
    workers: int = 1,
) -> Dict[str, Any]:
    cases = load_cases(path)
    if not cases:
        return {
            "suite": suite_name,
            "total": 0,
            "passed": 0,
            "pass_rate": 0.0,
            "cases": [],
        }

    workers = max(1, workers)
    results: List[Dict[str, Any] | None] = [None] * len(cases)

    if workers == 1:
        for i, case in enumerate(cases):
            results[i] = eval_case(
                i, case, in_process=in_process, rag_url=rag_url, timeout=timeout
            )
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    eval_case,
                    i,
                    case,
                    in_process=in_process,
                    rag_url=rag_url,
                    timeout=timeout,
                ): i
                for i, case in enumerate(cases)
            }
            for future in as_completed(futures):
                item = future.result()
                results[item["index"]] = item

    assert all(r is not None for r in results)
    passed = sum(1 for r in results if r["check"]["passed"])
    total = len(cases)
    return {
        "suite": suite_name,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "cases": results,  # type: ignore[arg-type]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG eval (retrieval)")
    parser.add_argument(
        "--suite",
        choices=["apple", "pear", "plum", "demo_hr", "all"],
        default="apple",
        help="Набор вопросов",
    )
    parser.add_argument(
        "--rag-url",
        default=os.environ.get("CLASSIFIER_RAG_URL", "http://localhost:5000/rag/context"),
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Прямой вызов retrieve_rag_context (рекомендуется: docker exec classifier)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Отключить reranker (RAG_RERANK_ENABLED=false); smoke-eval",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Параллельных запросов (оптимум ~2 при HTTP к classifier)",
    )
    args = parser.parse_args()

    apply_fast_mode(args.fast)
    if args.in_process:
        _ensure_project_root_on_path()

    suites = list(SUITES.keys()) if args.suite == "all" else [args.suite]
    started = time.perf_counter()
    report = {
        "mode": "retrieval",
        "rag_url": "in-process" if args.in_process else args.rag_url,
        "in_process": args.in_process,
        "fast": args.fast,
        "workers": max(1, args.workers),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suites": [],
    }
    exit_code = 0
    for name in suites:
        path = SUITES[name]
        if not path.is_file():
            print(f"Нет файла: {path}", file=sys.stderr)
            exit_code = 1
            continue
        summary = run_suite(
            name,
            path,
            args.rag_url,
            args.timeout,
            in_process=args.in_process,
            workers=args.workers,
        )
        report["suites"].append(summary)
        print(f"[{name}] {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
        if summary["passed"] < summary["total"]:
            exit_code = 1
            for c in summary["cases"]:
                if not c["check"]["passed"]:
                    print(f"  FAIL: {c['question'][:60]}… missing={c['check']['missing_in_context']}")

    elapsed = time.perf_counter() - started
    report["elapsed_s"] = round(elapsed, 2)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = args.suite
    if args.fast:
        suffix += "_fast"
    if args.in_process:
        suffix += "_local"
    out = RESULTS_DIR / f"{stamp}_{suffix}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Готово за {elapsed:.1f}s — отчёт: {out}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
