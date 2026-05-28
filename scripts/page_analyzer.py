import ollama
import os
import json
from PIL import Image
import fitz  # PyMuPDF
import io
from PIL import ImageEnhance, ImageFilter

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
    prompt = f"""
    Ты — эксперт по анализу архитектурно-строительных чертежей. Тебе предоставлен чертёж здания. Твоя задача — найти на нём указанные элементы {question} (список может включать как конкретные объекты, так и их типы: окна, двери, колонны, лестницы, арматурные сетки и т.д.).
Для каждого обнаруженного элемента предоставь ответ строго в следующем формате (один блок на элемент):
1. Имя объекта (object_name) — краткое название элемента (например, «Окно ПВХ», «Железобетонная колонна», «Вентиляционный канал»).
2. Размеры (dimensions) — все размеры, указанные на чертеже (длина, ширина, высота, диаметр, сечение и т.п.). Если размеров несколько — перечисли их все. Если размер отсутствует — напиши «не указано».
3. Материал (material) — материал изготовления (бетон, сталь, дерево, пластик и т.д.) согласно чертежу или условным обозначениям. Если материал не обозначен — напиши «не определён».
4. Количество (quantity) — количество одинаковых элементов, указанное в спецификации, на выносках или в легенде. Если количество явно не задано — напиши «1» (как единичный найденный объект).
Примечания:
1. Учитывай масштаб чертежа, размерные линии, маркировку узлов и спецификации.
2. Если элемент встречается несколько раз с разными характеристиками (например, окна разных типов), опиши каждый вариант отдельно.
3. Если элемент не найден — напиши: «Элемент {question} на чертеже не обнаружен».

Отвечай ТОЛЬКО в формате JSON:
{{
    "elements": [
        {{
            "object_name": "...",
            "dimensions": "...",
            "material": "...",
            "quantity": "..."
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
                doc = fitz.open(page_path)
                page = doc[0]
                dpi = 300
                pix = page.get_pixmap(dpi=dpi)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
    
                # Постобработка
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
                img = img.filter(ImageFilter.SHARPEN)
    
                img_path = os.path.join(session_folder, f'temp_page_{page_num}.png')
                img.save(img_path, optimize=True)
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
                    }],
                    options={
                        'temperature': 0.0,
                        'num_predict': 12000,
                        'top_k': 10,      # опционально
                        'top_p': 0.9     # опционально
                    }
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
                    'quantity': 'не указано'
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
