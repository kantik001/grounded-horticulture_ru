"""Тесты RAG retrieval: категории вопросов и дедупликация чанков."""

from langchain_core.documents import Document

from rag.chunking import diversify_fragments
from rag.retrieval import classify_question


def test_classify_rootstock():
    assert classify_question("Какие подвои СК для юга?") == "rootstock"


def test_classify_pest_as_disease():
    assert classify_question("Как бороться с плодожоркой?") == "disease"


def test_classify_relief():
    assert classify_question("Террасы сливы в КБР") == "relief"


def test_diversify_fragments_limits_per_source():
    docs = [
        Document(page_content="a1", metadata={"source_file": "article1.txt"}),
        Document(page_content="a2", metadata={"source_file": "article1.txt"}),
        Document(page_content="a3", metadata={"source_file": "article1.txt"}),
        Document(page_content="b1", metadata={"source_file": "article2.txt"}),
        Document(page_content="c1", metadata={"source_file": "article3.txt"}),
    ]
    out = diversify_fragments(docs, limit=4, max_per_source=2)
    assert len(out) == 4
    assert sum(1 for d in out if d.metadata["source_file"] == "article1.txt") == 2


def test_diversify_preserves_relevance_order():
    docs = [
        Document(page_content="first", metadata={"source_file": "a.txt"}),
        Document(page_content="second", metadata={"source_file": "b.txt"}),
        Document(page_content="third", metadata={"source_file": "a.txt"}),
    ]
    out = diversify_fragments(docs, limit=2, max_per_source=1)
    assert out[0].page_content == "first"
    assert out[1].page_content == "second"
