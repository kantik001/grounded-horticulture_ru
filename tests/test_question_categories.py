"""Тесты classify_question и загрузки config/question_categories.json."""

import json
from pathlib import Path

import pytest

from rag import question_categories as qc


@pytest.fixture(autouse=True)
def _reset_categories_cache(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    path = root / "config" / "question_categories.json"
    monkeypatch.setenv("QUESTION_CATEGORIES_CONFIG_PATH", str(path))
    qc.reload_question_categories_config()
    yield
    qc.reload_question_categories_config()


def test_classify_rootstock():
    assert qc.classify_question("Какие подвои СК для юга?") == "rootstock"


def test_classify_pest_as_disease():
    assert qc.classify_question("Как бороться с плодожоркой?") == "disease"


def test_classify_relief():
    assert qc.classify_question("Террасы сливы в КБР") == "relief"


def test_classify_general_fallback():
    assert qc.classify_question("Привет") == "general"


def test_category_rules_loaded_from_config():
    rules = qc.category_rules()
    ids = [r["id"] for r in rules]
    assert "rootstock" in ids
    assert "disease" in ids
    assert ids.index("rootstock") < ids.index("disease")


def test_custom_config_override(tmp_path, monkeypatch):
    custom = {
        "default_category": "general",
        "categories": [{"id": "hr_policy", "keywords": ["отпуск", "больнич"]}],
    }
    cfg_file = tmp_path / "question_categories.json"
    cfg_file.write_text(json.dumps(custom, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("QUESTION_CATEGORIES_CONFIG_PATH", str(cfg_file))
    qc.reload_question_categories_config()
    assert qc.classify_question("Как оформить отпуск?") == "hr_policy"
    assert qc.classify_question("Случайный вопрос") == "general"
