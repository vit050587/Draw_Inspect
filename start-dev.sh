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

# --- ПРОВЕРКА ПОДКЛЮЧЕНИЯ К МОДЕЛЯМ OLLAMA ---
echo "🔍 Проверка подключения к Ollama серверу..."

# Проверка доступности Ollama API
if ! curl -s "${OLLAMA_BASE_URL}/api/tags" > /dev/null 2>&1; then
    echo "❌ Ошибка: Не удалось подключиться к Ollama серверу по адресу ${OLLAMA_BASE_URL}"
    echo "   Убедитесь, что Ollama запущен: ollama serve"
    exit 1
fi

echo "✅ Ollama сервер доступен по адресу ${OLLAMA_BASE_URL}"

# Функция проверки модели
check_model() {
    local model_name=$1
    local model_type=$2
    
    echo "   Проверка модели ${model_type}: ${model_name}..."
    
    # Получаем список доступных моделей
    if curl -s "${OLLAMA_BASE_URL}/api/tags" | grep -q "\"name\":\"${model_name}\""; then
        echo "   ✅ Модель ${model_name} доступна"
        return 0
    else
        # Проверяем, есть ли модель с таким префиксом (например, gemma4:31b может быть как gemma4)
        if curl -s "${OLLAMA_BASE_URL}/api/tags" | grep -q "\"name\":\"${model_name%:*}\""; then
            echo "   ⚠️  Точная версия ${model_name} не найдена, но есть модель с префиксом ${model_name%:*}"
            return 0
        else
            echo "   ❌ Модель ${model_name} НЕ найдена в списке доступных моделей"
            echo "      Доступные модели:"
            curl -s "${OLLAMA_BASE_URL}/api/tags" | grep -oP '"name":"\K[^"]+' | sed 's/^/         - /'
            echo ""
            echo "      Для загрузки модели выполните: ollama pull ${model_name}"
            return 1
        fi
    fi
}

# Проверка моделей
VLM_MODEL_OK=true
VALIDATION_MODEL_OK=true

check_model "$DRAWING_VLM_MODEL" "VLM (анализ чертежей)" || VLM_MODEL_OK=false
check_model "$DRAWING_VALIDATION_MODEL" "Validation (классификация)" || VALIDATION_MODEL_OK=false

echo ""

# Предупреждение если модели недоступны
if [ "$VLM_MODEL_OK" = false ] || [ "$VALIDATION_MODEL_OK" = false ]; then
    echo "⚠️  Внимание: Одна или несколько моделей недоступны."
    echo "   Сервис может работать некорректно."
    echo ""
    read -p "Продолжить запуск Flask сервера? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Запуск отменен."
        exit 1
    fi
    echo "Продолжение запуска..."
else
    echo "✅ Все модели доступны. Запуск сервера..."
fi

echo ""
# ---------------------------------------------

# Запуск сервера на порту 6002 (чтобы не конфликтовал с другим сервисом на 6001)
flask run --host=0.0.0.0 --port=6002
