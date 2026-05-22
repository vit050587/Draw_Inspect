"""
Модуль анализа страниц с чертежами с использованием модели gemma4:31b через Ollama.
Анализирует каждую страницу и сохраняет результаты в отдельной папке сессии.
"""

import os
import ollama
import json
from typing import List, Dict, Any

# Конфигурация Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ANALYSIS_MODEL = os.getenv("DRAWING_ANALYSIS_MODEL", "gemma4:31b")


def analyze_pages(images: List[Dict[str, Any]], question: str, output_folder: str) -> List[Dict[str, Any]]:
    """
    Анализирует страницы с чертежами для ответа на вопрос пользователя.
    
    Args:
        images: Список словарей с информацией об изображениях
        question: Вопрос пользователя
        output_folder: Папка для сохранения результатов анализа
        
    Returns:
        Список результатов анализа для каждого изображения
    """
    # Создаем папку для результатов анализа
    analysis_folder = os.path.join(output_folder, 'analysis')
    os.makedirs(analysis_folder, exist_ok=True)
    
    client = ollama.Client(host=OLLAMA_URL, timeout=300.0)
    
    results = []
    
    for img_info in images:
        try:
            image_path = img_info['image_path']
            page_num = img_info.get('page_num', 1)
            source_file = img_info.get('source_file', 'unknown')
            category = img_info.get('category', 'unknown')
            
            # Формируем промпт для анализа
            analysis_prompt = f"""
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
            
            # Кодируем PDF файл в base64
            with open(image_path, 'rb') as f:
                import base64
                file_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Отправляем запрос к модели
            response = client.chat(
                model=ANALYSIS_MODEL,
                messages=[{
                    'role': 'user',
                    'content': analysis_prompt,
                    'images': [file_data]
                }],
                stream=False,
                options={'temperature': 0.1, 'num_predict': 2048}
            )
            
            analysis_text = response['message']['content'].strip()
            
            # Сохраняем результат анализа в файл
            result_filename = f"analysis_page_{page_num}_{source_file.replace('.pdf', '')}.json"
            result_path = os.path.join(analysis_folder, result_filename)
            
            result_data = {
                'page_num': page_num,
                'source_file': source_file,
                'category': category,
                'question': question,
                'analysis': analysis_text,
                'image_path': image_path
            }
            
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            results.append({
                'page_num': page_num,
                'source_file': source_file,
                'category': category,
                'image_path': image_path,
                'analysis': analysis_text,
                'result_file': result_path,
                'relevant': True
            })
            
            print(f"Проанализировано: страница {page_num} из {source_file}")
            
        except Exception as e:
            print(f"Ошибка анализа изображения {img_info.get('image_path', 'unknown')}: {e}")
            results.append({
                'page_num': img_info.get('page_num', 1),
                'source_file': img_info.get('source_file', 'unknown'),
                'category': img_info.get('category', 'unknown'),
                'image_path': img_info.get('image_path', ''),
                'analysis': f"Ошибка анализа: {str(e)}",
                'result_file': None,
                'relevant': False,
                'error': str(e)
            })
    
    return results
