# Draw_Inspect

Сервис для анализа чертежей и технической документации с использованием мультимодальных LLM (Ollama).

## Описание

Draw_Inspect — это веб-приложение, которое позволяет загружать PDF-файлы с чертежами, автоматически определять страницы с чертежами, анализировать их содержимое с помощью локальной VLM (gemma4:31b) и классифицировать элементы по строительному справочнику с валидацией через LLM (gemma3:27b). Приложение извлекает только страницы с чертежами (размером >30 см), игнорируя текстовые документы и спецификации.

## Возможности

- 📄 **Автоматическое определение чертежей** — извлечение только страниц с чертежами из PDF (порог: 30 см)
- 🔄 **Коррекция ориентации** — автоматический поворот страниц для правильного анализа
- 🖼️ **Поддержка изображений** — загрузка чертежей в формате изображений (PNG, JPG, JPEG)
- 🤖 **AI-анализ** — ответы на вопросы по содержимому чертежей с использованием VLM (gemma4:31b)
- 🏗️ **Классификация элементов** — сопоставление обнаруженных элементов со строительным справочником (10352 записи)
- 📊 **Экспорт результатов** — выгрузка классифицированных элементов в Excel и JSON
- 🔒 **Локальная работа** — все вычисления выполняются локально через Ollama
- 🐳 **Docker-поддержка** — быстрый запуск в контейнере

## Структура проекта

```
Draw_Inspect/
├── backend/              # Flask-приложение
│   └── app.py           # Основной сервер (API endpoints)
├── frontend/            # Веб-интерфейс
│   └── index.html       # Single-page приложение (CSS/JS встроенные)
├── scripts/             # Скрипты анализа
│   ├── drawing_detector.py    # Определение страниц с чертежами, коррекция ориентации
│   ├── page_analyzer.py       # Анализ страниц через VLM (gemma4:31b)
│   ├── response_generator.py  # Генерация структурированного ответа
│   └── element_classifier.py  # Классификация элементов по справочнику + LLM валидация
├── data/                # Справочники для классификации
│   ├── elements.json    # Полный справочник элементов (10352 строки)
│   ├── class.json       # Справочник классов (379 записей, JSON Lines)
│   ├── subclass.json    # Справочник подклассов (906 записей)
│   ├── purpose.json     # Справочник назначений (61 запись)
│   └── category.json    # Справочник категорий (10 записей)
├── uploads/             # Загруженные файлы (сессии)
├── outputs/             # Результаты обработки
├── docker-compose.yml   # Docker Compose конфигурация
├── Dockerfile           # Docker образ
├── requirements.txt     # Python зависимости
├── start-dev.sh         # Скрипт запуска для разработки
└── tunnel.sh            # SSH туннель для удалённого доступа
```

## Требования

- Python 3.10+
- Ollama с установленными моделями:
  - `gemma4:31b` — мультимодальная модель для анализа чертежей (VLM)
  - `gemma3:27b` — текстовая модель для валидации и классификации элементов
- Для работы с PDF: `poppler-utils`
- Для обработки изображений: `libgl1`, `libglib2.0-0`

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd Draw_Inspect
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Установка системных пакетов (для Linux)

```bash
sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-0 poppler-utils
```

## Настройка

Переменные окружения (настраиваются в `start-dev.sh` или `.env`):

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `UPLOAD_FOLDER` | Папка для загруженных файлов | `./uploads` |
| `OUTPUT_FOLDER` | Папка для результатов | `./outputs` |
| `OLLAMA_BASE_URL` | URL Ollama API | `http://localhost:11434` |
| `DRAWING_VLM_MODEL` | Модель для анализа чертежей (VLM) | `gemma4:31b` |
| `DRAWING_VALIDATION_MODEL` | Модель для валидации и классификации | `gemma3:27b` |
| `DRAWING_MIN_SIZE_CM` | Минимальный размер чертежа (см) | `30.0` |
| `MAX_UPLOAD_MB` | Максимальный размер загрузки (МБ) | `1024` |

**Примечание:** Файл `.env` отсутствует по умолчанию. Все переменные задаются в `start-dev.sh` или через `docker-compose.yml`.

