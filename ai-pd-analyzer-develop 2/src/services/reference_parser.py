import os
import json
from pathlib import Path
import ollama
import re

from .config import load_config
from .documents_registry import is_fz_document

OLLAMA_URL = load_config().ollama_url

# ======== 5 ЭТАП ==========
def punktМОРВ(progress_callback=None, output_folder=''):
    """
    Извлечение номеров пунктов из найденных ссылок
    
    Args:
        progress_callback: опциональная функция callback(progress_0_to_1, message_string)
    """
    # Константы
    MOPB_FOLDER = os.path.join(output_folder, "MOPB_ссылки")
    OUTPUT_FOLDER = os.path.join(output_folder, "MOPB_ссылки_с_номерами")
    
    print("  ЭТАП 3: ИЗВЛЕЧЕНИЕ НОМЕРОВ ИЗ JSON ФАЙЛОВ")
    
    if progress_callback:
        progress_callback(0.0, "Поиск JSON файлов с ссылками...")
    
    json_files = list(Path(MOPB_FOLDER).glob("*.json"))
    
    if not json_files:
        print(" JSON файлы не найдены!")
        if progress_callback:
            progress_callback(1.0, "JSON файлы не найдены")
        return
    
    if progress_callback:
        progress_callback(0.05, f"Найдено {len(json_files)} файлов для обработки")
    
    results = []
    total_files = len(json_files)
    
    for i, json_file in enumerate(json_files):
        # Прогресс: 5% - 90% распределяется между всеми файлами
        progress = 0.05 + ((i + 1) / total_files) * 0.85
        
        doc_code = json_file.stem  # Имя файла без расширения
        
        if progress_callback:
            progress_callback(
                progress,
                f"Извлечение номеров: {doc_code} ({i + 1}/{total_files})"
            )
        
        result = _process_json_file(json_file, OUTPUT_FOLDER)
        if result:
            results.append(result)
    
    if progress_callback:
        progress_callback(0.92, "Формирование итоговой статистики...")
    
    # ИТОГОВАЯ СТАТИСТИКА
    print("\n" + "="*80)
    print(" ИТОГОВАЯ СТАТИСТИКА")
    print("="*80)
    
    total_links = 0
    total_found = 0
    
    for r in results:
        print(f"\n{r['doc_code']}:")
        print(f"   Всего ссылок: {r['total']}")
        print(f"   Найдено номеров: {r['found']}")
        total_links += r['total']
        total_found += r['found']
    
    print(f"\nВсего обработано ссылок: {total_links}")
    print(f"Всего найдено номеров: {total_found}")
    if total_links > 0:
        print(f"Процент извлечения: {round(total_found / total_links * 100, 1)}%")
    
    if progress_callback:
        progress_callback(0.96, f"Извлечено {total_found} номеров из {total_links} ссылок")
    
    # Сохраняем сводную статистику
    summary = {
        "total_files_processed": len(results),
        "total_links": total_links,
        "total_numbers_found": total_found,
        "extraction_rate": round(total_found / total_links * 100, 1) if total_links > 0 else 0,
        "documents": results
    }
    
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    summary_path = os.path.join(OUTPUT_FOLDER, "сводка_извлечения_номеров.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    if progress_callback:
        progress_callback(1.0, f"Этап 3 завершён. Обработано {len(results)} документов")
    
    print(" ЭТАП 3 ЗАВЕРШЕН")
    print(f"  Результаты сохранены в папку: {OUTPUT_FOLDER}")
    print(f"  Сводка сохранена: {summary_path}")

def _process_json_file(json_file_path, output_folder):
   
    print(f"\n Обработка файла: {os.path.basename(json_file_path)}")
    print("="*80)
    
     
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    doc_code = data.get('doc_code', 'unknown')
    references = data.get('references', [])
    
    print(f"Документ: {doc_code}")
    print(f"Всего ссылок: {len(references)}")
    
    
    updated_references = []
    found_count = 0
    
    for i, ref in enumerate(references, 1):
        punkt_text = ref.get('punkt', '')
        page = ref.get('page', '?')
        full_paragraph = ref.get('punkt', 'full_paragraph')
        
        print(f"\n{i}. Страница {page}")
        print(f"   Текст: {punkt_text[:100]}...")
        
        if is_fz_document(doc_code):
            
            fz_components = _extract_fz_components_with_llm(punkt_text, doc_code)
            
            valid_components = _validate_fz_with_regex(punkt_text, fz_components, doc_code)
            
            if valid_components:
                ref['fz_references'] = valid_components
                found_count += 1
                print(f"    Найдены ссылки на ФЗ: {valid_components}")
            else:
                if 'fz_references' in ref:
                    del ref['fz_references']
                print(f"    Нет ссылок на ФЗ (после проверки)")
        else:
             
            numbers = _extract_punkt_numbers_with_llm(punkt_text, doc_code)
            
             
            valid_numbers = _validate_sp_with_regex(punkt_text, numbers, doc_code, full_paragraph)
            
            if valid_numbers:
                if valid_numbers[0]:
                    ref['punkt_numbers'] = valid_numbers
                    found_count += 1
                    print(f"     Найдены номера: {', '.join(valid_numbers)}")
            else:
                if 'punkt_numbers' in ref:
                    del ref['punkt_numbers']
                print(f"    Нет номеров пунктов (после проверки)")
        
        updated_references.append(ref)
    
    data['references'] = updated_references

    os.makedirs(output_folder, exist_ok=True)
    
    output_file = os.path.join(output_folder, os.path.basename(json_file_path))
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n Статистика по файлу:")
    print(f"   Всего ссылок: {len(references)}")
    print(f"   Найдено номеров: {found_count}")
    print(f"   Сохранено: {output_file}")
    
    return {
        'doc_code': doc_code,
        'total': len(references),
        'found': found_count
    }

def _extract_punkt_numbers_with_llm(punkt_text, doc_code):
   
    prompt = f"""Ты - эксперт по извлечению номеров пунктов из текстов нормативных документов.

Текст: "{punkt_text}"
Документ: {doc_code}

ВАЖНЕЙШЕЕ ПРАВИЛО:
Извлекай ВСЕ номера пунктов, которые относятся к документу {doc_code}, независимо от того, есть перед ними "п.", "пункт" или нет.

АЛГОРИТМ ДЕЙСТВИЙ:
1. Найди в тексте упоминание документа {doc_code}
2. Найди ВСЕ числовые последовательности с точками (например: 3.1, 4.2.5, 5.1.3) которые находятся в контексте этого документа
3. Если упоминается толко {doc_code} без пунктов, то верни пустой массив. ОЧЕНЬ ВАЖНО, ЧТОБЫ БЫЛ ПУСТОЙ МАССИВ, ЕСЛИ УПОМЯНУТ ТОЛЬКО ДОКМУЕНТ
3. Числовые последовательности могут быть:
   - БЕЗ префиксов: просто числа с точками
   - С префиксами: "п.", "п", "пункт", "пункты", "пп."
   - После слов: "согласно", "см.", "в соответствии с", "по"
4. Если видишь диапазон через дефис (например, 4.1-4.3) - разверни его полностью: ["4.1", "4.2", "4.3"]
5. Если видишь буквы со скобками (а), б), д) и т.д.) - игнорируй их, извлекай только числовую часть
6. Номер не должен совпадать с {doc_code}, иначе верни пустой массив
7. Не выделяй номер пункта из номера {doc_code}. 
8. Перед номером пункта никогда не встречается слово "поз." или "табл."

КОГДА ВОЗВРАЩАТЬ ПУСТОЙ МАССИВ:
- Текст начинается с "табл." или "таблица"
- В тексте упоминается "табл." или "таблица" в связи с пунктом
- В тексте нет упоминания {doc_code}
- Текст содержит только одиночное число без точек (например, просто "13130")
- Текст содержит упоминание только {doc_code} без привязки к пунктам

ПРИМЕРЫ ИЗВЛЕЧЕНИЯ:
Текст: "п. 3.1 {doc_code}"
Результат: ["3.1"]

Текст: "3.1 {doc_code}"
Результат: ["3.1"]

Текст: "обратите внимание на 3.1 и 3.2 {doc_code}"
Результат: ["3.1", "3.2"]

Текст: "4.1-4.3 {doc_code}"
Результат: ["4.1", "4.2", "4.3"]

Текст: "согласно 5.2.1 {doc_code}"
Результат: ["5.2.1"]

Текст: "п. д) 7.14 {doc_code}"
Результат: ["7.14"]

Текст: "д) 7.14 {doc_code}"
Результат: ["7.14"]

Текст: "3.6 {doc_code}"
Результат: ["3.6"]

Текст: "табл. 1 {doc_code}"
Результат: []

Текст: "поз. 3.1 {doc_code}"
Результат: []

Текст: "табл. 1, поз. 3.1 {doc_code}"
Результат: []

Текст: "согласно {doc_code}"
Результат: []

Текст: "просто текст без номеров {doc_code}"
Результат: []

Текст: "123" (если это не номер пункта)
Результат: []

Текст: "5.3.1. Согласно п. 6.1.8 {doc_code}"
Результат: [6.1.8]

Текст: "5.3.1. Согласно п. 6.1.8 {doc_code}"
Результат: [6.1.8]

Верни ТОЛЬКО JSON массив. Никаких пояснений.
"""

    try:
        client = ollama.Client(host=OLLAMA_URL, timeout=60.0)
        response = client.chat(
            model='yandex/YandexGPT-5-Lite-8B-instruct-GGUF:latest',
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 200}
        )
        
        result = response['message']['content'].strip()
        
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return []
        
    except Exception as e:
        print(f"   ❌ Ошибка LLM: {e}")
        return []

