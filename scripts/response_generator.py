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
    source_files = set()
    
    for page in pages_data.get('pages', []):
        page_num = page.get('page_num', 1)
        source_file = page.get('source_file', '')
        source_files.add(source_file)
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
                source_files.add(element['source_file'])
    
    # Формируем краткий структурированный ответ (только основная информация)
    answer_lines = []
    answer_lines.append(f"📊 Результат поиска элементов по запросу: \"{question}\"")
    answer_lines.append("")
    
    if not all_elements:
        answer_lines.append("⚠️ Элементы не найдены или анализ еще не завершен.")
        answer_lines.append("")
        answer_lines.append("Проверьте корректность запроса и попробуйте снова.")
    else:
        answer_lines.append(f"✅ Найдено элементов: {len(all_elements)}")
        answer_lines.append("")
        answer_lines.append("Элементы найдены в следующих документах:")
        for src_file in sorted(source_files):
            answer_lines.append(f"  • {src_file}")
    
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
    summary = f"Обработано файлов: {len(source_files)}. "
    summary += f"Обработано страниц: {len(page_references)}. "
    if all_elements:
        summary += f"Найдено элементов: {len(all_elements)}."
    else:
        summary += "Элементы не найдены."
    
    return {
        'answer': answer_text,
        'findings': findings,
        'summary': summary,
        'page_references': sorted(list(page_references))
    }


if __name__ == '__main__':
    print("Response generator module loaded successfully")
