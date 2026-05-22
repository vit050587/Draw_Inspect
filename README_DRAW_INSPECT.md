# Draw_Inspect - Сервис анализа чертежей

## Запуск на сервере (локальная разработка)

1. Подключитесь к серверу по SSH
2. Запустите скрипт разработки:
   ```bash
   ./start-dev.sh
   ```
3. В отдельном терминале на локальной машине запустите туннель:
   ```bash
   ./tunnel.sh
   ```
4. Откройте в браузере: `http://localhost:8081`

**Порты:**
- Серверный порт: 6002
- Локальный порт (через туннель): 8081

## Запуск в Docker

```bash
docker-compose up --build
```

Сервис будет доступен на `http://localhost:6002` (только localhost, не доступно извне)

## Конфликт портов с другим сервисом

Этот сервис использует порты, которые не конфликтуют с `ai-pd-analyzer-develop 2`:

| Сервис | Серверный порт | Локальный порт (туннель) | Docker порт |
|--------|---------------|-------------------------|-------------|
| ai-pd-analyzer-develop 2 | 6001 | 8080 | 6000 |
| draw_inspect (этот) | 6002 | 8081 | 6002 |

## Структура проекта

```
/workspace/
├── backend/          # Flask приложение
│   └── app.py
├── frontend/         # HTML интерфейс
│   └── index.html
├── scripts/          # Скрипты анализа
│   ├── classifier.py
│   ├── vlm_analyzer.py
│   ├── llm_responder.py
│   └── pdf_processor.py
├── uploads/          # Загруженные файлы (создается автоматически)
├── outputs/          # Результаты анализа (создается автоматически)
├── start-dev.sh      # Скрипт запуска на сервере
├── tunnel.sh         # Скрипт SSH туннеля
├── Dockerfile        # Docker образ
└── docker-compose.yml # Docker Compose конфигурация
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и настройте при необходимости:

```bash
cp .env.example .env
```

Основные переменные:
- `FLASK_APP` - путь к Flask приложению
- `UPLOAD_FOLDER` - папка для загруженных файлов
- `OUTPUT_FOLDER` - папка для результатов
- `OLLAMA_BASE_URL` - URL Ollama API
- `DRAWING_VLM_MODEL` - модель для анализа чертежей
- `DRAWING_VALIDATION_MODEL` - модель для валидации
- `DRAWING_MIN_SIZE_CM` - минимальный размер чертежа в см
