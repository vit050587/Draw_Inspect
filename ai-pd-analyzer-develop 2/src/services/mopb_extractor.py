import os
import json
import ollama
import fitz
import re
import copy

from .config import load_config
from .documents_registry import is_fz_document, load_documents
from .prompt_manager import PromptManager
from .ollama_service import OllamaService

OLLAMA_URL = load_config().ollama_url
NORMS_MODEL = load_config().norms_model
REPORT_FILENAME = load_config().report_filename

ollama_service = OllamaService(PromptManager())

# ======== 4 ЭТАП ==========
def searchМОРВ(MOPB_PDF, progress_callback=None, output_folder=''):
    """
    Поиск всех ссылок на СП и статьи закона в MOPB.pdf
    Двухэтапный анализ: сначала ищем ссылки, потом будем выделять номера пунктов
    
    Args:
        MOPB_PDF: путь к PDF файлу
        progress_callback: опциональная функция callback(progress_0_to_1, message_string)
    """

    report_path = os.path.join(output_folder, REPORT_FILENAME)
    with open(report_path, mode="a", encoding="utf-8") as report:
        print("  ДВУХЭТАПНЫЙ АНАЛИЗ ДОКУМЕНТА MOPB.pdf", file = report)
        print("  ДВУХЭТАПНЫЙ АНАЛИЗ ДОКУМЕНТА MOPB.pdf")

    # ======== 4 ЭТАП ==========
    OUTPUT_FOLDER = os.path.join(output_folder, "MOPB_ссылки")
    
    if progress_callback:
        progress_callback(0.0, "Загрузка списка документов...")

    DOCUMENTS = load_documents()
    print(DOCUMENTS)

    with open(report_path, mode="a", encoding="utf-8") as report:
        print(DOCUMENTS, file=report)
        
    if progress_callback:
        progress_callback(0.05, f"Загружено {len(DOCUMENTS)} типов документов для поиска")
    
    results = []
    
    # Извлечение текста из PDF
    if progress_callback:
        progress_callback(0.1, "Извлечение текста из PDF...")
    
    pages_text = _extract_text_from_MOPB(MOPB_PDF, report_path=report_path)
    
    if progress_callback:
        progress_callback(0.3, f"Извлечено {len(pages_text)} страниц текста")
    
    # Обработка каждого документа
    total_docs = len(DOCUMENTS)
    
    for i, doc in enumerate(DOCUMENTS):
        # Прогресс: 30% - 90% распределяется между всеми документами
        progress = 0.3 + ((i + 1) / total_docs) * 0.6
        
        doc_code = doc.get('code', doc.get('name', f'doc_{i}'))
        
        if progress_callback:
            progress_callback(
                progress,
                f"Поиск ссылок на {doc_code} ({i + 1}/{total_docs})"
            )
        
        result = _process_document(MOPB_PDF, doc, pages_text, OUTPUT_FOLDER, report_path)
        
        if result:
            results.append(result)
    
    if progress_callback:
        progress_callback(0.92, "Формирование итоговой статистики...")
    
    # ИТОГОВАЯ СТАТИСТИКА
    with open(report_path, mode="a", encoding="utf-8") as report:
        print("\n" + "="*80, file=report)
        print(" ИТОГОВАЯ СТАТИСТИКА", file=report)
        print("="*80, file=report)
    
    total_refs = 0
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        for r in results:
            print(f"\n{r['doc_code']}: {r['references_count']} ссылок", file=report)
            print(f"     {r['json_file']}", file=report)
            total_refs += r['references_count']
    
        print(f"\nВсего найдено ссылок: {total_refs}", file=report)
        print(f"Обработано документов: {len(results)}", file=report)
    
    if progress_callback:
        progress_callback(0.96, f"Найдено {total_refs} ссылок в {len(results)} документах")
    
    # Сохраняем сводную статистику
    summary = {
        "total_documents_processed": len(results),
        "total_references_found": total_refs,
        "documents": results
    }
    
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    summary_path = os.path.join(OUTPUT_FOLDER, "сводка_поиска.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    if progress_callback:
        progress_callback(1.0, f"Поиск завершён. Найдено {total_refs} ссылок")
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"  Сводка сохранена: {summary_path}", file = report)
        print("  РАБОТА ЗАВЕРШЕНА", file = report)
    
    return results

