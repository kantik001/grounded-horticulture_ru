"""Embeddings для multilingual-e5: обязательные префиксы query:/passage:."""

E5_MODEL = "intfloat/multilingual-e5-small"

_embeddings = None


def _passage(text: str) -> str:
    t = (text or "").strip()
    if t.lower().startswith("passage:"):
        return t
    return f"passage: {t}"


def _query(text: str) -> str:
    t = (text or "").strip()
    if t.lower().startswith("query:"):
        return t
    return f"query: {t}"


def reset_embeddings() -> None:
    """Сброс кэша (тесты, смена модели)."""
    global _embeddings
    _embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    from langchain_huggingface import HuggingFaceEmbeddings

    class E5Embeddings(HuggingFaceEmbeddings):
        """intfloat/multilingual-e5-small ожидает префиксы при индексации и поиске."""

        def embed_documents(self, texts):
            return super().embed_documents([_passage(t) for t in texts])

        def embed_query(self, text):
            return super().embed_query(_query(text))

    _embeddings = E5Embeddings(model_name=E5_MODEL)
    return _embeddings
