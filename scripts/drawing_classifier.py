"""
Модуль классификации чертежей с использованием модели gemma4:31b через Ollama.
Классифицирует страницы с чертежами по категориям:
1. building_elevation - все здание вид сбоку
2. residential_floor_plan - план этажа вид сверху жилые этажи
3. non_residential_floor_plan - план этажа вид сверху нежилые этажи
4. technical_floor - технический этаж
5. parking_floor - план здания вид сверху парковка
"""

import os
import ollama
from typing import List, Dict, Any
from pathlib import Path

# Конфигурация Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CLASSIFICATION_MODEL = os.getenv("DRAWING_CLASSIFICATION_MODEL", "gemma4:31b")


def classify_drawings(images: List[Dict[str, Any]], output_folder: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Классифицирует изображения чертежей по категориям и распределяет по папкам.
    
    Args:
        images: Список словарей с информацией об изображениях
        output_folder: Базовая папка для сохранения классифицированных изображений
        
    Returns:
        Словарь с категориями и списками изображений в каждой
    """
    # Создаем папки для категорий
    categories = {
        'building_elevation': [],  # все здание вид сбоку
        'residential_floor_plan': [],  # план этажа вид сверху жилые этажи
        'non_residential_floor_plan': [],  # план этажа вид сверху нежилые этажи
        'technical_floor': [],  # технический этаж
        'parking_floor': [],  # план здания вид сверху парковка
        'other': []  # другое
    }
    
    category_folders = {
        'building_elevation': '01_building_elevation',
        'residential_floor_plan': '02_residential_floor_plan',
        'non_residential_floor_plan': '03_non_residential_floor_plan',
        'technical_floor': '04_technical_floor',
        'parking_floor': '05_parking_floor',
        'other': '06_other'
    }
    
    # Создаем папки для категорий внутри session_folder
    drawings_folder = os.path.join(output_folder, 'drawings')
    for folder_name in category_folders.values():
        os.makedirs(os.path.join(drawings_folder, folder_name), exist_ok=True)
    
    client = ollama.Client(host=OLLAMA_URL, timeout=120.0)
    
    classification_prompt = """
Вы эксперт в области архитектурных чертежей и планов зданий.

Классифицируйте этот чертеж в одну из следующих категорий:
- building_elevation (все здание вид сбоку)
- residential_floor_plan (план этажа вид сверху жилые этажи)  
- non_residential_floor_plan (план этажа вид сверху нежилые этажи)
- technical_floor (технический этаж)
- parking_floor (план здания вид сверху парковка)
- other (другое)

Внимательно проанализируйте изображение и определите тип чертежа.
Отвечайте ТОЛЬКО названием категории на английском из списка выше, без пояснений.
"""
    
    for img_info in images:
        try:
            image_path = img_info['path']
            
            # Кодируем PDF файл в base64
            with open(image_path, 'rb') as f:
                import base64
                # Для PDF читаем весь файл
                file_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Отправляем запрос к модели
            response = client.chat(
                model=CLASSIFICATION_MODEL,
                messages=[{
                    'role': 'user',
                    'content': classification_prompt,
                    'images': [file_data]
                }],
                stream=False,
                options={'temperature': 0.1, 'num_predict': 100}
            )
            
            category = response['message']['content'].strip().lower()
            
            # Очищаем категорию от лишних символов
            for cat in categories.keys():
                if cat in category:
                    category = cat
                    break
            
            # Если категория не распознана, помещаем в other
            if category not in categories:
                category = 'other'
            
            # Копируем изображение в соответствующую папку
            dest_folder = os.path.join(drawings_folder, category_folders[category])
            filename = os.path.basename(image_path)
            dest_path = os.path.join(dest_folder, filename)
            
            # Копируем файл
            import shutil
            shutil.copy2(image_path, dest_path)
            
            # Добавляем информацию о классификации
            categories[category].append({
                'page_num': img_info.get('page_num', 1),
                'source_file': img_info.get('source_file', 'unknown'),
                'image_path': dest_path,
                'category': category
            })
            
            print(f"Классифицировано: {filename} -> {category}")
            
        except Exception as e:
            print(f"Ошибка классификации изображения {img_info.get('path', 'unknown')}: {e}")
            # В случае ошибки помещаем в other
            category = 'other'
            categories[category].append({
                'page_num': img_info.get('page_num', 1),
                'source_file': img_info.get('source_file', 'unknown'),
                'image_path': img_info.get('path', ''),
                'category': 'error',
                'error': str(e)
            })
    
    return categories


def get_relevant_categories_for_question(question: str) -> List[str]:
    """
    Определяет, какие категории чертежей релевантны для данного вопроса.
    
    Args:
        question: Вопрос пользователя
        
    Returns:
        Список релевантных категорий
    """
    question_lower = question.lower()
    
    # Правила сопоставления вопросов и категорий
    if any(word in question_lower for word in ['этажность', 'высот', 'здани', 'фасад', 'вид сбоку']):
        return ['building_elevation']
    
    elif any(word in question_lower for word in ['парковк', 'машиномест', 'автомобил', 'гараж']):
        return ['parking_floor']
    
    elif any(word in question_lower for word in ['жил', 'квартир', ' жилой ', 'жилых']):
        return ['residential_floor_plan']
    
    elif any(word in question_lower for word in ['технич', 'инженер', 'оборудован', 'вентиляц', 'насос']):
        return ['technical_floor']
    
    elif any(word in question_lower for word in ['нежил', 'коммерч', 'офис', 'магазин', 'склад']):
        return ['non_residential_floor_plan']
    
    elif any(word in question_lower for word in ['лестниц', 'марш', 'ступен', 'ширин']):
        # Лестницы могут быть на любых этажах, смотрим все планы этажей
        return ['residential_floor_plan', 'non_residential_floor_plan', 'technical_floor', 'parking_floor']
    
    elif any(word in question_lower for word in ['коридор', 'пути', 'эвакуаци', 'выход', 'расстояни']):
        # Пути эвакуации могут быть везде
        return ['residential_floor_plan', 'non_residential_floor_plan', 'technical_floor', 'parking_floor']
    
    else:
        # Если не удается понять вопрос, анализируем все чертежи
        return ['building_elevation', 'residential_floor_plan', 'non_residential_floor_plan', 
                'technical_floor', 'parking_floor', 'other']
