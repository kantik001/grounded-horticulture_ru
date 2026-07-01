"""Загрузка config/crops.json — единый список культур для RAG и CV."""

import json
import os
from typing import Any, Dict, Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_CONFIG: Optional[Dict[str, Any]] = None
_CONFIG_MTIME: Optional[float] = None


# Ищет путь к crops.json (env, локально или /config в Docker).
def _config_path() -> str:
    env = os.environ.get("CROPS_CONFIG_PATH")
    if env and os.path.isfile(env):
        return env
    for candidate in (
        os.path.join(_PROJECT_ROOT, "config", "crops.json"),
        "/config/crops.json",
    ):
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(_PROJECT_ROOT, "config", "crops.json")


# Читает и кэширует crops.json; при изменении файла на диске перечитывает.
def load_crops_config() -> Dict[str, Any]:
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


def reload_crops_config() -> Dict[str, Any]:
    """Сброс кэша crops.json (тесты)."""
    global _CONFIG, _CONFIG_MTIME
    _CONFIG = None
    _CONFIG_MTIME = None
    return load_crops_config()


# Возвращает crop_id по умолчанию из конфига (обычно apple).
def default_crop_id() -> str:
    return load_crops_config().get("default_crop", "apple")


# Приводит crop_id к нижнему регистру и проверяет, что культура есть в конфиге.
def normalize_crop_id(crop_id: Optional[str]) -> str:
    cid = (crop_id or "").strip().lower() or default_crop_id()
    crops = load_crops_config().get("crops", {})
    if cid not in crops:
        raise ValueError(f"Неизвестная культура: {crop_id}")
    return cid


# Возвращает запись одной культуры из crops.json (name_ru, cv_enabled, rag_enabled).
def get_crop(crop_id: str) -> Dict[str, Any]:
    cid = normalize_crop_id(crop_id)
    return load_crops_config()["crops"][cid]


# Список всех культур для API GET /crops.
def list_crops() -> Dict[str, Any]:
    cfg = load_crops_config()
    return {
        "default_crop": cfg.get("default_crop", "apple"),
        "crops": cfg.get("crops", {}),
    }
