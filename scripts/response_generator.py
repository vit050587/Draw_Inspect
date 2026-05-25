"""
Модуль формирования ответа пользователю на основе анализа страниц.
Использует модель gemma4:31b через Ollama для генерации структурированного ответа.
"""

import os
import ollama
import json
from typing import List, Dict, Any
from pathlib import Path

# Конфигурация Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
RESPONSE_MODEL = os.getenv("RESPONSE_GENERATION_MODEL", "gemma4:31b")

# Путь к файлу с промптом
PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'
RESPONSE_PROMPT_FILE = PROMPTS_DIR / 'response_prompt.txt'


def load_response_prompt(question: str, context: str) -> str:
    """Загружает промпт генерации ответа из файла и подставляет вопрос и контекст"""
    try:
        with open(RESPONSE_PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        return prompt_template.format(question=question, context=context)
    except Exception as e:
        print(f"❌ Ошибка загрузки промпта из {RESPONSE_PROMPT_FILE}: {e}")
        # Возвращаем дефолтный промпт в случае ошибки
        return f"""
Вы помощник, специализирующийся на анализе пожарной безопасности по чертежам зданий.

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

РЕЗУЛЬТАТЫ АНАЛИЗА ЧЕРТЕЖЕЙ:
{context}

На основе приведенного выше анализа предоставьте структурированный ответ:

1. Дайте четкий, прямой ответ на вопрос
2. Перечислите конкретные находки с точными измерениями, где они доступны
3. Для каждой находки укажите, на какой странице/чертеже она была найдена
4. Если информация недоступна или неясна, прямо заявите об этом

Форматируйте ваш ответ в JSON следующим образом:
{{
    "answer": "Прямой ответ на вопрос",
    "findings": [
        {{
            "object_name": "Название объекта",
            "dimensions": "Все размеры объекта",
            "material": "Материалы из которых построен объект",
            "page_number": 5,
            "source_file": "filename.pdf",
            "confidence": "high/medium/low"
        }}
    ],
    "summary": "Краткое резюме всех находок"
}}

Отвечайте ТОЛЬКО действительным JSON, без дополнительного текста.
"""


def generate_response(analysis_results: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
    """
    Формирует ответ пользователю на основе результатов анализа страниц.
    Сначала агрегирует данные из всех JSON-отчетов, затем использует LLM для форматирования.
    
    Args:
        analysis_results: Список результатов анализа страниц (содержит page_num, source_file, analysis, found_objects)
        question: Вопрос пользователя
        
    Returns:
        Словарь с ответом, находками и ссылками на страницы
    """
    client = ollama.Client(host=OLLAMA_URL, timeout=300.0)
    
    # Агрегируем данные из всех отчетов
    all_findings = []
    page_numbers = []
    source_files = set()
    
    for result in analysis_results:
        if result.get('relevant', False):
            page_num = result.get('page_num', 1)
            source_file = result.get('source_file', 'unknown')
            
            page_numbers.append(page_num)
            source_files.add(source_file)
            
            # Извлекаем found_objects напрямую из результата анализа
            # (page_analyzer.py сохраняет их в поле 'found_objects')
            found_objects = result.get('found_objects', [])
            
            if found_objects and isinstance(found_objects, list):
                for obj in found_objects:
                    finding = {
                        'object_name': obj.get('name', 'Неизвестный объект'),
                        'dimensions': obj.get('characteristics', {}).get('dimensions', 'размеры не указаны'),
                        'material': obj.get('characteristics', {}).get('material', 'материал не указан'),
                        'location': obj.get('characteristics', {}).get('location', ''),
                        'quantity': obj.get('characteristics', {}).get('quantity', ''),
                        'page_number': page_num,
                        'source_file': source_file,
                        'confidence': obj.get('confidence', 'medium'),
                        'additional_params': obj.get('characteristics', {}).get('additional_params', '')
                    }
                    all_findings.append(finding)
            else:
                # Если found_objects нет, используем текстовый анализ
                analysis_text = result.get('analysis', 'Нет данных')
                finding = {
                    'object_name': 'Объект по вопросу',
                    'dimensions': 'см. детали в анализе',
                    'material': 'см. детали в анализе',
                    'location': '',
                    'quantity': '',
                    'page_number': page_num,
                    'source_file': source_file,
                    'confidence': 'medium',
                    'analysis_text': analysis_text[:500] if len(analysis_text) > 500 else analysis_text
                }
                all_findings.append(finding)
    
    # Если не нашли объектов, возвращаем пустой ответ
    if not all_findings:
        return {
            'answer': f"По запросу '{question}' ничего не найдено в предоставленных чертежах.",
            'findings': [],
            'page_references': [],
            'summary': 'Объекты не найдены'
        }
    
    # Формируем контекст для LLM из агрегированных данных
    context_parts = []
    for i, finding in enumerate(all_findings, 1):
        context_parts.append(f"""
НАХОДКА {i}:
- Объект: {finding['object_name']}
- Размеры: {finding['dimensions']}
- Материал: {finding['material']}
- Страница: {finding['page_number']}
- Файл: {finding['source_file']}
- Локация: {finding.get('location', '')}
- Количество: {finding.get('quantity', '')}
- Дополнительно: {finding.get('additional_params', '')}
""")
    
    context = "\n".join(context_parts)
    
    # Формируем промпт для генерации итогового ответа
    response_prompt = f"""
Вы помощник, специализирующийся на анализе пожарной безопасности по чертежам зданий.

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

АГРЕГИРОВАННЫЕ ДАННЫЕ ИЗ ВСЕХ СТРАНИЦ:
{context}

На основе приведенных данных предоставьте ОЧЕНЬ ПОДРОБНЫЙ структурированный ответ:

1. Дайте полный ответ на вопрос, перечислив ВСЕ найденные объекты
2. Для КАЖДОГО объекта укажите:
   - На какой странице (номер) и в каком файле найден
   - Все размеры которые указаны
   - Материалы из которых сделан объект
   - Локацию и количество если доступны
3. Сгруппируйте информацию по объектам (если один тип объекта встречается на нескольких страницах - объедините информацию)
4. Если информация недоступна или неясна, прямо заявите об этом

Форматируйте ваш ответ в JSON следующим образом:
{{
    "answer": "Подробный прямой ответ на вопрос с перечислением всех объектов",
    "findings": [
        {{
            "object_name": "Название объекта",
            "dimensions": "Все размеры объекта",
            "material": "Материалы из которых построен объект",
            "pages": [1, 5, 8],
            "files": ["file1.pdf", "file2.pdf"],
            "locations": ["локация 1", "локация 2"],
            "total_quantity": "общее количество",
            "confidence": "high/medium/low"
        }}
    ],
    "summary": "Краткое резюме всех находок с общей статистикой"
}}

Отвечайте ТОЛЬКО действительным JSON, без дополнительного текста.
"""
    
    try:
        response = client.chat(
            model=RESPONSE_MODEL,
            messages=[{'role': 'user', 'content': response_prompt}],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 4096}
        )
        
        response_text = response['message']['content'].strip()
        
        # Извлекаем JSON из ответа
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Если JSON не найден, создаем структуру вручную из агрегированных данных
            result = {
                'answer': f"Найдено {len(all_findings)} объектов по вопросу: {question}",
                'findings': all_findings,
                'summary': f'Всего найдено {len(all_findings)} объектов на {len(set(page_numbers))} страницах'
            }
        
        # Добавляем ссылки на страницы
        result['page_references'] = sorted(list(set(page_numbers)))
        result['source_files'] = list(source_files)
        
        return result
        
    except Exception as e:
        print(f"Ошибка генерации ответа: {e}")
        # Возвращаем ответ в случае ошибки - используем агрегированные данные напрямую
        return _generate_fallback_response(all_findings, question, page_numbers, source_files, str(e))


def _generate_fallback_response(all_findings: List[Dict[str, Any]], question: str, page_numbers: List[int], source_files: set, error: str) -> Dict[str, Any]:
    """
    Генерирует резервный ответ в случае ошибки LLM на основе агрегированных данных.
    """
    if not all_findings:
        return {
            'answer': f"По запросу '{question}' ничего не найдено.",
            'findings': [],
            'page_references': [],
            'source_files': list(source_files),
            'summary': 'Объекты не найдены',
            'error': error
        }
    
    # Группируем находки по имени объекта
    grouped = {}
    for finding in all_findings:
        obj_name = finding['object_name']
        if obj_name not in grouped:
            grouped[obj_name] = {
                'object_name': obj_name,
                'dimensions': finding['dimensions'],
                'material': finding['material'],
                'pages': [],
                'files': [],
                'locations': [],
                'quantities': [],
                'confidence': finding['confidence']
            }
        grouped[obj_name]['pages'].append(finding['page_number'])
        grouped[obj_name]['files'].append(finding['source_file'])
        if finding.get('location'):
            grouped[obj_name]['locations'].append(finding['location'])
        if finding.get('quantity'):
            grouped[obj_name]['quantities'].append(finding['quantity'])
    
    # Формируем итоговые находки с объединением данных
    final_findings = []
    for obj_name, data in grouped.items():
        final_finding = {
            'object_name': data['object_name'],
            'dimensions': data['dimensions'],
            'material': data['material'],
            'pages': sorted(list(set(data['pages']))),
            'files': list(set(data['files'])),
            'locations': data['locations'] if data['locations'] else ['локация не указана'],
            'total_quantity': ', '.join(data['quantities']) if data['quantities'] else 'количество не указано',
            'confidence': data['confidence']
        }
        final_findings.append(final_finding)
    
    return {
        'answer': f"Найдено {len(final_findings)} типов объектов по вопросу: {question}",
        'findings': final_findings,
        'page_references': sorted(list(set(page_numbers))),
        'source_files': list(source_files),
        'summary': f'Всего найдено {len(final_findings)} типов объектов на {len(set(page_numbers))} страницах из {len(source_files)} файла(ов)',
        'error': error
    }