def _extract_fz_components_with_llm(punkt_text, doc_code):
    
    prompt = f"""Ты - эксперт. Извлеки номера статей и частей из текста ссылки на {doc_code}.

Текст: "{punkt_text}"

ПРАВИЛА:
1. Номер статьи ищется ПОСЛЕ слов: "ст.", "статья", "статьи"
2. Номер части ищется ПОСЛЕ слов: "ч.", "часть", "части"
3. Ссылка должна относиться только к {doc_code}
4. Если в тексте есть "ст. 76, п. 1" - верни статью 76
5. Если это просто упоминание закона без номера статьи - верни пустой массив []
7. Если помимо таблицы указана статья, то верни статью и пункт
8. Игнорируй слово "таблица", "табл.", обращай внимание только на "ч." и "ст."

ПРИМЕРЫ:
"ст. 6" → [{{"article": "6", "part": null}}]
"ч.5 ст.134" → [{{"article": "134", "part": "5"}}]
"ч. 11 ст. 87" → [{{"article": "87", "part": "11"}}]
"ст. 71, табл. 15" → [{{"article": "71", "part": null}}]
"ст. 76, п. 1" → [{{"article": "76", "part": null}}]
"ч.3, ст.70, таблица 15" → [{{"article": "70", "part": 3}}]
"таблица 15" → []
"ч.1 ст. 73 и табл. 17" → [{{"article": "73", "part": 1}}]
 
"ст. 71, табл. 15 Технического регламента №{doc_code}" → [{{"article": "71", "part": null}}]

"№{doc_code}" → []
"Федеральный закон от 22.07.2008 № {doc_code}" → []

Верни ТОЛЬКО JSON массив объектов. Если нет статьи - верни [].
"""
    
    try:
        client = ollama.Client(host=OLLAMA_URL, timeout=60.0)
        response = client.chat(
            model='yandex/YandexGPT-5-Lite-8B-instruct-GGUF:latest',
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 500}
        )
        
        result = response['message']['content'].strip()
        
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return []
        
    except Exception as e:
        print(f"   ❌ Ошибка LLM: {e}")
        return []

