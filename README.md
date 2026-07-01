# 🍏 grounded-horticulture — помощник садовода

**Grounded RAG** для садоводства: гибридный поиск по научным статьям, Telegram Mini App и веб-клиент с API-ключом.

> **Публичный репозиторий:** в git только демо-данные (`data/demo_hr/`, `data/apple/sample_*.txt`).
> Полный корпус статей и веса `.pth` — локально. См. [DATA_LICENSE.md](DATA_LICENSE.md), [data/README.md](data/README.md), [docs/PUBLIC_REPO.md](docs/PUBLIC_REPO.md).

Telegram Web App + AI: **фото** → классификация болезней (бета); **текст** → ответы по статьям (RAG). Оркестрация и LLM — **Go**, CV и гибридный retrieval (vector + BM25 + reranker) — **Python**.

Полный план развития: [`docs/ROADMAP.md`](docs/ROADMAP.md).  
**Универсальная платформа (ядро vs domain pack):** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DEPLOY.md`](docs/DEPLOY.md).  
**Портфолио / case study:** [`docs/AGRO_CASE_STUDY_RU.md`](docs/AGRO_CASE_STUDY_RU.md) (RU), [`docs/AGRO_CASE_STUDY_EN.md`](docs/AGRO_CASE_STUDY_EN.md) (EN).  
**Готовность к пилоту:** [`docs/PILOT_READINESS_AUDIT.md`](docs/PILOT_READINESS_AUDIT.md).  
База знаний по коду: [`docs/knowledge-base/README.md`](docs/knowledge-base/README.md).

## Описание

- Распознавание яблока/листа (**MobileNetV2** в Python) и рекомендации по фото (**Go** → LLM или шаблоны). **CV в бета-режиме:** без обученного `.pth` используется ImageNet backbone — см. `photo_beta_notice` в `config/branding.json`.
- Текстовые вопросы по статьям из **`data/`**: Python **только retrieval** (`/rag/context`), ответ собирает **Go** + LLM + верификация.
- **Telegram auth**: Web App передаёт `initData`, Go проверяет подпись бота (см. `server/auth_telegram.go`).
- **Browser / API auth**: заголовок `X-API-Key` (ключи в `API_KEYS` или `API_KEYS_FILE`) — для веб-клиентов без Telegram и внешних интеграций.

## Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────────┐
│  Telegram Web   │────▶│   Go Server      │────▶│ Python (Flask)              │
│  App + initData │◀────│  auth, rate limit│     │  /classify — CV             │
└─────────────────┘     │  /message (чат)  │────▶│  /rag/context — hybrid RAG  │
                          └────────┬────────┘     └─────────────────────────────┘
                                   │
                                   ▼  LLM (OpenRouter / OpenAI-compatible)
                            ┌──────────────┐
                            │  LLM API     │
                            └──────────────┘
```

## Структура каталогов

```
grounded-horticulture/
├── api/              # Flask: /classify, /rag/context, /health
├── cv/               # PyTorch MobileNetV2, registry, обучение
├── rag/              # Chroma + BM25 hybrid, reranker, retrieval
├── data/             # .txt статьи для RAG (в публичном git: demo_hr + sample_*.txt; полный корпус — локально)
├── server/           # Go: /message, /classify, RAG+LLM, сессии
├── config/           # crops, prompts, branding, onboarding, few_shot, question_categories, photo_templates, cv_class_labels
├── webapp/           # index.html, app.js, app.css, admin.html, nginx
├── eval/             # rag_*_baseline.jsonl, run_rag_eval.py
└── docker-compose.yml
```

## Технологии

### Python-сервис
- **MobileNetV2** + **PyTorch** — классификация изображений
- **Flask** — HTTP API (`/classify`, `/rag/context`, `/health`)
- **LangChain + Chroma + BM25 (rank-bm25) + cross-encoder reranker** — гибридный поиск по `data/` (e5 embeddings)

### Серверная часть (Go)
- **Gin** - веб-фреймворк
- **HTTP Client** - взаимодействие с Python сервисом и LLM API

### Клиентская часть
- **Telegram Web App** - кроссплатформенное приложение
- **HTML/CSS/JavaScript** - нативный веб-интерфейс

## Классы для распознавания (CV, яблоня)

