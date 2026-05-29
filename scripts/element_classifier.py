import ollama
import os
import json
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import re
from difflib import SequenceMatcher
from collections import defaultdict


# Синонимы и связанные понятия для улучшения поиска (fallback, если нет enriched справочника)
SYNONYM_GROUPS = [
    {'лоджия', 'балкон', 'балконный'},
    {'дверь', 'дверной', 'двери'},
    {'окно', 'оконный', 'остекление', 'окна'},
    {'стена', 'стеновой', 'стеновая', 'стен'},
    {'плита', 'перекрытие'},
    {'пол', 'напольный'},
    {'потолок', 'потолочный'},
    {'фасад', 'фасадный'},
    {'кровля', 'крыша', 'кровельный'},
    {'фундамент', 'фундаментный'},
    {'перегородка', 'внутренняя стена'},
]

# Контекстные пары: ключевое слово → ожидаемые классы/подклассы
CONTEXT_HINTS = {
    'лодж': {'балкон', 'балконный', 'плита балкона', 'балконная дверь', 'Балконная дверь'},
    'балкон': {'лодж', 'лоджия'},
    'остекл': {'окно', 'оконный', 'светопрозрачный'},
    'дверь на лодж': {'Балконная дверь', 'балконная дверь'},
    'дверь на балкон': {'Балконная дверь', 'балконная дверь'},
    'стена лодж': {'Стена', 'Плита лоджии', 'Ограждение'},
    'стена балкон': {'Стена', 'Плита балкона', 'Ограждение'},
}


def load_reference_elements(elements_json_path):
    """
    Загружает справочник элементов.
    Если есть enriched справочник с search_keys, строит индекс для быстрого поиска.
    
    Returns:
        tuple: (reference_elements, search_index)
        - reference_elements: список всех элементов
        - search_index: dict {нормализованный_ключ: [elem1, elem2, ...]} для быстрого поиска
    """
    if not os.path.exists(elements_json_path):
        return [], {}
    
    with open(elements_json_path, 'r', encoding='utf-8') as f:
        reference_elements = json.load(f)
    
    # Строим индекс для поиска по search_keys (если есть)
    search_index = defaultdict(list)
    has_enriched = False
    
    for elem in reference_elements:
        # Индексируем основные поля
        for field in ['class', 'subclass', 'purpose', 'category']:
            value = elem.get(field, '') or ''
            normalized = normalize_text(value)
            if normalized:
                search_index[normalized].append(elem)
                # Также индексируем отдельные слова
                for word in normalized.split():
                    if len(word) > 2:
                        search_index[word].append(elem)
        
        # Индексируем search_keys из enriched справочника
        search_keys = elem.get('search_keys', [])
        if search_keys:
            has_enriched = True
            for key in search_keys:
                normalized_key = normalize_text(key)
                if normalized_key:
                    search_index[normalized_key].append(elem)
                    # Индексируем отдельные слова из ключей
                    for word in normalized_key.split():
                        if len(word) > 2:
                            search_index[word].append(elem)
    
    return reference_elements, search_index, has_enriched


def normalize_text(text):
    """Нормализует текст для сравнения: нижний регистр, удаление лишних пробелов."""
    if not text:
        return ''
    return ' '.join(text.lower().strip().split())


def get_synonym_expansions(text):
    """Возвращает набор слов с учётом синонимов."""
    normalized = normalize_text(text)
    words = set(normalized.split())
    expansions = set(words)
    
    for word in words:
        for group in SYNONYM_GROUPS:
            if any(word.startswith(g[:3]) for g in group):  # Проверяем по первым 3 буквам
                expansions.update(group)
    
    return expansions