## Запуск

### Режим разработки

```bash
chmod +x start-dev.sh
./start-dev.sh
```

Приложение будет доступно по адресу: http://localhost:6002

### Docker

```bash
docker-compose up --build
```

Приложение будет доступно по адресу: http://localhost:6002

### Через SSH туннель

Для доступа к удалённому экземпляру:

```bash
chmod +x tunnel.sh
./tunnel.sh
```

Затем откройте: http://localhost:8081

## API

### Загрузка файлов

**POST** `/api/upload`

Загружает файлы (PDF или изображения) для анализа. Автоматически определяет страницы с чертежами (>30 см) и извлекает их в отдельные PDF-файлы.

**Тело запроса:** `multipart/form-data` с файлами в поле `files`

**Ответ:**
```json
{
  "session_id": "uuid",
  "total_pages": 5,
  "drawing_pages": 3
}
```

### Анализ чертежей

**POST** `/api/analyze`

Анализирует загруженные чертежи с заданным вопросом. Выполняет:
1. Конвертацию страниц в изображения
2. Отправку в VLM модель (gemma4:31b)
3. Генерацию структурированного ответа
4. Классификацию элементов по справочнику
5. Создание Excel-отчёта

**Тело запроса:**
```json
{
  "session_id": "uuid",
  "question": "Опиши основные размеры на чертеже"
}
```

**Ответ:**
```json
{
  "status": "completed",
  "response": "На чертеже представлены...",
  "analysis": [...],
  "classified_elements_count": 15,
  "download_url": "/api/download/<session_id>/classified_elements.xlsx"
}
```

### Скачивание результатов

**GET** `/api/download/<session_id>/<filename>`

Скачивает файл результатов классификации (Excel или JSON).

**Параметры:**
- `session_id` — идентификатор сессии
- `filename` — имя файла (`classified_elements.xlsx` или `classified_elements.json`)

### Получение справочников

**GET** `/data/<filename>`

Возвращает JSON-справочник для использования во фронтенде.

**Доступные файлы:**
- `class.json` — справочник классов (379 записей)
- `subclass.json` — справочник подклассов (906 записей)
- `purpose.json` — справочник назначений (61 запись)
- `category.json` — справочник категорий (10 записей)

## Использование

### Через веб-интерфейс

