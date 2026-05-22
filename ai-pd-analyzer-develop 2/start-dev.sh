#!/bin/bash
PROJECT_DIR="/home/kosinov.va/Projects/processing_schema/ai-pd-analyzer"
VENV_DIR="/home/kosinov.va/.venv"

cd "$PROJECT_DIR" || exit
source "$VENV_DIR/bin/activate"

# Основные настройки Flask
export FLASK_APP=src.wsgi
export FLASK_ENV=development

# Пути к данным
export OUTPUT_FOLDER="$PROJECT_DIR/outputs"
export UPLOAD_FOLDER="$PROJECT_DIR/uploads"
export SESSIONS_FILE="$PROJECT_DIR/outputs/sessions.json"
export DOCUMENTS_PATH="$PROJECT_DIR/data/documents.json"
export PERECHEN_PDF="$PROJECT_DIR/data/Perechen.xlsx"

# Настройки LLM
export OLLAMA_BASE_URL="http://localhost:11434"

# --- НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ АНАЛИЗА ЧЕРТЕЖЕЙ ---
export DRAWING_VLM_MODEL="gemma4:31b"
export DRAWING_VALIDATION_MODEL="gemma3:27b"
export DRAWING_MIN_SIZE_CM="42.0"
# ---------------------------------------------

# Создание необходимых директорий
mkdir -p "$PROJECT_DIR/outputs"
mkdir -p "$PROJECT_DIR/uploads"
mkdir -p "$PROJECT_DIR/data"
# Папки для чертежей будут создаваться динамически внутри сессий, 
# но можно создать общую структуру, если нужно
mkdir -p "$PROJECT_DIR/outputs/drawing_pages" 

# Запуск сервера
flask run --host=0.0.0.0 --port=6001