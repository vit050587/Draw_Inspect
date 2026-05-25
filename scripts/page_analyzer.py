"""
Модуль анализа страниц с чертежами с использованием модели gemma4:31b через Ollama.
Анализирует каждую страницу и сохраняет результаты в отдельной папке сессии.
"""

import os
import ollama
import json
import base64
import time
import logging
from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF для работы с PDF

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================

def setup_logging():
    current_dir = Path(__file__).resolve().parent  # scripts/
    project_dir = current_dir.parent  # корень проекта (Draw_Inspect)
    log_dir = project_dir / 'outputs' / 'logs'
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'page_analyzer.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Конфигурация Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ANALYSIS_MODEL = os.getenv("DRAWING_ANALYSIS_MODEL", "gemma4:31b")

REQUEST_DELAY = 2  # Пауза между запросами (2 секунды)

# Путь к файлу с промптом
PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'
ANALYSIS_PROMPT_FILE = PROMPTS_DIR / 'analysis_prompt.txt'

logger.info("="*80)
logger.info("ЗАПУСК АНАЛИЗА ЧЕРТЕЖЕЙ")
logger.info("="*80)
logger.info(f"Модель: {ANALYSIS_MODEL}")
logger.info(f"🔌 Подключение к Ollama: {OLLAMA_URL}")


def load_analysis_prompt(question: str) -> str:
    """Загружает промпт анализа из файла и подставляет вопрос"""
    try:
        with open(ANALYSIS_PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        return prompt_template.format(question=question)
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки промпта из {ANALYSIS_PROMPT_FILE}: {e}")
        # Возвращаем дефолтный промпт в случае ошибки
        return f"""
Вы эксперт в области архитектурных чертежей и пожарной безопасности.

Проанализируйте этот чертеж здания и предоставьте информацию, связанную со следующим вопросом:

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

Ищите и сообщайте:
- Лестницы (количество, ширина, расположение)
- Коридоры (ширина, длина)
- Площади помещений
- Парковочные места (количество)
- Эвакуационные выходы
- Любые другие элементы, относящиеся к пожарной безопасности

Будьте конкретны и точны. Если вы не можете найти определенную информацию, четко укажите это.
Предоставьте измерения, где они видны на чертеже.

Укажите также номер страницы/изображения для ссылки.

Формат ответа должен быть структурированным:
1. Основная информация по вопросу
2. Детали с измерениями
3. Номер страницы где найдена информация
"""


def pdf_to_base64(pdf_path: str) -> str:
    """Конвертирует PDF страницу в base64 PNG для отправки модели"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        
        # Создаем матрицу для высокого качества
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        
        # Рендерим страницу в pixmap
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


def analyze_pages(images: List[Dict[str, Any]], question: str, output_folder: str) -> List[Dict[str, Any]]:
    """
    Анализирует страницы с чертежами для ответа на вопрос пользователя.
    
    Args:
        images: Список словарей с информацией об изображениях (path, page_num, source_file, size)
        question: Вопрос пользователя
        output_folder: Папка для сохранения результатов анализа
        
    Returns:
        Список результатов анализа для каждого изображения
    """
    # Создаем папку для результатов анализа
    analysis_folder = Path(output_folder) / 'analysis'
    analysis_folder.mkdir(parents=True, exist_ok=True)
    
    client = ollama.Client(host=OLLAMA_URL, timeout=300.0)
    
    results = []
    total_images = len(images)
    
    logger.info(f"🔍 Анализ {total_images} страниц для вопроса: {question[:50]}...")
    
    for i, img_info in enumerate(images):
        try:
            image_path = img_info.get('path') or img_info.get('image_path')
            page_num = img_info.get('page_num', 1)
            source_file = img_info.get('source_file', 'unknown')
            size = img_info.get('size', 'unknown')
            
            logger.info(f"   Обработка страницы {i+1}/{total_images}: {os.path.basename(image_path)}")
            
            # Формируем промпт для анализа из файла
            analysis_prompt = load_analysis_prompt(question)
            
            # Конвертируем PDF в base64 через fitz (рендеринг в PNG)
            logger.info(f"      🧠 Конвертация PDF страницы в base64...")
            b64 = pdf_to_base64(image_path)
            if not b64:
                raise Exception("Не удалось конвертировать PDF в изображение")
            
            # Отправляем запрос к модели
            logger.info(f"      🧠 Отправка запроса модели {ANALYSIS_MODEL}...")
            start_time = time.time()
            
            response = client.chat(
                model=ANALYSIS_MODEL,
                messages=[{
                    'role': 'user',
                    'content': analysis_prompt,
                    'images': [b64]
                }],
                stream=False,
                options={'temperature': 0.1, 'num_predict': 2048}
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"      ⏱️ Модель отвечала {elapsed_time:.1f} секунд")
            
            analysis_text = response['message']['content'].strip()
            
            # Сохраняем результат анализа в файл
            result_filename = f"analysis_page_{page_num}_{source_file.replace('.pdf', '')}.json"
            result_path = analysis_folder / result_filename
            
            result_data = {
                'page_num': page_num,
                'source_file': source_file,
                'size': size,
                'question': question,
                'analysis': analysis_text,
                'image_path': image_path
            }
            
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            results.append({
                'page_num': page_num,
                'source_file': source_file,
                'size': size,
                'image_path': image_path,
                'analysis': analysis_text,
                'result_file': str(result_path),
                'relevant': True
            })
            
            logger.info(f"      ✅ Проанализировано: страница {page_num} из {source_file}")
            
            # Пауза между запросами для стабильности
            if i < total_images - 1:
                time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа изображения {img_info.get('path', img_info.get('image_path', 'unknown'))}: {e}")
            results.append({
                'page_num': img_info.get('page_num', 1),
                'source_file': img_info.get('source_file', 'unknown'),
                'size': img_info.get('size', 'unknown'),
                'image_path': img_info.get('path', img_info.get('image_path', '')),
                'analysis': f"Ошибка анализа: {str(e)}",
                'result_file': None,
                'relevant': False,
                'error': str(e)
            })
    
    logger.info("\n" + "="*80)
    logger.info(f"АНАЛИЗ ЗАВЕРШЕН: {len(results)} страниц обработано")
    logger.info("="*80)
    
    return results