def _validate_sp_with_regex(punkt_text, numbers, doc_code, full_paragraph):
   
    if not numbers:
        return numbers
    
    # Если значений несколько считается что вид мог быть  п.4.1-4.3
    if len(numbers) >= 3 and numbers[0] in punkt_text and numbers[-1] in punkt_text:
        return numbers 
    
    doc_code_num = doc_code.removeprefix("СП").strip()

    valid_numbers = []
    for num in numbers:
        pattern = r'п?\.?\s*' + re.escape(num)
        pattern_pos = r'поз\.?\s?' + re.escape(num) + r'\b'
        pattern_tab = r'(табл\.|таблица)\s?'+ re.escape(num) + r'\b'
        if re.search(pattern, punkt_text, re.IGNORECASE):
            if doc_code_num != num:
                if not re.search(pattern_pos, punkt_text, re.IGNORECASE) and not re.search(pattern_tab, punkt_text, re.IGNORECASE):
                    valid_numbers.append(num)
    if valid_numbers:
        return valid_numbers
    else:
        return []

def _validate_fz_with_regex(punkt_text, fz_components, doc_code):
   
    if not fz_components:
        return fz_components
    
   
    article_keywords = [r'ст\.', r'статья', r'статьи']
    has_article_keyword = False
    for kw in article_keywords:
        if re.search(kw, punkt_text, re.IGNORECASE):
            has_article_keyword = True
            break
    
    if not has_article_keyword:
        return []
    
    
    #table_patterns = [r'табл\.', r'таблица', r'таблиц']
    #for pattern in table_patterns:
    #    if re.search(pattern, punkt_text, re.IGNORECASE):
    #        return []
    
    
    valid_components = []
    law_number = doc_code.split('-', 1)[0]
    for comp in fz_components:
        article = comp.get('article')
        part = comp.get('part')
        
        if not article:
            continue
        
        
        if article == doc_code or article == law_number:
            # 
            if not re.search(r'ст\.\s*' + re.escape(article), punkt_text, re.IGNORECASE):
                continue
        
      
        # Проеряем что номер статьи присутствует в тексте ссылки.
        if str(article).lower() not in punkt_text.lower():
            continue
        
         
        if part:
            # ищем номер части
            if str(part).lower() not in punkt_text.lower():
                continue
        
        valid_components.append(comp)
    
    return valid_components

