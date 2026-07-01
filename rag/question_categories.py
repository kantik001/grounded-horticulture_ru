"""Загрузка config/question_categories.json — domain pack для classify_question."""

import json
import os
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_CONFIG: Optional[Dict[str, Any]] = None
_CONFIG_MTIME: Optional[float] = None


def _config_path() -> str:
    env = os.environ.get("QUESTION_CATEGORIES_CONFIG_PATH")
    if env and os.path.isfile(env):
        return env
    for candidate in (
        os.path.join(_PROJECT_ROOT, "config", "question_categories.json"),
        "/config/question_categories.json",
    ):
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(_PROJECT_ROOT, "config", "question_categories.json")


def load_question_categories_config() -> Dict[str, Any]:
    global _CONFIG, _CONFIG_MTIME
    path = _config_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    if _CONFIG is not None and _CONFIG_MTIME == mtime:
        return _CONFIG
    with open(path, encoding="utf-8") as f:
        _CONFIG = json.load(f)
    _CONFIG_MTIME = mtime
    return _CONFIG


def reload_question_categories_config() -> Dict[str, Any]:
    """Сброс кэша (тесты)."""
    global _CONFIG, _CONFIG_MTIME
    _CONFIG = None
    _CONFIG_MTIME = None
    return load_question_categories_config()


def category_rules() -> List[Dict[str, Any]]:
    cfg = load_question_categories_config()
    return list(cfg.get("categories") or [])


def default_category() -> str:
    cfg = load_question_categories_config()
    return str(cfg.get("default_category") or "general")


def classify_question(question: str) -> str:
    """Категория вопроса по ключевым словам из domain pack (порядок категорий важен)."""
    q_lower = (question or "").lower()
    for rule in category_rules():
        cat_id = str(rule.get("id") or "").strip()
        if not cat_id:
            continue
        keywords = rule.get("keywords") or []
        if any(kw in q_lower for kw in keywords if kw):
            return cat_id
    return default_category()
