"""
Поиск по статьям (RAG retrieval): контекст для Go с учётом crop_id.
"""

import json
import os
from typing import Any, Dict, List

from rag.crops_config import get_crop, normalize_crop_id
from rag.debug_log import rag_debug
from rag.question_categories import classify_question

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_few_shot_cache = None


# Загружает config/few_shot.json один раз в кэш.
def _few_shot_path() -> str:
    env = os.environ.get("FEW_SHOT_CONFIG_PATH")
    if env and os.path.isfile(env):
        return env
    for candidate in (
        os.path.join(_PROJECT_ROOT, "config", "few_shot.json"),
        "/config/few_shot.json",
    ):
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(_PROJECT_ROOT, "config", "few_shot.json")


def _load_few_shot() -> dict:
    global _few_shot_cache
    if _few_shot_cache is not None:
        return _few_shot_cache
    path = _few_shot_path()
    with open(path, encoding="utf-8") as f:
        _few_shot_cache = json.load(f)
    return _few_shot_cache


# Возвращает few-shot пример для культуры и категории вопроса.
def few_shot_for(crop_id: str, category: str) -> str:
    crop_shots = _load_few_shot().get(crop_id, {})
    return crop_shots.get(category) or crop_shots.get("general", "")


# Главная функция: поиск в Chroma → context, few_shot, fragments для Go.
def retrieve_rag_context(user_question: str, crop_id: str = "apple") -> Dict[str, Any]:
    q = (user_question or "").strip()
    empty = {
        "success": False,
        "error": "",
        "context": "",
        "few_shot": "",
        "category": "general",
        "fragments": [],
        "crop_id": crop_id,
    }
    if not q:
        empty["error"] = "Пустой вопрос"
        return empty

    try:
        crop_id = normalize_crop_id(crop_id)
    except ValueError as e:
        empty["error"] = str(e)
        return empty

    crop = get_crop(crop_id)
    if not crop.get("rag_enabled", True):
        empty["error"] = (
            f"База статей для «{crop.get('name_ru', crop_id)}» пока не подключена. "
            "Выберите другую культуру или вернитесь позже."
        )
        return empty

    from rag.vector_store import search

    category = classify_question(q)
    fragments = search(q, crop_id=crop_id, k=8, category=category)
    if not fragments:
        empty["error"] = (
            f"Не нашёл информации в статьях по культуре «{crop.get('name_ru', crop_id)}»."
        )
        return empty

    for f in fragments:
        rag_debug(f"[RAG:{crop_id}] источник: {f.metadata.get('filename')}")

    context_parts: List[str] = []
    fr_json: List[Dict[str, str]] = []
    for frag in fragments:
        source_name = frag.metadata.get("filename", "Неизвестный источник")
        context_parts.append(f"Текст из статьи '{source_name}':\n{frag.page_content}")
        fr_json.append({"filename": source_name, "content": frag.page_content})

    context = "\n\n---\n\n".join(context_parts)
    few_shot = few_shot_for(crop_id, category)

    return {
        "success": True,
        "error": "",
        "context": context,
        "few_shot": few_shot,
        "category": category,
        "fragments": fr_json,
        "crop_id": crop_id,
    }
