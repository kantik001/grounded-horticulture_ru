"""Gunicorn: production WSGI для classifier (1 worker + threads — общая память ML-моделей)."""

import os

bind = f"0.0.0.0:{os.environ.get('CLASSIFIER_PORT', '5000')}"
workers = max(1, int(os.environ.get("GUNICORN_WORKERS", "1")))
threads = max(1, int(os.environ.get("GUNICORN_THREADS", "4")))
timeout = max(30, int(os.environ.get("GUNICORN_TIMEOUT", "300")))
graceful_timeout = 30
keepalive = 5
worker_class = "gthread" if threads > 1 else "sync"
# PyTorch / sentence-transformers нельзя инициализировать в master до fork — deadlock в worker.
preload_app = False
accesslog = "-"
errorlog = "-"
capture_output = True


def post_fork(server, worker):
    """Прогрев RAG в worker-процессе, который обрабатывает /rag/context."""
    from rag.warmup import warmup_rag

    warmup_rag()