def calculate_similarity_score(object_name, ref_elem, use_search_keys=True):
    """
    Вычисляет оценку схожести между именем объекта и элементом справочника.
    Учитывает class, subclass, purpose, category, синонимы и search_keys (из enriched справочника).
    Возвращает кортеж (score, match_details).
    """
    obj_normalized = normalize_text(object_name)
    obj_words = set(obj_normalized.split())
    
    ref_class = normalize_text(ref_elem.get('class', '') or '')
    ref_subclass = normalize_text(ref_elem.get('subclass', '') or '')
    ref_purpose = normalize_text(ref_elem.get('purpose', '') or '')
    ref_category = normalize_text(ref_elem.get('category', '') or '')
    
    # Объединяем все поля справочника для поиска
    ref_full = f"{ref_class} {ref_subclass} {ref_purpose}".strip()
    ref_words = set(ref_full.split())
    
    score = 0
    match_details = []
    
    # 1. Точное совпадение class (наивысший приоритет)
    if ref_class and ref_class == obj_normalized:
        score += 100
        match_details.append('exact_class')
    
    # 2. Class содержит object_name или наоборот
    if ref_class and obj_normalized in ref_class:
        score += 80
        match_details.append('class_contains_obj')
    elif ref_class and ref_class in obj_normalized:
        score += 70
        match_details.append('obj_contains_class')
    
    # 3. Subclass совпадение (важно для уточнения)
    if ref_subclass:
        if obj_normalized in ref_subclass:
            score += 75
            match_details.append('subclass_contains')
        elif ref_subclass in obj_normalized:
            score += 65
            match_details.append('obj_contains_subclass')
    
    # 4. Проверка search_keys из enriched справочника (новый приоритетный блок)
    if use_search_keys:
        search_keys = ref_elem.get('search_keys', [])
        for key in search_keys:
            key_normalized = normalize_text(key)
            if not key_normalized:
                continue
            # Полное совпадение с ключом поиска
            if key_normalized == obj_normalized:
                score += 95
                match_details.append(f'exact_search_key:{key}')
                break
            # Ключ содержит object_name или наоборот
            if obj_normalized in key_normalized:
                score += 70
                match_details.append(f'search_key_contains_obj:{key}')
                break
            if key_normalized in obj_normalized:
                score += 60
                match_details.append(f'obj_contains_search_key:{key}')
                break
            # Совпадение по словам из ключей
            key_words = set(key_normalized.split())
            common_key_words = obj_words & key_words
            if common_key_words:
                score += len(common_key_words) * 12
                match_details.append(f'search_key_words:{common_key_words}')
    
    # 5. Проверка синонимов (fallback если нет search_keys)
    obj_expansions = get_synonym_expansions(object_name)
    ref_expansions = get_synonym_expansions(ref_full)
    
    common_synonyms = obj_expansions & ref_expansions
    if common_synonyms:
        score += len(common_synonyms) * 15
        match_details.append(f'synonyms:{common_synonyms}')
    
    # 6. Контекстные подсказки (лоджия→балкон и т.д.)
    for context_key, expected_values in CONTEXT_HINTS.items():
        if context_key in obj_normalized:
            # Проверяем, есть ли ожидаемые значения в ref_elem
            for expected in expected_values:
                if expected.lower() in ref_class.lower() or expected.lower() in ref_subclass.lower():
                    score += 50
                    match_details.append(f'context:{context_key}→{expected}')
                    break
    
    # 7. Совпадение по словам (частичное)
    common_words = obj_words & ref_words
    if common_words:
        score += len(common_words) * 10
        match_details.append(f'common_words:{common_words}')
    
    # 8. Fuzzy matching для коротких названий
    if len(obj_normalized) > 3 and ref_class:
        ratio = SequenceMatcher(None, obj_normalized, ref_class).ratio()
        if ratio > 0.6:
            fuzzy_score = int(ratio * 40)
            score += fuzzy_score
            match_details.append(f'fuzzy:{ratio:.2f}')
    
    # 9. Совпадение по purpose
    if obj_normalized in ref_purpose.lower():
        score += 40
        match_details.append('purpose_match')
    
    return score, match_details


