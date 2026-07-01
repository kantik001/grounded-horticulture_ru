"""Тесты человекочитаемых заголовков статей."""

import os

import pytest

from rag.titles import get_pretty_title, title_from_slug as _title_from_slug


@pytest.fixture(autouse=True)
def crops_config_path(monkeypatch):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    monkeypatch.setenv("CROPS_CONFIG_PATH", os.path.join(root, "config", "crops.json"))


def test_title_from_slug():
    t = _title_from_slug("article308_effektivnost_regulyatora_rosta.txt")
    assert "effektivnost" in t.lower()
    assert "_" not in t


def test_get_pretty_title_mapped():
    title = get_pretty_title("apple", "article9_liberty_rootstocks_young_stavropol.txt")
    assert "Либерти" in title or "liberty" in title.lower()


def test_get_pretty_title_slug_fallback():
    title = get_pretty_title("apple", "article999_neizvestnaya_statya_test.txt")
    assert title != "article999_neizvestnaya_statya_test.txt"
    assert "neizvestnaya" in title.lower() or "Neizvestnaya" in title
