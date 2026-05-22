"""
Модуль формирования ответа пользователю на основе анализа страниц.
Использует модель gemma4:31b через Ollama для генерации структурированного ответа.
"""

import os
import ollama
import json
from typing import List, Dict, Any

# Конфигурация Ollama
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
RESPONSE_MODEL = os.getenv("RESPONSE_GENERATION_MODEL", "gemma4:31b")


def generate_response(analysis_results: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
    """
    Формирует ответ пользователю на основе результатов анализа страниц.
    
    Args:
        analysis_results: Список результатов анализа страниц
        question: Вопрос пользователя
        
    Returns:
        Словарь с ответом, находками и ссылками на страницы
    """
    client = ollama.Client(host=OLLAMA_URL, timeout=300.0)
    
    # Подготавливаем контекст из результатов анализа
    context_parts = []
    for result in analysis_results:
        if result.get('relevant', False) and result.get('analysis'):
            page_num = result.get('page_num', 1)
            source_file = result.get('source_file', 'unknown')
            analysis = result.get('analysis', '')
            
            context_parts.append(f"""
СТРАНИЦА {page_num} (файл: {source_file}):
{analysis}
""")
    
    context = "\n\n".join(context_parts)
    
    # Формируем промпт для генерации ответа
    response_prompt = f"""
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
            "description": "Конкретная находка",
            "page_number": 5,
            "source_file": "filename.pdf",
            "confidence": "high/medium/low"
        }}
    ],
    "summary": "Краткое резюме всех находок"
}}

Отвечайте ТОЛЬКО действительным JSON, без дополнительного текста.
"""
    
    try:
        response = client.chat(
            model=RESPONSE_MODEL,
            messages=[{'role': 'user', 'content': response_prompt}],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 2048}
        )
        
        response_text = response['message']['content'].strip()
        
        # Извлекаем JSON из ответа
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Если JSON не найден, создаем структуру вручную
            result = {
                'answer': response_text,
                'findings': [],
                'summary': ''
            }
        
        # Добавляем ссылки на страницы
        page_refs = list(set([f['page_number'] for f in result.get('findings', []) if 'page_number' in f]))
        result['page_references'] = sorted(page_refs)
        
        return result
        
    except Exception as e:
        print(f"Ошибка генерации ответа: {e}")
        # Возвращаем ответ в случае ошибки
        return _generate_fallback_response(analysis_results, question, str(e))


def _generate_fallback_response(analysis_results: List[Dict[str, Any]], question: str, error: str) -> Dict[str, Any]:
    """
    Генерирует резервный ответ в случае ошибки LLM.
    """
    findings = []
    page_numbers = []
    
    for result in analysis_results:
        if result.get('relevant', False):
            page_num = result.get('page_num', 1)
            source_file = result.get('source_file', 'unknown')
            analysis = result.get('analysis', 'Нет данных')
            
            page_numbers.append(page_num)
            findings.append({
                'description': f"Анализ страницы {page_num}: {analysis[:200]}...",
                'page_number': page_num,
                'source_file': source_file,
                'confidence': 'medium'
            })
    
    return {
        'answer': f"На основе анализа {len(page_numbers)} чертежей voici информацию по вопросу: {question}",
        'findings': findings,
        'page_references': sorted(list(set(page_numbers))),
        'summary': f'Анализ завершен. Найдено {len(findings)} релевантных элементов.',
        'error': error
    }