**Пайплайн реализован; production-весов в репозитории нет** — для демо используйте текстовый RAG. После обучения (`cv/train_classifier.py`) модель распознаёт:
1. `healthy_apple` - Здоровое яблоко
2. `apple_scab` - Парша яблони
3. `black_rot` - Чёрная гниль
4. `cedar_apple_rust` - Кедрово-яблоневая ржавчина
5. `healthy_leaf` - Здоровый лист
6. `powdery_mildew` - Мучнистая роса
7. `fire_blight` - Бактериальный ожог
8. `bitter_rot` - Горькая гниль
9. `blue_mold` - Голубая плесень
10. `brown_rot` - Бурая гниль

## Процесс работы

**Фото:** снимок в чате → `POST /api/message` (multipart, поле `image`) → Go `classifyAndRecommend` → Python CV → LLM или шаблон из `photo_templates.json`. Отдельный `POST /classify` — для интеграций без сессии.

**Текст:** вопрос в чате → `POST /api/message` (JSON) → Go → Python `/rag/context` → LLM + verify. `POST /chat` **устарел** (заголовок `Deprecation`); используйте `/message` с сессией.

**Культуры:** `cv_enabled` / `rag_enabled` в `config/crops.json` проверяются на Go перед CV и RAG.

**Конфиг:** в Docker каталог `./config` смонтирован в `/config`; перезагрузка Go — `kill -HUP` или `CONFIG_RELOAD_INTERVAL_SEC`.

**Безопасность:** защищённые API требуют `X-Telegram-Init-Data` или `X-API-Key` (см. `.env.example`). Для локальной разработки: `TELEGRAM_AUTH_DISABLED=true` (только dev).  
**Метрики:** `GET /metrics` (Prometheus, без auth — ограничьте сеть на проде).

## Установка и запуск

### Вариант 1: Локальная установка (для разработки)

#### 1. Установка зависимостей Python

```bash
pip install -r cv/requirements.txt
```

**Примечание:** Для установки PyTorch с поддержкой CUDA посетите https://pytorch.org/get-started/locally/

#### 2. Настройка переменных окружения

Скопируйте файл `.env.example` в корень проекта:

```bash
cp .env.example .env
```

Отредактируйте `.env` при необходимости:

См. **`.env.example`**: `TELEGRAM_BOT_TOKEN`, **`API_KEYS`** / **`API_KEYS_FILE`** (браузер без Telegram), **`LLM_API_KEY`**, `HF_TOKEN` (ускорение загрузки моделей HF) (ключ OpenRouter или другого OpenAI-совместимого API; переменная `OPENROUTER_API_KEY` не используется), `DATABASE_URL`, `UPLOAD_DIR`, `CLASSIFIER_URL`, `CLASSIFIER_RAG_URL`, `CORS_ALLOWED_ORIGINS`, `RATE_LIMIT_REQUESTS_PER_MINUTE`.

**Локальная разработка без Telegram:** в `.env` задайте `TELEGRAM_AUTH_DISABLED=true` (только dev, не для продакшена).

**Продакшен:** укажите `TELEGRAM_BOT_TOKEN` от @BotFather **или** задайте `API_KEYS` для браузерного доступа; в `CORS_ALLOWED_ORIGINS` добавьте URL вашего Web App (например `https://your-domain.com`).

#### 3. Запуск Python сервиса классификации

```bash
python api/app.py
```

Сервис запустится на порту 5000.

**Важно:** Собственные веса болезней — через `cv/train_classifier.py` → `models/apple_classifier.pth`.
Без `.pth` используется **ImageNet backbone** (torchvision скачивает веса при первом запуске).

#### 4. Установка зависимостей Go

```bash
cd server
go mod download
```

#### 5. Запуск Go сервера

```bash
cd server
go run .
```

Сервер запустится на порту 8080 и автоматически загрузит `.env` файл из директории `server/`.

#### 6. Размещение Web App

Разместите файл `webapp/index.html` на любом HTTPS хостинге (GitHub Pages, Vercel, Netlify и т.д.)

В файле `index.html` замените `YOUR_SERVER_URL` на адрес вашего Go сервера (например, `https://your-domain.com`).

### Вариант 2: Docker Compose (рекомендуется для продакшена)