def _process_document(MOPB_PDF, doc, doc_text, output_folder, report_path):
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"🏁 ОБРАБОТКА {doc['code']}", file = report)
        print(f"🏁 ОБРАБОТКА {doc['code']}")
     
    os.makedirs(output_folder, exist_ok=True)
     
    doc_safe = doc['code'].replace(' ', '_').replace('-', '_')

    output_json = os.path.join(output_folder, f"MOPB_{doc_safe}_пункты_полные.json")

    # составляем альтернативные варианты как указанные + код с отсутсвующими пробелами + переносы строк
    alternatives = [doc["code"]] + doc["codes"] + [doc['code'].replace(" ", "")] + [doc['code'].replace(" ", "\n")] + [doc['code'].replace(" ", " \n")] 
     
    matched_page_numbers, merged_pages_text = _extract_pages_with_doc_mention(MOPB_PDF, doc_text, doc['code'], alternatives = alternatives, report_path=report_path)
    
    if not matched_page_numbers:
        with open(report_path, mode="a", encoding="utf-8") as report:
            print(f"\n Страницы с упоминанием {doc['code']} не найдены. Пропускаем.", file = report)
        return None
    
    # Используем склеенный текст страниц, чтобы LLM видел целые абзацы.
    merged_pages_text = [{"text":p, "page_num":i+1} for i, p in enumerate(merged_pages_text) if i+1 in matched_page_numbers]
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"  ЭТАП 2: ПОИСК ССЫЛОК ЧЕРЕЗ LLM", file = report)
        print(f"  ЭТАП 2: ПОИСК ССЫЛОК ЧЕРЕЗ LLM")
     
    all_references = []
    
    for page_data in merged_pages_text:
        with open(report_path, mode="a", encoding="utf-8") as report:
            print(f"\n Анализ страницы {page_data['page_num']}...", file = report)
        
        # references1 = _extract_references_with_llm(
        #     page_data['text'], 
        #     page_data['page_num'], 
        #     doc['code'],
        #     doc['pattern'],
        #     report_path=report_path
        # )
        references = ollama_service.get_tg_model_answer("links_extraction", {"doc_code": doc['code'], "text": page_data['text']})
        
        for ref in references:
            #Дополнительная проверка для сводов правил СП
            if is_fz_document(doc['code']) or (doc['code'] in ref['punkt']) or (str(doc['code']).replace(" ","") in ref['punkt']) or any(alternative in ref['punkt'] for alternative in alternatives):
                ref['page'] = page_data['page_num']
                ref['doc_code'] = doc['code']
            
                all_references.append(ref)
                with open(report_path, mode="a", encoding="utf-8") as report:
                    print(f"    Найдена ссылка на {ref['punkt']}", file = report)
            else:
                with open(report_path, mode="a", encoding="utf-8") as report:
                    print(f"    Найденная ссылка на {doc['code']} в пункте {ref['punkt']} некорректна", file = report)
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"Всего найдено ссылок: {len(all_references)}", file = report)
     
    output = {
        'doc_code': doc['code'],
        'doc_name': doc['name'],
        'extracted_pages': matched_page_numbers,
        'references': all_references
    }
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"\n Результаты сохранены в {output_folder}", file = report)
    
    return {
        'doc_code': doc['code'],
        'references_count': len(all_references),
        'json_file': output_json
    }