1. Откройте приложение в браузере (http://localhost:6002)
2. Загрузите PDF-файл с чертежами или изображения (PNG, JPG, JPEG)
3. Система автоматически определит и извлечёт страницы с чертежами (>30 см)
4. Введите вопрос по содержимому чертежей
5. Получите AI-ответ на основе анализа
6. При необходимости скачайте Excel-файл с классифицированными элементами

### Через API

```bash
# 1. Загрузка файлов
curl -X POST http://localhost:6002/api/upload \
  -F "files=@drawing1.pdf" \
  -F "files=@drawing2.png"

# Ответ: {"session_id": "abc-123", "total_pages": 5, "drawing_pages": 3}

# 2. Анализ чертежей
curl -X POST http://localhost:6002/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123", "question": "Перечисли все размеры на чертеже"}'

# Ответ: {"status": "completed", "response": "...", "download_url": "/api/download/abc-123/classified_elements.xlsx"}

# 3. Скачивание результатов
curl -O http://localhost:6002/api/download/abc-123/classified_elements.xlsx
```

## Поток данных (Data Flow)

### Загрузка файлов
```
POST /api/upload 
  → Сохранение в uploads/<session_id>/
  → extract_drawing_pages_to_pdf() → извлечение страниц >30см в uploads/<session_id>/pages/
  → Сохранение pages_info.json с метаданными
```

### Анализ
```
POST /api/analyze
  → analyze_pages() → PDF→PNG конвертация → ollama.chat(gemma4:31b) → парсинг JSON
  → Сохранение analysis_results.json
  → generate_response() → формирование текстового ответа
  → classify_elements() → сопоставление с elements.json → создание Excel
  → Сохранение results.json и classified_elements.xlsx
```

## Структура сессии

Каждая сессия хранения в `uploads/<session_id>/`:

```
uploads/<session_id>/
├── files/                  # Исходные загруженные файлы
├── pages/                  # Извлеченные страницы-чертежи (PDF)
├── request.json            # Метаданные запроса (session_id, question, status)
├── pages_info.json         # Информация о страницах (размеры, ориентация)
├── analysis_results.json   # Результаты анализа страниц (JSON от VLM)
├── results.json            # Полный ответ (вопрос, анализ, ответ, классификация)
├── classified_elements.json # JSON классификации элементов
└── classified_elements.xlsx # Excel таблица для скачивания
```

## Зависимости

### Python пакеты

| Пакет | Версия | Назначение |
|-------|--------|------------|
| Flask | 3.0.0 | Веб-фреймворк |
| flask-cors | 4.0.0 | Поддержка CORS |
| PyMuPDF | 1.23.8 | Работа с PDF (извлечение страниц, размеры) |
| ollama | 0.6.2 | Интеграция с Ollama API |
| Pillow | 10.0.0 | Обработка изображений |
| pdf2image | 1.16.3 | Конвертация PDF в PNG для VLM |
| openpyxl | >=3.1.5 | Создание Excel-отчётов |
| pandas | 2.1.4 | Обработка данных классификации |

### Системные пакеты (Linux)

```bash
sudo apt-get install -y libgl1 libglib2.0-0 poppler-utils
```

- `libgl1`, `libglib2.0-0` — для обработки изображений (Pillow)
- `poppler-utils` — для конвертации PDF в изображения (pdf2image)

## Архитектура

### Компоненты системы

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend        │────▶│   Scripts       │
│   (index.html)  │◀────│   (Flask app.py) │◀────│   (analysis)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                        │
                                ▼                        ▼
                         ┌──────────────────┐     ┌─────────────────┐
                         │   Data Files     │     │   Ollama API    │
                         │   ( справочники) │     │   (gemma4:31b,  │
                         └──────────────────┘     │    gemma3:27b)  │
                                                  └─────────────────┘
```

### Модули анализа

1. **drawing_detector.py** — детекция чертежей по размеру (>30 см), коррекция ориентации
2. **page_analyzer.py** — анализ страниц через VLM (gemma4:31b), извлечение элементов
3. **response_generator.py** — генерация структурированного текстового ответа
4. **element_classifier.py** — классификация элементов по справочнику + LLM валидация (gemma3:27b)

## Граф вызовов

```
backend/app.py
├── GET / → serve_frontend()
├── GET /data/<filename> → serve_data(filename)
├── POST /api/upload → upload_files()
│   └── scripts/drawing_detector.extract_drawing_pages_to_pdf()
├── POST /api/analyze → analyze()
│   ├── scripts/page_analyzer.analyze_pages()
│   │   └── ollama.chat(model=gemma4:31b)
│   ├── scripts/response_generator.generate_response()
│   │   └── ollama.chat()
│   └── scripts/element_classifier.classify_elements()
│       ├── find_local_match() (поиск по справочнику)
│       └── ollama.chat(model=gemma3:27b) (валидация)
└── GET /api/download/<session_id>/<filename> → download_file()
```

## Режимы работы

- **Синхронный HTTP** — все запросы обрабатываются в режиме request/response
- **Без фоновых задач** — нет cron, Celery, APScheduler
- **Однопоточный режим** — Flask development server (для prod использовать Gunicorn через Docker)

## Лицензия

Проприетарное ПО

## Контакты

Для вопросов и предложений обращайтесь к разработчикам проекта.

## Changelog

### Версия 1.0

- ✅ Загрузка PDF и изображений чертежей
- ✅ Автоматическое определение страниц с чертежами (>30 см)
- ✅ Коррекция ориентации страниц
- ✅ Анализ через VLM (gemma4:31b)
- ✅ Классификация элементов по справочнику (10352 записи)
- ✅ Валидация через LLM (gemma3:27b)
- ✅ Экспорт результатов в Excel и JSON
- ✅ Single-page веб-интерфейс
- ✅ Docker-поддержка