def find_local_match(object_name, reference_elements, search_index=None, has_enriched=False):
    """
    Локальный поиск наилучшего соответствия по названию элемента.
    Использует улучшенный алгоритм с синонимами, контекстными подсказками и search_keys.
    
    Args:
        object_name: имя объекта для поиска
        reference_elements: полный список элементов справочника
        search_index: предварительно построенный индекс для быстрого поиска (если есть)
        has_enriched: флаг использования enriched справочника с search_keys
    
    Returns:
        лучший матч или None.
    """
    if not object_name:
        return None
    
    best_match = None
    best_score = 0
    best_details = []
    
    # Если есть search_index, сначала ищем по нему (быстрый поиск)
    candidates = []
    seen_ids = set()
    
    if search_index:
        obj_normalized = normalize_text(object_name)
        obj_words = obj_normalized.split()
        
        def add_candidates(elem_list):
            """Добавляет элементы в candidates, избегая дубликатов"""
            for elem in elem_list:
                elem_id = id(elem)
                if elem_id not in seen_ids:
                    seen_ids.add(elem_id)
                    candidates.append(elem)
        
        # Добавляем кандидатов из индекса по полному названию
        if obj_normalized in search_index:
            add_candidates(search_index[obj_normalized])
        
        # Добавляем кандидатов по отдельным словам
        for word in obj_words:
            if len(word) > 2 and word in search_index:
                add_candidates(search_index[word])
        
        # Добавляем кандидатов по синонимам
        synonym_expansions = get_synonym_expansions(object_name)
        for syn in synonym_expansions:
            if syn in search_index:
                add_candidates(search_index[syn])
    
    # Если нашли кандидатов через индекс, проверяем только их
    # Иначе проверяем все элементы (fallback)
    elements_to_check = candidates if candidates else reference_elements
    
    # Ограничиваем количество элементов для проверки (оптимизация)
    if len(elements_to_check) > 500:
        elements_to_check = elements_to_check[:500]
    
    for ref_elem in elements_to_check:
        score, details = calculate_similarity_score(
            object_name, 
            ref_elem, 
            use_search_keys=has_enriched
        )
        
        if score > best_score:
            best_score = score
            best_match = ref_elem
            best_details = details
    
    # Возвращаем только если хорошее совпадение (score >= 60)
    # Сlightly lowered threshold to allow more matches with synonym/context/search_keys support
    if best_score >= 60:
        return best_match
    return None


def classify_elements(session_folder, elements_json_path):
    """
    Сопоставляет найденные элементы со справочником elements.json.
    Автоматически ищет enriched справочник (elements_enriched.json) в той же папке.
    Создает JSON с классификацией и Excel таблицу.
    
    Args:
        session_folder: папка сессии
        elements_json_path: путь к справочнику elements.json (или elements_enriched.json)
    
    Returns:
        dict: результаты классификации с путями к сохраненным файлам
    """
    model = os.environ.get('DRAWING_VALIDATION_MODEL', 'gemma3:27b')
    
    # Проверяем, есть ли enriched справочник в той же папке
    base_dir = os.path.dirname(elements_json_path)
    base_name = os.path.basename(elements_json_path)
    
    # Если указан elements.json, пробуем найти elements_enriched.json
    enriched_path = None
    if base_name == 'elements.json':
        enriched_candidate = os.path.join(base_dir, 'elements_enriched.json')
        if os.path.exists(enriched_candidate):
            enriched_path = enriched_candidate
    
    # Используем enriched справочник если есть, иначе fallback на обычный
    actual_elements_path = enriched_path if enriched_path else elements_json_path
    has_enriched = enriched_path is not None
    
    # Загружаем справочник элементов с построением индекса
    reference_elements, search_index, has_enriched_data = load_reference_elements(actual_elements_path)
    
    if not reference_elements:
        return {
            'error': f'Справочник не найден: {actual_elements_path}',
            'classified_elements': [],
            'json_path': None,
            'excel_path': None
        }
    
    # Сообщаем какой справочник используется
    print(f"Используется справочник: {actual_elements_path}")
    print(f"Записей в справочнике: {len(reference_elements)}")
    print(f"Enriched справочник с search_keys: {has_enriched_data}")
    print(f"Размер поискового индекса: {len(search_index)} ключей")
    
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
                'quantity': element.get('quantity', ''),
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
    
    # Шаг 1: Локальное сопоставление для каждого элемента с использованием search_index
    classified_elements = []
    elements_for_llm = []
    
    for elem in found_elements:
        object_name = elem.get('object_name', '')
        best_match = find_local_match(
            object_name, 
            reference_elements, 
            search_index=search_index, 
            has_enriched=has_enriched_data
        )
        
        if best_match:
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
                'dimensions': elem.get('dimensions', ''),
                'material': elem.get('material', ''),
                'quantity': elem.get('quantity', '')
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
Используй название элемента (object_name) для сопоставления.

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
            "dimensions": "...",
            "material": "...",
            "quantity": "..."
        }}
    ]
}}

Если точное соответствие не найдено, укажите ближайший вариант или null для полей.
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
                    'dimensions': elem.get('dimensions', ''),
                    'material': elem.get('material', ''),
                    'quantity': elem.get('quantity', '')
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
                    'dimensions': elem.get('dimensions', ''),
                    'material': elem.get('material', ''),
                    'quantity': elem.get('quantity', '')
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
            'Количество': elem.get('quantity', ''),
            'Размеры': elem.get('dimensions', ''),
            'Материал': elem.get('material', '')
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
