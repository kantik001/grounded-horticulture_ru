# База знаний RAG (`data/`)

## Публичный репозиторий

В git **не включён** полный корпус статей журнала ПВЮР (~500 файлов) — только:

| Каталог | В репо | Назначение |
|---------|--------|------------|
| `demo_hr/` | ✅ | Sandbox платформы (HR-политики) |
| `apple/sample_*.txt` | ✅ | Демо-статьи для быстрого старта |
| `pear/`, `plum/` | README | Добавьте свои `.txt` локально |
| `apple/*.txt` (кроме sample) | ❌ gitignore | Положите локально для полного RAG |

После добавления статей:

```bash
docker compose -p union_ai_apple stop classifier
docker compose -p union_ai_apple run --rm -e FORCE_RAG_REINDEX=true classifier python scripts/reindex_rag.py
docker compose -p union_ai_apple start classifier
```

Полный eval (`python scripts/run_rag_eval.py --suite all`) рассчитан на полный корпус — на демо-данных пройдёт только часть вопросов.

## Формат файла `.txt`

Каждая статья — отдельный файл в `data/{crop_id}/`. Рекомендуемая структура:

```
Метаданные источника:
- Заголовок: ...
- URL: ... (опционально)

Основной текст статьи...
```

## Права на контент

Не публикуйте в открытый git чужие тексты без разрешения правообладателя.  
См. [DATA_LICENSE.md](../DATA_LICENSE.md).
