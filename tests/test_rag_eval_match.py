"""Тесты нормализации expect_contains в run_rag_eval."""

import importlib.util
from pathlib import Path


def _load_eval_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_rag_eval.py"
    spec = importlib.util.spec_from_file_location("run_rag_eval", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_context_contains_exact():
    mod = _load_eval_module()
    assert mod.context_contains("клоновые подвои сливы", "подвои")


def test_context_contains_russian_stem():
    mod = _load_eval_module()
    assert mod.context_contains("клоновые подвои сливы", "подвой")


def test_context_contains_missing():
    mod = _load_eval_module()
    assert not mod.context_contains("урожайность яблони", "парша")
