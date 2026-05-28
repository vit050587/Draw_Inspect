import ollama
import os
import json
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

def classify_elements(session_folder, elements_json_path):
    """
    Сопоставляет найденные элементы со справочником elements.json.
    Создает JSON с классификацией и Excel таблицу.
    
    Args:
        session_folder: папка сессии
        elements_json_path: путь к справочнику elements.json
    
    Returns:
        dict: результаты классификации с путями к сохраненным файлам
    """
    model = os.environ.get('DRAWING_VALIDATION_MODEL', 'gemma3:27b')
    
    # Загружаем справочник элементов
    if not os.path.exists(elements_json_path):
        return {
            'error': f'Справочник не найден: {elements_json_path}',
            'classified_elements': [],
            'json_path': None,
            'excel_path': None
        }
    
    with open(elements_json_path, 'r', encoding='utf-8') as f:
        reference_elements = json.load(f)
    
    # Загружаем найденные элементы из результатов анализа
    analysis_results_path = os.path.join(session_folder, 'analysis_results.json')
    if not os.path.exists(analysis_results_path):
        return {
            'error': 'Результаты анализа не найдены. Сначала выполните анализ страниц.',
            'classified_elements': [],
            'json_path': None,
            'excel_path': None
        }
    
    with open(analysis_results_path, 'r', encoding='utf-8') as f:
        analysis_results = json.load(f)
    
    # Собираем все найденные элементы
    found_elements = []
    for page_result in analysis_results:
        page_num = page_result.get('page_number', 1)
        source_file = page_result.get('source_file', '')
        
        for element in page_result.get('elements', []):
            found_elements.append({
                'object_name': element.get('object_name', ''),
                'dimensions': element.get('dimensions', ''),
                'material': element.get('material', ''),
                'location': element.get('location', ''),
                'quantity': element.get('quantity', ''),
                'confidence': element.get('confidence', 'medium'),
                'page_number': page_num,
                'source_file': source_file
            })
    
    if not found_elements:
        return {
            'error': 'Найденные элементы отсутствуют',
            'classified_elements': [],
            'json_path': None,
            'excel_path': None
        }
    
    # Промпт для классификации элементов
    prompt = f"""Ты эксперт по классификации строительных элементов.
    
СПРАВОЧНИК ЭЛЕМЕНТОВ (эталон):
{json.dumps(reference_elements[:20], ensure_ascii=False, indent=2)}
... (всего {len(reference_elements)} элементов в справочнике)

НАЙДЕННЫЕ ЭЛЕМЕНТЫ для классификации:
{json.dumps(found_elements[:10], ensure_ascii=False, indent=2)}
... (всего {len(found_elements)} элементов для классификации)

ЗАДАЧА:
Для каждого найденного элемента подберите наилучшее соответствие из справочника.
Используй название элемента (object_name), размеры и материал для сопоставления.

Отвечай ТОЛЬКО в формате JSON:
{{
    "classified_elements": [
        {{
            "original_object_name": "...",
            "code_category": "ЭЛ 10",
            "code_purpose": "ЭЛ 10 10",
            "code_class": "ЭЛ 10 10 10",
            "code_subclass": "ЭЛ 10 10 10 01",
            "category": "Земляные сооружения, фундаменты",
            "purpose": "Фундаменты",
            "class": "Свая",
            "subclass": "Свая забивная",
            "ifcClass": "IfcPile",
            "source_file": "filename.pdf",
            "page_number": 5,
            "match_confidence": "high"
        }}
    ]
}}

Если точное соответствие не найдено, укажите ближайший вариант или null для полей.
match_confidence: high/medium/low - уверенность в сопоставлении
"""
    
    try:
        # Отправляем запрос модели
        response = ollama.chat(
            model=model,
            messages=[{
                'role': 'user',
                'content': prompt
            }]
        )
        
        response_text = response['message']['content']
        
        # Парсим ответ
        classified_elements = []
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                data = json.loads(json_str)
                classified_elements = data.get('classified_elements', [])
        except json.JSONDecodeError:
            # Если не удалось распарсить, создаем заглушку
            classified_elements = [{
                'original_object_name': elem.get('object_name', ''),
                'code_category': 'не определено',
                'code_purpose': None,
                'code_class': None,
                'code_subclass': None,
                'category': 'не определено',
                'purpose': None,
                'class': None,
                'subclass': None,
                'ifcClass': None,
                'source_file': elem.get('source_file', ''),
                'page_number': elem.get('page_number', 1),
                'match_confidence': 'low'
            } for elem in found_elements[:10]]
        
        # Сохраняем JSON результат
        output_json_path = os.path.join(session_folder, 'classified_elements.json')
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(classified_elements, f, ensure_ascii=False, indent=2)
        
        # Создаем DataFrame для Excel
        df_data = []
        for elem in classified_elements:
            df_data.append({
                'Имя объекта': elem.get('original_object_name', ''),
                'Код категории': elem.get('code_category', ''),
                'Код назначения': elem.get('code_purpose', ''),
                'Код класса': elem.get('code_class', ''),
                'Код подкласса': elem.get('code_subclass', ''),
                'Категория': elem.get('category', ''),
                'Назначение': elem.get('purpose', ''),
                'Класс': elem.get('class', ''),
                'Подкласс': elem.get('subclass', ''),
                'IFC Class': elem.get('ifcClass', ''),
                'Файл': elem.get('source_file', ''),
                'Страница': elem.get('page_number', ''),
                'Уверенность': elem.get('match_confidence', '')
            })
        
        df = pd.DataFrame(df_data)
        
        # Сохраняем Excel
        output_excel_path = os.path.join(session_folder, 'classified_elements.xlsx')
        df.to_excel(output_excel_path, index=False, sheet_name='Классификация')
        
        return {
            'classified_elements': classified_elements,
            'json_path': output_json_path,
            'excel_path': output_excel_path,
            'total_classified': len(classified_elements)
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'classified_elements': [],
            'json_path': None,
            'excel_path': None
        }


if __name__ == '__main__':
    print("Element classifier module loaded successfully")
