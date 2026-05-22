"""
Модуль классификации чертежей с использованием модели gemma4:31b через Ollama.
Классифицирует страницы с чертежами по категориям из config/classification_rules.json.
"""

import os
import re
import json
import base64
import time
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF для работы с PDF
import ollama

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================

def setup_logging():
    # Используем путь относительно текущего файла
    current_dir = Path(__file__).resolve().parent  # scripts/
    project_dir = current_dir.parent  # корень проекта (Draw_Inspect)
    log_dir = project_dir / 'outputs' / 'logs'
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'drawing_classifier.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

# Конфигурация Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CLASSIFICATION_MODEL = os.getenv("DRAWING_CLASSIFICATION_MODEL", "gemma4:31b")

# Настройки для стабильности
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
REQUEST_DELAY = 2  # Пауза между запросами (2 секунды)

# Пути к файлам конфигурации и промптов
PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_DIR / 'config'
PROMPTS_DIR = PROJECT_DIR / 'prompts'

CLASSIFICATION_RULES_FILE = CONFIG_DIR / 'classification_rules.json'
CLASSIFICATION_PROMPT_FILE = PROMPTS_DIR / 'classification_prompt.txt'

logger.info("="*80)
logger.info("ЗАПУСК КЛАССИФИКАЦИИ ЧЕРТЕЖЕЙ")
logger.info("="*80)
logger.info(f"Модель: {CLASSIFICATION_MODEL}")
logger.info(f"Пауза между запросами: {REQUEST_DELAY} сек")
logger.info(f"🔌 Подключение к Ollama: {OLLAMA_URL}")


def load_classification_rules() -> Dict[str, Any]:
    """Загружает правила классификации из JSON файла"""
    try:
        with open(CLASSIFICATION_RULES_FILE, 'r', encoding='utf-8') as f:
            rules = json.load(f)
            logger.info(f"✅ Загружены правила классификации из {CLASSIFICATION_RULES_FILE}")
            return rules
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки правил из {CLASSIFICATION_RULES_FILE}: {e}")
        # Возвращаем дефолтные правила
        return {
            "categories": {
                "building_elevation": {"folder_name": "01_building_elevation"},
                "residential_floor_plan": {"folder_name": "02_residential_floor_plan"},
                "non_residential_floor_plan": {"folder_name": "03_non_residential_floor_plan"},
                "technical_floor": {"folder_name": "04_technical_floor"},
                "parking_floor": {"folder_name": "05_parking_floor"},
                "other": {"folder_name": "06_other"}
            },
            "default_categories": ["building_elevation", "residential_floor_plan", "non_residential_floor_plan", 
                                   "technical_floor", "parking_floor", "other"]
        }


