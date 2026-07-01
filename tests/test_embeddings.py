"""Тесты префиксов multilingual-e5."""

import sys

from rag.embeddings import _passage, _query, get_embeddings, reset_embeddings


def test_passage_prefix():
    assert _passage("текст") == "passage: текст"
    assert _passage("passage: уже") == "passage: уже"


def test_query_prefix():
    assert _query("вопрос") == "query: вопрос"
    assert _query("Query: есть") == "Query: есть"


def test_get_embeddings_singleton(monkeypatch):
    reset_embeddings()
    created = []

    class FakeHFModule:
        class HuggingFaceEmbeddings:
            def __init__(self, model_name):
                created.append(model_name)

    monkeypatch.setitem(sys.modules, "langchain_huggingface", FakeHFModule)

    first = get_embeddings()
    second = get_embeddings()
    assert first is second
    assert len(created) == 1
    reset_embeddings()
