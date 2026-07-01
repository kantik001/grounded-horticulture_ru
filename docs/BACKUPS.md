# Резервное копирование (Docker volumes)

Рекомендуемое расписание для **продакшена**: ежедневный бэкап + хранение 7–14 дней.  
Имена volumes задаются в [`docker-compose.yml`](../docker-compose.yml) (проект `union_ai_apple`).

| Volume Compose | Содержимое | Критичность |
|----------------|------------|-------------|
| `postgres_data` | Сессии, сообщения, feedback, analytics | **Высокая** |
| `chroma_data` | Векторный индекс RAG (Chroma) | **Высокая** (пересобирается из `data/`, но долго) |
| `bm25_data` | BM25 индекс | **Высокая** (пересобирается из `data/`) |
| `uploads_data` | Фото пользователей в чате | Средняя |
| `models` | CV-веса `.pth` | Низкая (если нет кастомных весов) |

---

## PostgreSQL

```bash
# Создать дамп (контейнер postgres должен работать)
docker compose -p union_ai_apple exec -T postgres \
  pg_dump -U gardener -d gardener -Fc > backups/postgres_$(date +%Y%m%d).dump

# Восстановление (осторожно: перезапишет БД)
docker compose -p union_ai_apple exec -T postgres \
  pg_restore -U gardener -d gardener --clean --if-exists < backups/postgres_YYYYMMDD.dump
```

Альтернатива без `exec`: `pg_dump` с хоста по `DATABASE_URL` / порту `5432` (если проброшен).

---

## Chroma и BM25

Индексы лежат в volumes classifier-сервиса. Бэкап — архив каталогов из контейнера или volume snapshot.

```bash
# Пример: tar из running classifier (пути внутри образа)
docker compose -p union_ai_apple exec classifier \
  tar -czf - /app/chroma_db /app/bm25_db > backups/rag_indexes_$(date +%Y%m%d).tar.gz
```

**Восстановление после потери:** смонтировать архив или выполнить переиндексацию:

```bash
make docker-reindex-apply
# или: python scripts/reindex_rag.py (classifier остановлен)
```

Переиндексация из `data/` занимает время (e5 + BM25); бэкап индексов ускоряет recovery.

---

## Uploads (фото в чате)

```bash
docker compose -p union_ai_apple exec server \
  tar -czf - /data/uploads > backups/uploads_$(date +%Y%m%d).tar.gz
```

---

## Проверка бэкапов

Раз в месяц: восстановить дамп Postgres в тестовый контейнер и открыть 1–2 сессии; для RAG — smoke `python scripts/run_rag_eval.py --suite apple --fast --in-process` на восстановленном индексе.

---

## Связанные документы

- [DEPLOY.md](../DEPLOY.md)
- [knowledge-base/docker-overview.md](./knowledge-base/docker-overview.md)
- [knowledge-base/metrics-and-alerts.md](./knowledge-base/metrics-and-alerts.md)
