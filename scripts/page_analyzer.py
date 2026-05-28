import ollama
import os
import json
from PIL import Image
import fitz  # PyMuPDF

def analyze_pages(pages, question, session_folder):
    """
    Анализирует страницы чертежей с помощью VLM модели для поиска элементов.
    
    Args:
        pages: список страниц с путями и метаданными
        question: вопрос пользователя (класс элемента для поиска)
        session_folder: папка сессии для сохранения результатов
    
    Returns:
        list: результаты анализа по каждой странице
    """
    model = os.environ.get('DRAWING_VLM_MODEL', 'gemma4:31b')
    results = []
    
    # Промпт для анализа страницы
    prompt = f"""Ты анализируешь чертеж здания. Найди на этом чертеже следующие элементы: {question}

Для каждого найденного элемента предоставь:
1. Имя объекта (object_name) - краткое название
2. Размеры (dimensions) - все доступные размеры
3. Материал (material) - из чего сделан элемент
4. Локацию (location) - где расположен на чертеже
5. Количество (quantity) - если указано
6. Уверенность (confidence) - high/medium/low

Отвечай ТОЛЬКО в формате JSON:
{{
    "elements": [
        {{
            "object_name": "...",
            "dimensions": "...",
            "material": "...",
            "location": "...",
            "quantity": "...",
            "confidence": "high"
        }}
    ]
}}
"""
    
    for page_info in pages:
        page_path = page_info['path']
        page_num = page_info.get('page_num', 1)
        source_file = page_info.get('source_file', '')
        
        try:
            # Конвертируем PDF страницу в изображение или берем готовое изображение
            if page_path.lower().endswith('.pdf'):
                # Открываем PDF и конвертируем первую страницу в изображение
                doc = fitz.open(page_path)
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_path = os.path.join(session_folder, f'temp_page_{page_num}.png')
                pix.save(img_path)
                doc.close()
                image_path = img_path
            else:
                image_path = page_path
            
            # Отправляем изображение модели
            with open(image_path, 'rb') as img_file:
                response = ollama.chat(
                    model=model,
                    messages=[{
                        'role': 'user',
                        'content': prompt,
                        'images': [img_file.read()]
                    }]
                )
            
            # Парсим ответ
            response_text = response['message']['content']
            
            # Пытаемся извлечь JSON из ответа
            elements = []
            try:
                # Ищем JSON в ответе
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    data = json.loads(json_str)
                    elements = data.get('elements', [])
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, создаем элемент с сырым текстом
                elements = [{
                    'object_name': f'Элемент на странице {page_num}',
                    'dimensions': 'не указаны',
                    'material': 'не указан',
                    'location': 'не указана',
                    'quantity': 'не указано',
                    'confidence': 'medium',
                    'raw_response': response_text[:500]
                }]
            
            # Добавляем информацию о странице к каждому элементу
            for element in elements:
                element['page_number'] = page_num
                element['source_file'] = source_file
            
            results.append({
                'page_number': page_num,
                'source_file': source_file,
                'elements': elements
            })
            
            # Очищаем временный файл
            if page_path.lower().endswith('.pdf') and os.path.exists(image_path):
                os.remove(image_path)
                
        except Exception as e:
            results.append({
                'page_number': page_num,
                'source_file': source_file,
                'error': str(e),
                'elements': []
            })
    
    return results


if __name__ == '__main__':
    # Тестовый запуск
    print("Page analyzer module loaded successfully")