def _extract_references_with_llm(page_text, page_num, doc_code, doc_pattern, report_path=''):
   
    if 'СП' not in doc_code:
        prompt = f"""Ты - эксперт по проектной документации. Проанализируй текст страницы и найди ВСЕ ссылки на {doc_code}.

Текст страницы {page_num}:
====================
{page_text}
====================

Задача:
1. Найди все строки, где есть ссылки на {doc_code}
2. Для каждой ссылки определи:
   - полную строку ссылки
   - полный абзац, в котором находится эта ссылка

Примеры ссылок на Федеральный закон {doc_code}:
- "ст. 6"
- "ч.5 ст.134 № {doc_code}"
- "согласно требованиям ст. 90 Технического регламента {doc_code}"
- "ч. 4 ст. 89 ФЗ №123"
- "в соответствии с требованиями {doc_code}"

ВАЖНО: Игнорируй ссылки на другие документы!

Верни результат в формате JSON:
[
    {{
        "punkt": "полная строка ссылки",
        "full_paragraph": "полный текст абзаца со ссылкой"
    }}
]

Если ссылок нет - верни пустой массив [].
Верни ТОЛЬКО JSON, без пояснений.
"""
    else:
        excluded_documents = "СП 1.13130, СП 2.13130, СП 3.13130, СП 4.13130, СП 59.13330, 123-ФЗ и другие"
        excluded_documents = excluded_documents.replace(doc_code, "")
        excluded_documents = excluded_documents.replace(", ,",",")
        
        prompt = f"""Ты - эксперт по проектной документации. Проанализируй текст страницы и найди ВСЕ ссылки ТОЛЬКО на {doc_code}.

Текст страницы {page_num}:
====================
{page_text}
====================

Задача:
1. Найди все строки, где есть ссылки на {doc_code}
2. Игнорируй ссылки на другие документы ({excluded_documents})
3. Для каждой ссылки определи:
   - полную строку ссылки
   - полный абзац, в котором находится эта ссылка

Примеры ссылок на {doc_code}:
- "8.9 {doc_code}"
- "п.5.1.3 {doc_code}"
- "п. 3.1 {doc_code}"
- "табл. 1 {doc_code}"
- "пп. 4.4.15 {doc_code}"
- "п.п. 5.1.2, 5.1.3, 5.2.8 {doc_code}"

ВАЖНО: Если в строке есть упоминание другого документа - ПРОПУСТИ такую ссылку!

Верни результат в формате JSON:
[
    {{
        "punkt": "полная строка ссылки",
        "full_paragraph": "полный текст абзаца со ссылкой"
    }}
]

Если ссылок нет - верни пустой массив [].
Верни ТОЛЬКО JSON, без пояснений.
"""
    
    try:
        client = ollama.Client(host=OLLAMA_URL, timeout=60.0)
        response = client.chat(
            model=NORMS_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 8192}
        )
        
        result_text = response['message']['content'].strip()
        
        # Ищем JSON в ответе
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return []
            
    except Exception as e:
        with open(report_path, mode="a", encoding="utf-8") as report:
            print(f"     Ошибка LLM: {e}", file = report)
        return []

def _extract_text_from_MOPB(pdf_path, output_pdf='MOPB_распознанный', report_path=''):
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f" Всего страниц в исходном PDF: {total_pages}", file = report)
    pages_text = []

    for i, p in enumerate(doc):
        page_text = p.get_text()
        if len(page_text) >= 100:
            pages_text.append(page_text)
        else:
            pages_text.append("")
            with open(report_path, mode="a", encoding="utf-8") as report:
                print(f'На странице {i+1} не удалось прочитать текст. На странице расположено изображение', file = report)
    
    return pages_text


def _extract_pages_with_doc_mention(pdf_path, pages_text, doc_code, alternatives:list = [], report_path=''):
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"  ЭТАП 1: ПОИСК СТРАНИЦ С УПОМИНАНИЕМ {doc_code}", file = report)
        print(f"  ЭТАП 1: ПОИСК СТРАНИЦ С УПОМИНАНИЕМ {doc_code}")

    doc = fitz.open(pdf_path)
    # Удаляем пустые строки из текста для облегчения работы модели (особенно в районе проектной рамки)
    new_pages_text = []
    for txt in pages_text:
        lines = txt.splitlines()
        new_lines = ""
        for line in lines:
            match = re.search(r"^\s*$", line)
            if not match:
                new_lines += line + "\n"
        new_pages_text.append(new_lines)
    merged_pages_text = _merge_pages_by_center_split(new_pages_text)

    total_pages = len(pages_text)
    pages_with_doc = []
    
    for page_num in range(total_pages):
        merged_text = merged_pages_text[page_num]
        
        if len(alternatives) == 0:
            if (doc_code in merged_text)or(str(doc_code).replace(" ","") in merged_text):
                pages_with_doc.append(page_num + 1)
                with open(report_path, mode="a", encoding="utf-8") as report:
                    print(f"    Страница {page_num + 1}: найдено '{doc_code}'", file = report)
        else:
            for alternative in alternatives:
                if alternative in merged_text:
                    pages_with_doc.append(page_num + 1)
                    with open(report_path, mode="a", encoding="utf-8") as report:
                        print(f"    Страница {page_num + 1}: найдено '{alternative}'", file = report)
                    break
    
    with open(report_path, mode="a", encoding="utf-8") as report:
        print(f"\n Найдено страниц с упоминанием {doc_code}: {len(pages_with_doc)}", file = report)
        print(f"   Страницы: {pages_with_doc}", file = report)
    
    if pages_with_doc:
        with open(report_path, mode="a", encoding="utf-8") as report:
            print(f"\n Страницы с упоминанием {doc_code} найдены", file = report)
    else:
        with open(report_path, mode="a", encoding="utf-8") as report:
            print(f"\n Страницы с упоминанием {doc_code} не найдены", file = report)
    
    return pages_with_doc, merged_pages_text