#### 1. Подготовка

Убедитесь, что у вас установлены Docker и Docker Compose.

Создайте файл `.env` в корне проекта:

```bash
cp .env.example .env
```

#### 2. Запуск всех сервисов

```bash
docker compose up -d --build
```

Команды поднимут четыре контейнера (проект Compose: `union_ai_apple`):
- `union_ai_apple_postgres` (PostgreSQL)
- `union_ai_apple_classifier` (Python, порт 5000)
- `union_ai_apple_server` (Go, порт 8080)
- `union_ai_apple_webapp` (Nginx, порт 80)

После смены статей: `make docker-reindex-apply` (reindex в volumes `chroma_data` + `bm25_data` + restart classifier). На Windows локальный `make reindex` может падать на Chroma — используйте Docker.

#### 3. Проверка статуса

```bash
docker compose ps
docker compose logs -f
make smoke          # API на :8080, нужен TELEGRAM_AUTH_DISABLED=true в .env
```

#### 4. Остановка

```bash
docker compose down
```

## Обучение модели

Для обучения классификатора на собственных данных:

1. Подготовьте датасет со структурой:
```
data/
├── train/
│   ├── healthy_apple/
│   ├── apple_scab/
│   └── ...
└── val/
    ├── healthy_apple/
    ├── apple_scab/
    └── ...
```

2. Запустите обучение:
```bash
cd cv
python train_classifier.py
```

3. Отредактируйте `cv/train_classifier.py` для указания путей к данным

## API Endpoints

### Go Server

#### POST /classify
Загрузка изображения для анализа

**Request:**
- Content-Type: multipart/form-data
- Body: image (file)

**Response:**
```json
{
  "success": true,
  "prediction": "healthy_apple",
  "confidence": 0.95,
  "top_predictions": [
    {"label": "healthy_apple", "confidence": 0.95},
    {"label": "healthy_leaf", "confidence": 0.03}
  ],
  "recommendation": "🍎 Здоровое яблоко обнаружено!..."
}
```

#### GET /health
Проверка работоспособности сервера

#### POST /chat (устарел)
Одиночный RAG-вопрос без сессии. Ответ с заголовком `Deprecation: true`. Используйте **`POST /message`** (ниже).

#### POST /session, GET /history, POST /message
Чат с историей (**основной UI**). Требуют `X-Telegram-Init-Data`.

**POST /message:** JSON `{session_id, text, crop_id?}` или multipart (`session_id`, `text`, `image`, `crop_id?`). Фото → CV + рекомендация; текст → RAG + LLM. Проверяются `cv_enabled` / `rag_enabled` из `crops.json`.

### Python Classifier Service

#### POST /classify
Классификация изображения

**Request:**
- Content-Type: multipart/form-data
- Body: image (file)

**Response:**
```json
{
  "success": true,
  "prediction": "healthy_apple",
  "confidence": 0.95,
  "top_predictions": [...]
}
```

#### POST /rag/context
Гибридный поиск (vector + BM25 + reranker); возвращает `context`, `fragments`, `few_shot` для сборки ответа в Go.

**Request:** `{"question": "текст"}`  
**Response:** `{"success": true, "context": "...", "fragments": [...], ...}`

## Требования к изображениям

- Формат: JPEG, PNG
- Максимальный размер: 10 MB
- Рекомендуемое разрешение: от 224x224 пикселей

## Конфигурация LLM

- **И текст RAG, и советы по фото:** `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` в Go (см. `.env.example`). Без ключа по фото — шаблоны; текстовый чат вернёт ошибку о необходимости ключа.

## Демо

### Чат (текстовый RAG)

<video src="docs/assets/demo-chat.mp4" controls width="720"></video>

### Админка (статьи и обратная связь)

<video src="docs/assets/demo-admin.mp4" controls width="720"></video>

Сценарий записи: [docs/PUBLIC_REPO.md](docs/PUBLIC_REPO.md).

## Лицензия

Исходный код — [Apache License 2.0](LICENSE).

Тексты в `data/` — см. [DATA_LICENSE.md](DATA_LICENSE.md) (отдельно от лицензии на код).

## Контакты

Для вопросов и предложений создайте issue в репозитории проекта.
