#!/bin/bash
PROJECT_DIR="/home/kosinov.va/Projects/processing_schema/Draw_Inspect"
VENV_DIR="/home/kosinov.va/Projects/processing_schema/Draw_Inspect.venv"

cd "$PROJECT_DIR" || exit

# Проверка и активация venv (если существует)
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

# Основные настройки Flask
export FLASK_APP=backend/app.py
export FLASK_ENV=development

# Пути к данным
export UPLOAD_FOLDER="$PROJECT_DIR/uploads"
export OUTPUT_FOLDER="$PROJECT_DIR/outputs"

# Настройки LLM (для совместимости с другим сервисом)
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

# --- НАСТРОЙКИ ДЛЯ АНАЛИЗА ЧЕРТЕЖЕЙ ---
export DRAWING_VLM_MODEL="${DRAWING_VLM_MODEL:-gemma4:31b}"
export DRAWING_VALIDATION_MODEL="${DRAWING_VALIDATION_MODEL:-gemma3:27b}"
export DRAWING_MIN_SIZE_CM="${DRAWING_MIN_SIZE_CM:-42.0}"
# --------------------------------------

# Создание необходимых директорий
mkdir -p "$UPLOAD_FOLDER"
mkdir -p "$OUTPUT_FOLDER"

# Запуск сервера на порту 6002 (чтобы не конфликтовал с другим сервисом на 6001)
flask run --host=0.0.0.0 --port=6002