def _merge_pages_by_center_split(pages_text_list):
    """
    Разделяет страницы пополам по абзацу и склеивает попарно разделенные части
    """
    pages_text_list = copy.deepcopy(pages_text_list)

    def _find_split_position_from_center(text: str) -> int | None:
        """
        Ищет ближайшую к центру позицию, где встречается:
            '\n' + заглавная буква, кроме первых символов 'СП'
            '\n' + нумерация пунктов кириллицей (например д.1), кроме п. (ссылка на пункт документа)
            '\n' + цифра, кроме обозначений пунктов нормативных документов и предыдущая строка не заканчивается на'СП'
        Возвращает индекс начала '\n', либо None.
        """

        if not text:
            return None

        #pattern = re.compile(r"\n(?=[A-ZА-ЯЁ0-9])")
        pattern = re.compile(r"\n(?=[A-ZА-РТ-ЯЁ])|\n(?=С[^П])|\n(?=[а-ор-я]\.[1-9]+)|(?<!СП\s)\n(?=[1-9](?![\.0-9]*\s+СП))")
        middle = len(text) // 2

        # Собираем все позиции начала совпадений
        matches = [m.start() for m in pattern.finditer(text)]
        if not matches:
            return None

        # Ищем ближайшую к середине.
        best_pos = min(matches, key=lambda pos: abs(pos - middle))
        return best_pos

    for i in range(len(pages_text_list) - 1):
        next_page_text = pages_text_list[i + 1]
        split_pos = _find_split_position_from_center(next_page_text)

        if split_pos is None:
            continue

        part_to_move = next_page_text[:split_pos]
        remaining_part = next_page_text[split_pos:]

        pages_text_list[i] += part_to_move
        pages_text_list[i + 1] = remaining_part

    return pages_text_list

def _check_stu(input_folder):
    if input_folder:
        if not os.path.exists(input_folder):
            print(f"Ошибка: Папка '{input_folder}' не существует")
            return False

    
    mopb_links_folder = os.path.join(input_folder, "MOPB_ссылки")
    if not os.path.exists(mopb_links_folder):
        print(f"Ошибка: Папка 'МОРВ_ссылки' не найдена в '{input_folder}'")
        return False
    
    if not os.path.isdir(mopb_links_folder):
        print(f"Ошибка: 'МОРВ_ссылки' не является папкой")
        return False

    json_file_name = "MOPB_Специальные_технические_условия_пункты_полные.json"
    json_file_path = os.path.join(mopb_links_folder, json_file_name)
    
    if not os.path.exists(json_file_path):
        print(f"Ошибка: Файл '{json_file_name}' не найден в папке 'МОРВ_ссылки'")
        return False
    
    if not os.path.isfile(json_file_path):
        print(f"Ошибка: '{json_file_name}' не является файлом")
        return False
    

    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        print(f"Ошибка: Не удалось прочитать JSON-файл: {e}")
        return False
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return False
    
    if "extracted_pages" not in data:
        print(f"Ошибка: Поле 'extracted_pages' отсутствует в JSON-файле")
        return False
    
    extracted_pages = data["extracted_pages"]
    
    if extracted_pages is None:
        print("Ошибка: Поле 'extracted_pages' равно None")
        return False
    
    if isinstance(extracted_pages, (list, str, dict)):
        if len(extracted_pages) == 0:
            print("Ошибка: Поле 'extracted_pages' пустое")
            return False
    elif isinstance(extracted_pages, (int, float)):
        if extracted_pages == 0:
            print("Ошибка: Поле 'extracted_pages' равно 0")
            return False
    elif isinstance(extracted_pages, bool):
        if not extracted_pages:
            print("Ошибка: Поле 'extracted_pages' равно False")
            return False
    
    return True
