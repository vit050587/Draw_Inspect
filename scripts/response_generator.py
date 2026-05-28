import ollama
import os
import json

def generate_response(session_folder, question):
    """
    Генерирует текстовый ответ на основе результатов анализа страниц.
    Создает структурированный документ для удобного чтения человеком.
    
    Args:
        session_folder: папка сессии с результатами анализа
        question: вопрос пользователя
    
    Returns:
        dict: ответ в формате JSON с полями answer, findings, summary, page_references
    """
    # Загружаем результаты анализа страниц
    pages_info_path = os.path.join(session_folder, 'pages_info.json')
    if not os.path.exists(pages_info_path):
        return {
            'answer': 'Ошибка: информация о страницах не найдена',
            'findings': [],
            'summary': '',
            'page_references': []
        }
    
    with open(pages_info_path, 'r', encoding='utf-8') as f:
        pages_data = json.load(f)
    
    # Собираем все элементы из всех страниц
    all_elements = []
    source_files = set()
    total_files = len(pages_data.get('pages', []))
    
    for page in pages_data.get('pages', []):
        source_file = page.get('source_file', '')
        source_files.add(source_file)
    
    # Загружаем сохраненные результаты анализа если есть
    results_path = os.path.join(session_folder, 'analysis_results.json')
    if os.path.exists(results_path):
        with open(results_path, 'r', encoding='utf-8') as f:
            analysis_results = json.load(f)
        
        for page_result in analysis_results:
            elements = page_result.get('elements', [])
            for element in elements:
                element['page_number'] = page_result.get('page_number', 1)
                element['source_file'] = page_result.get('source_file', '')
                all_elements.append(element)
                source_files.add(element['source_file'])
    
    # Формируем подробный ответ с детализацией по каждому элементу
    answer_lines = []
    
    # Подсчитываем общее количество элементов (сумма quantity)
    total_quantity = 0
    for element in all_elements:
        try:
            qty = element.get('quantity', '0')
            # Пытаемся преобразовать в число, если это возможно
            if isinstance(qty, (int, float)):
                total_quantity += int(qty)
            elif isinstance(qty, str) and qty.replace('.', '', 1).replace(',', '', 1).isdigit():
                # Заменяем запятую на точку для float и преобразуем
                total_quantity += int(float(qty.replace(',', '.')))
        except (ValueError, TypeError):
            pass
    
    if not all_elements:
        answer_lines.append(f"📊 Результат поиска элементов по запросу: \"{question}\"")
        answer_lines.append("")
        answer_lines.append("⚠️ Элементы не найдены или анализ еще не завершен.")
        answer_lines.append("")
        answer_lines.append("Проверьте корректность запроса и попробуйте снова.")
    else:
        answer_lines.append(f"📊 Результат поиска элементов по запросу: \"{question}\"")
        answer_lines.append("")
        answer_lines.append(f"✅ Найдено элементов: {total_quantity}")
        answer_lines.append("")
        
        # Детальная информация по каждому элементу
        for idx, element in enumerate(all_elements, 1):
            obj_name = element.get('object_name', 'Не указано')
            dimensions = element.get('dimensions', 'не указано')
            material = element.get('material', 'не определён')
            quantity = element.get('quantity', '')
            source_file = element.get('source_file', '')
            page_num = element.get('page_number', 1)
            
            answer_lines.append(f"{idx}. {obj_name}")
            answer_lines.append("")
            answer_lines.append(f"📏 Размеры: {dimensions}")
            answer_lines.append(f"🧱 Материал: {material}")
            answer_lines.append(f"🔢 Количество: {quantity}")
            answer_lines.append("📄 Найден в документах:")
            answer_lines.append(f"{source_file}")
            answer_lines.append(f"Страницы: {page_num}")
            answer_lines.append("")
    
    answer_text = "\n".join(answer_lines)
    
    # Формируем findings для совместимости с frontend
    findings = []
    for element in all_elements:
        findings.append({
            'object_name': element.get('object_name', 'Не указано'),
            'dimensions': element.get('dimensions', 'не указаны'),
            'material': element.get('material', 'не указан'),
            'quantity': element.get('quantity', ''),
            'pages': [element.get('page_number', 1)],
            'files': [element.get('source_file', '')]
        })
    
    # Сводка: количество файлов, страниц и элементов
    # Подсчитываем уникальные страницы из ВСЕХ обработанных страниц (pages_data)
    unique_pages = set()
    for page in pages_data.get('pages', []):
        page_key = (page.get('source_file', ''), page.get('page_num', 1))
        unique_pages.add(page_key)
    
    # Если pages_data пуст, пробуем взять из элементов
    if not unique_pages:
        for element in all_elements:
            page_key = (element.get('source_file', ''), element.get('page_number', 1))
            unique_pages.add(page_key)
    
    summary = f"Обработано файлов: {len(source_files)}. "
    summary += f"Обработано страниц: {len(unique_pages)}. "
    if all_elements:
        summary += f"Найдено элементов: {total_quantity}."
    else:
        summary += "Элементы не найдены."
    
    return {
        'answer': answer_text,
        'findings': findings,
        'summary': summary,
        'page_references': sorted(list(range(1, len(unique_pages) + 1)))
    }


if __name__ == '__main__':
    print("Response generator module loaded successfully")
