#!/usr/bin/env python3
"""
Скрипт для обогащения файла elements.json поисковыми ключами (синонимами и ассоциациями)
с использованием LLM gemma3:27b через Ollama API.
"""

import json
import requests
import sys
from typing import Optional, List

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:27b"
INPUT_FILE = "data/elements.json"
OUTPUT_FILE = "data/elements_enriched.json"


def get_search_keys_from_llm(class_name: str, subclass_name: Optional[str] = None) -> List[str]:
    """
    Запрашивает у LLM gemma3:27b создание 3-4 синонимов/ассоциаций для заданного класса/подкласса.
    
    Args:
        class_name: Название класса
        subclass_name: Название подкласса (опционально)
    
    Returns:
        Список синонимов/ассоциаций
    """
    # Формируем строку для запроса
    if subclass_name:
        query_text = f"{class_name} - {subclass_name}"
    else:
        query_text = class_name
    
    # Формируем промпт для LLM
    prompt = f"""Для строительного элемента "{query_text}" придумай 3-4 синонима или ассоциативных выражения (поисковых ключа), которые могут использоваться для поиска этого элемента. 
Ответ должен быть строго в формате JSON массива строк на русском языке, без какого-либо дополнительного текста.
Пример ответа: ["синоним 1", "синоним 2", "синоним 3"]

Элемент: {query_text}
Поисковые ключи:"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 256
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        generated_text = result.get("response", "")
        
        # Парсим ответ как JSON
        try:
            # Пытаемся найти JSON массив в ответе
            start_idx = generated_text.find("[")
            end_idx = generated_text.rfind("]") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = generated_text[start_idx:end_idx]
                search_keys = json.loads(json_str)
                return search_keys
            else:
                print(f"Не удалось найти JSON в ответе для '{query_text}': {generated_text[:200]}")
                return []
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON для '{query_text}': {e}")
            print(f"Полученный текст: {generated_text[:200]}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Ollama API для '{query_text}': {e}")
        return []


def enrich_elements(input_file: str, output_file: str):
    """
    Обогащает элементы из входного файла поисковыми ключами и сохраняет в выходной файл.
    
    Args:
        input_file: Путь к входному файлу JSON
        output_file: Путь к выходному файлу JSON
    """
    # Читаем входной файл
    with open(input_file, 'r', encoding='utf-8') as f:
        elements = json.load(f)
    
    print(f"Загружено {len(elements)} элементов из {input_file}")
    
    enriched_count = 0
    skipped_count = 0
    
    for i, element in enumerate(elements):
        class_name = element.get("class")
        subclass_name = element.get("subclass")
        
        # Пропускаем элементы без класса
        if not class_name:
            print(f"[{i+1}/{len(elements)}] Пропущено: нет класса")
            element["search_keys"] = []
            skipped_count += 1
            continue
        
        # Формируем описание для запроса
        if subclass_name:
            description = f"{class_name} - {subclass_name}"
        else:
            description = class_name
        
        print(f"[{i+1}/{len(elements)}] Обработка: {description}")
        
        # Получаем поисковые ключи от LLM
        search_keys = get_search_keys_from_llm(class_name, subclass_name)
        
        if search_keys:
            element["search_keys"] = search_keys
            enriched_count += 1
            print(f"  Получено ключей: {len(search_keys)}")
        else:
            element["search_keys"] = []
            print(f"  Не удалось получить ключи")
    
    # Сохраняем результат
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== Результаты ===")
    print(f"Всего элементов: {len(elements)}")
    print(f"Обогащено: {enriched_count}")
    print(f"Пропущено (нет класса): {skipped_count}")
    print(f"Результат сохранен в: {output_file}")


if __name__ == "__main__":
    # Проверяем доступность Ollama API
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("Ollama API доступен")
        else:
            print(f"Ollama API вернул статус: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("Ошибка: Не удалось подключиться к Ollama API.")
        print("Убедитесь, что Ollama запущен (команда: ollama serve)")
        sys.exit(1)
    
    # Запускаем обогащение
    enrich_elements(INPUT_FILE, OUTPUT_FILE)
