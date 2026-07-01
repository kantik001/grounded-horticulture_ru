"""Тесты условного debug-лога RAG."""

from rag.debug_log import rag_debug, rag_debug_enabled


def test_rag_debug_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RAG_DEBUG", raising=False)
    assert rag_debug_enabled() is False


def test_rag_debug_enabled(monkeypatch):
    monkeypatch.setenv("RAG_DEBUG", "true")
    assert rag_debug_enabled() is True
