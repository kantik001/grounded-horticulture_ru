# Ветка `public-portfolio`

Подготовка репозитория к **публичному** GitHub (портфолио / трудоустройство).

## Что убрано из git (остаётся на `master` / локально)

| Категория | Файлы |
|-----------|--------|
| Журнальный корпус | `data/apple/*.txt`, `data/pear/*.txt`, `data/plum/*.txt` (кроме `sample_*.txt`, `README.txt`) |
| Архив | `data/_archive/` |
| Веса CV | `models/*.pth` (torchvision качает ImageNet сам) |
| Ingest PDF | `scripts/journal_*.py`, `restore_*.py`, `enrich_manual_articles.py` |
| Внутренние заметки | `docs/LEARNING_SESSION_*.md` |
| Аудит сливы | `eval/plum_miscategorized_audit.json`, `plum_miscategorized_audit.md` |

Файлы корпуса **остаются на диске** (если были) — только сняты с индекса git и добавлены в `.gitignore`.

## Что в публичном репо

- Весь код платформы (Go, Python RAG, webapp, eval JSONL, тесты, CI)
- `data/demo_hr/` — sandbox HR
- `data/apple/sample_*.txt` — демо для быстрого старта
- [DATA_LICENSE.md](DATA_LICENSE.md), [data/README.md](data/README.md)

## Имена репозиториев на GitHub

| Аудитория | Репозиторий | Статьи |
|-----------|-------------|--------|
| RU | `grounded-horticulture_ru` | Habr |
| EN | `grounded-horticulture` | dev.to |

Взаимные ссылки в README обоих репо.

## Запись демо (GIF для README)

1. **Чат:** http://localhost/ — ввести API-ключ из `.env` (`API_KEYS`), культура «Яблоня», вопросы:
   - «Какие признаки парши на листьях?»
   - «Какие подвои подходят для интенсивного сада?»
2. **Админка:** http://localhost/admin.html — логин `ADMIN_USER` / пароль `ADMIN_PASSWORD` из `.env`.
3. Сохранить записи в `docs/assets/demo-chat.mp4` и `docs/assets/demo-admin.mp4`.
4. Вставить в README (секция «Демо»).

Перед записью: дождаться healthy у classifier (~1–2 мин после старта), один тестовый вопрос «вхолостую».

## Публикация

```bash
git push -u origin public-portfolio
# на GitHub: сделать default branch или открыть PR в main
```

Перед push: убедитесь, что `.env` никогда не коммитился (`git log -- .env`).

## Вернуть полный корпус в git

Работайте на ветке `master` — там полный `data/` и ingest-скрипты.