def load_classification_prompt() -> str:
    """Загружает промпт классификации из файла"""
    try:
        with open(CLASSIFICATION_PROMPT_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки промпта из {CLASSIFICATION_PROMPT_FILE}: {e}")
        # Возвращаем дефолтный промпт в случае ошибки
        return """Вы эксперт в области архитектурных чертежей и планов зданий.

Внимательно проанализируйте изображение и определите тип чертежа.

Классифицируйте этот чертеж в одну из следующих категорий:
- building_elevation (все здание вид сбоку/фасад)
- residential_floor_plan (план этажа вид сверху жилые этажи с квартирами)  
- non_residential_floor_plan (план этажа вид сверху нежилые этажи: офисы, магазины, коммерция)
- technical_floor (технический этаж с инженерным оборудованием, вентиляцией, насосами)
- parking_floor (план здания вид сверху парковка с машиноместами)
- other (другое: схемы, разрезы, детали, не подходящие под категории выше)

Отвечайте ТОЛЬКО названием категории на английском из списка выше, без пояснений.
Пример ответа: residential_floor_plan
"""


def pdf_to_base64(pdf_path: str) -> str:
    """Конвертирует PDF страницу в base64 PNG для отправки модели"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        
        # Используем матрицу 1:1 для сохранения фактического разрешения страницы
        mat = fitz.Matrix(1, 1)
        
        # Рендерим страницу в pixmap с полным разрешением
        pix = page.get_pixmap(matrix=mat)
        
        # Конвертируем в PNG байты
        img_data = pix.tobytes("png")
        
        doc.close()
        
        size_mb = len(img_data) / (1024 * 1024)
        logger.info(f"      📐 Размер изображения: {pix.width}x{pix.height} ({size_mb:.1f} МБ)")
        
        return base64.b64encode(img_data).decode("utf-8")
    except Exception as e:
        logger.error(f"❌ Ошибка конвертации изображения {pdf_path}: {e}")
        return None


def create_classification_prompt() -> str:
    """Возвращает промпт классификации из файла"""
    return load_classification_prompt()


def classify_single_page(page_path: str, client: ollama.Client) -> str:
    """
    Классифицирует одну страницу с чертежом.
    Возвращает название категории или None в случае ошибки.
    """
    try:
        # Конвертируем PDF в base64
        logger.info(f"      🧠 Конвертация PDF страницы в base64...")
        b64 = pdf_to_base64(page_path)
        if not b64:
            return None
        
        prompt = create_classification_prompt()
        
        logger.info(f"      🧠 Отправка запроса модели {CLASSIFICATION_MODEL}...")
        
        start_time = time.time()
        response = client.chat(
            model=CLASSIFICATION_MODEL,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [b64]
            }],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 100}
        )
        elapsed_time = time.time() - start_time
        logger.info(f"      ⏱️ Модель отвечала {elapsed_time:.1f} секунд")
        
        category = response['message']['content'].strip().lower()
        logger.info(f"      📋 Получен ответ: {category}")
        
        # Очищаем категорию от лишних символов и ищем совпадения
        valid_categories = [
            'building_elevation',
            'residential_floor_plan', 
            'non_residential_floor_plan',
            'technical_floor',
            'parking_floor',
            'other'
        ]
        
        for cat in valid_categories:
            if cat in category:
                logger.info(f"      ✅ Распознана категория: {cat}")
                return cat
        
        # Если категория не распознана, помещаем в other
        logger.warning(f"      ⚠️ Категория не распознана, назначаем 'other'")
        return 'other'
        
    except Exception as e:
        logger.error(f"      ❌ Ошибка классификации страницы {page_path}: {e}")
        return None


def classify_drawings(session_id: str, pages_folder: str, output_folder: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Классифицирует изображения чертежей по категориям и распределяет по папкам.
    
    Args:
        session_id: ID сессии
        pages_folder: Папка с PDF страницами для классификации (uploads/{session_id}/pages)
        output_folder: Базовая папка для сохранения классифицированных изображений (uploads/{session_id})
        
    Returns:
        Словарь с категориями и списками изображений в каждой
    """
    # Загружаем правила классификации из JSON
    rules = load_classification_rules()
    categories_config = rules.get('categories', {})
    
    # Создаем клиент Ollama с увеличенным таймаутом (10 минут) для обработки больших изображений
    # timeout=None означал бы бесконечность, но лучше поставить разумный лимит на случай зависания
    client = ollama.Client(host=OLLAMA_URL, timeout=600)
    
    # Инициализируем категории из конфига
    categories = {}
    category_folders = {}
    
    for cat_key, cat_info in categories_config.items():
        categories[cat_key] = []
        category_folders[cat_key] = cat_info.get('folder_name', f'06_{cat_key}')
    
    # Создаем папку drawings и подпапки для категорий внутри session_folder
    drawings_folder = Path(output_folder) / 'drawings'
    for folder_name in category_folders.values():
        (drawings_folder / folder_name).mkdir(parents=True, exist_ok=True)
    
    # Получаем список всех PDF файлов в папке pages
    pages_path = Path(pages_folder)
    if not pages_path.exists():
        logger.error(f"❌ Папка со страницами не найдена: {pages_folder}")
        return categories
    
    pdf_files = list(pages_path.glob("*.pdf"))
    total_pages = len(pdf_files)
    
    if total_pages == 0:
        logger.warning(f"⚠️ В папке {pages_folder} не найдено PDF файлов")
        return categories
    
    logger.info(f"🔍 Найдено {total_pages} страниц для классификации")
    
    # Классифицируем каждую страницу
    for i, pdf_file in enumerate(pdf_files):
        logger.info(f"   Обработка страницы {i+1}/{total_pages}: {pdf_file.name}")
        
        # Извлекаем номер страницы из имени файла
        page_num = i + 1
        try:
            # Пытаемся извлечь номер страницы из имени файла
            match = re.search(r'page_(\d+)', pdf_file.name)
            if match:
                page_num = int(match.group(1))
        except:
            pass
        
        # Классифицируем страницу
        category = classify_single_page(str(pdf_file), client)
        
        if not category:
            logger.warning(f"      ⚠️ Не удалось классифицировать, помещаем в 'other'")
            category = 'other'
        
        # Копируем файл в соответствующую папку категории
        dest_folder = drawings_folder / category_folders[category]
        dest_path = dest_folder / pdf_file.name
        
        shutil.copy2(str(pdf_file), str(dest_path))
        logger.info(f"      ✅ Скопировано в: {dest_folder.name}/{pdf_file.name}")
        
        # Добавляем информацию о классификации
        categories[category].append({
            'page_num': page_num,
            'source_file': pdf_file.name,
            'image_path': str(dest_path),
            'category': category
        })
        
        # Пауза между запросами для стабильности
        if i < total_pages - 1:
            time.sleep(REQUEST_DELAY)
    
    # Логируем итоги
    logger.info("\n" + "="*80)
    logger.info("ИТОГИ КЛАССИФИКАЦИИ:")
    for cat, items in categories.items():
        logger.info(f"  {category_folders[cat]}: {len(items)} стр.")
    logger.info("="*80)
    
    return categories


def get_relevant_categories_for_question(question: str) -> List[str]:
    """
    Определяет, какие категории чертежей релевантны для данного вопроса.
    Использует правила из config/classification_rules.json.
    
    Args:
        question: Вопрос пользователя
        
    Returns:
        Список релевантных категорий
    """
    # Загружаем правила классификации
    rules = load_classification_rules()
    question_mapping = rules.get('question_category_mapping', {})
    default_categories = rules.get('default_categories', [
        'building_elevation', 'residential_floor_plan', 'non_residential_floor_plan',
        'technical_floor', 'parking_floor', 'other'
    ])
    
    question_lower = question.lower()
    
    # Проверяем сопоставления из конфига
    for pattern, categories in question_mapping.items():
        # Разбираем паттерн с regex-подобными символами (|)
        keywords = pattern.split('|')
        if any(keyword.strip() in question_lower for keyword in keywords):
            return categories
    
    # Если не найдено совпадений, возвращаем все категории по умолчанию
    return default_categories
