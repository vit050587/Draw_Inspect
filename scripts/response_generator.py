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
    page_references = set()
    
    for page in pages_data.get('pages', []):
        page_num = page.get('page_num', 1)
        source_file = page.get('source_file', '')
        
        # Пытаемся загрузить результаты анализа для этой страницы
        # (в реальном сценарии они должны быть сохранены page_analyzer.py)
        page_references.add(page_num)
    
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
                page_references.add(element['page_number'])
    
    # Формируем структурированный текстовый ответ
    answer_lines = []
    answer_lines.append(f"📊 Результат поиска элементов по запросу: \"{question}\"")
    answer_lines.append("")
    answer_lines.append("=" * 60)
    answer_lines.append("")
    
    if not all_elements:
        answer_lines.append("⚠️ Элементы не найдены или анализ еще не завершен.")
        answer_lines.append("")
        answer_lines.append("Проверьте корректность запроса и попробуйте снова.")
    else:
        answer_lines.append(f"✅ Найдено элементов: {len(all_elements)}")
        answer_lines.append("")
        answer_lines.append("-" * 60)
        answer_lines.append("ДЕТАЛИ ПО НАЙДЕННЫМ ОБЪЕКТАМ:")
        answer_lines.append("-" * 60)
        answer_lines.append("")
        
        for idx, element in enumerate(all_elements, 1):
            obj_name = element.get('object_name', 'Не указано')
            dimensions = element.get('dimensions', 'не указаны')
            material = element.get('material', 'не указан')
            quantity = element.get('quantity', 'не указано')
            page_num = element.get('page_number', '?')
            source_file = element.get('source_file', 'не указано')
            
            answer_lines.append(f"{idx}. 🏗️ {obj_name}")
            answer_lines.append(f"   📏 Размеры: {dimensions}")
            answer_lines.append(f"   🧱 Материал: {material}")
            if quantity != 'не указано':
                answer_lines.append(f"   🔢 Количество: {quantity}")
            answer_lines.append(f"   📄 Найден в документе: {source_file}")
            answer_lines.append(f"   📑 Страница: {page_num}")
            answer_lines.append("")
    
    answer_lines.append("=" * 60)
    answer_lines.append("")
    
    # Сводка
    summary = f"Всего обработано страниц: {len(page_references)}. "
    if all_elements:
        summary += f"Найдено {len(all_elements)} элементов."
    else:
        summary += "Элементы не найдены."
    
    answer_lines.append(summary)
    
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
    
    return {
        'answer': answer_text,
        'findings': findings,
        'summary': summary,
        'page_references': sorted(list(page_references))
    }


if __name__ == '__main__':
    print("Response generator module loaded successfully")
