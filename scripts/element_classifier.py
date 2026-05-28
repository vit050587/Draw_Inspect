import ollama
import os
import json
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import re


def find_local_match(object_name, reference_elements):
    """
    Локальный поиск наилучшего соответствия по названию элемента.
    Возвращает лучший матч и уверенность.
    """
    if not object_name:
        return None, 'low'
    
    # Нормализуем имя для поиска
    object_name_lower = object_name.lower().strip()
    
    best_match = None
    best_score = 0
    
    for ref_elem in reference_elements:
        ref_class = ref_elem.get('class', '') or ''
        ref_category = ref_elem.get('category', '') or ''
        ref_purpose = ref_elem.get('purpose', '') or ''
        
        # Считаем skor совпадения
        score = 0
        
        # Точное совпадение class (наиболее важный критерий)
        if ref_class.lower() == object_name_lower:
            score = 100
        # Содержит ли class в себе object_name
        elif object_name_lower in ref_class.lower():
            score = 80
        # object_name содержит class
        elif ref_class.lower() and ref_class.lower() in object_name_lower:
            score = 70
        # Совпадение по категории + назначение
        elif object_name_lower in ref_purpose.lower():
            score = 50
        elif object_name_lower in ref_category.lower():
            score = 30
        
        if score > best_score:
            best_score = score
            best_match = ref_elem
    
    # Определяем уверенность
    if best_score >= 100:
        confidence = 'high'
    elif best_score >= 70:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    return best_match, confidence


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
    
    # Шаг 1: Локальное сопоставление для каждого элемента
    classified_elements = []
    elements_for_llm = []
    
    for elem in found_elements:
        object_name = elem.get('object_name', '')
        best_match, match_confidence = find_local_match(object_name, reference_elements)
        
        if best_match and match_confidence in ['high', 'medium']:
            # Нашли хорошее совпадение локально
            classified_elements.append({
                'original_object_name': object_name,
                'code_category': best_match.get('code_category'),
                'code_purpose': best_match.get('code_purpose'),
                'code_class': best_match.get('code_class'),
                'code_subclass': best_match.get('code_subclass'),
                'category': best_match.get('category'),
                'purpose': best_match.get('purpose'),
                'class': best_match.get('class'),
                'subclass': best_match.get('subclass'),
                'ifcClass': best_match.get('ifcClass'),
                'source_file': elem.get('source_file', ''),
                'page_number': elem.get('page_number', 1),
                'match_confidence': match_confidence,
                'dimensions': elem.get('dimensions', ''),
                'material': elem.get('material', '')
            })
        else:
            # Не нашли хорошего совпадения — добавляем в список для LLM
            elements_for_llm.append(elem)
    
    # Шаг 2: Если есть элементы без совпадений, используем LLM для них
    if elements_for_llm:
        # Формируем подмножество справочника для отправки в LLM
        # Группируем по class и берем уникальные значения
        unique_classes = set()
        for elem in elements_for_llm:
            obj_name = elem.get('object_name', '').lower().strip()
            # Ищем похожие названия классов в справочнике
            for ref in reference_elements:
                ref_class = ref.get('class', '') or ''
                if obj_name in ref_class.lower() or ref_class.lower() in obj_name:
                    unique_classes.add(ref.get('code_class', ''))
        
        # Если не нашли похожих, берем случайные элементы из разных категорий
        if len(unique_classes) < 50:
            sampled_refs = reference_elements[::max(1, len(reference_elements)//50)]
        else:
            # Берем элементы с нужными code_class
            sampled_refs = [ref for ref in reference_elements if ref.get('code_class', '') in list(unique_classes)[:50]]
        
        if len(sampled_refs) > 100:
            sampled_refs = sampled_refs[:100]
        
        # Промпт для классификации оставшихся элементов
        prompt = f"""Ты эксперт по классификации строительных элементов.

СПРАВОЧНИК ЭЛЕМЕНТОВ (эталон, релевантные записи):
{json.dumps(sampled_refs, ensure_ascii=False, indent=2)}

НАЙДЕННЫЕ ЭЛЕМЕНТЫ для классификации (без точного локального совпадения):
{json.dumps(elements_for_llm, ensure_ascii=False, indent=2)}

ЗАДАЧА:
Для каждого найденного элемента подберите наилучшее соответствие из справочника.
Используй название элемента (object_name), размеры (dimensions) и материал (material) для сопоставления.

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
            "match_confidence": "high",
            "dimensions": "...",
            "material": "..."
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
            llm_classified = []
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    data = json.loads(json_str)
                    llm_classified = data.get('classified_elements', [])
            except json.JSONDecodeError:
                # Если не удалось распарсить, создаем заглушку с низким доверием
                llm_classified = [{
                    'original_object_name': elem.get('object_name', ''),
                    'code_category': None,
                    'code_purpose': None,
                    'code_class': None,
                    'code_subclass': None,
                    'category': None,
                    'purpose': None,
                    'class': None,
                    'subclass': None,
                    'ifcClass': None,
                    'source_file': elem.get('source_file', ''),
                    'page_number': elem.get('page_number', 1),
                    'match_confidence': 'low',
                    'dimensions': elem.get('dimensions', ''),
                    'material': elem.get('material', '')
                } for elem in elements_for_llm]
            
            # Добавляем результаты LLM к основным
            classified_elements.extend(llm_classified)
            
        except Exception as e:
            # Ошибка LLM — добавляем элементы с null значениями
            for elem in elements_for_llm:
                classified_elements.append({
                    'original_object_name': elem.get('object_name', ''),
                    'code_category': None,
                    'code_purpose': None,
                    'code_class': None,
                    'code_subclass': None,
                    'category': None,
                    'purpose': None,
                    'class': None,
                    'subclass': None,
                    'ifcClass': None,
                    'source_file': elem.get('source_file', ''),
                    'page_number': elem.get('page_number', 1),
                    'match_confidence': 'low',
                    'dimensions': elem.get('dimensions', ''),
                    'material': elem.get('material', '')
                })
    
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


if __name__ == '__main__':
    print("Element classifier module loaded successfully")
