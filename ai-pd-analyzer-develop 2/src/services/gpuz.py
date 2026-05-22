import time
import re

import fitz
import ollama

from .config import load_config

OLLAMA_URL = load_config().ollama_url

# ======== 1 ЭТАП ==========
def findDateInGPZU(GPZU_filename: str) -> dict:
    """
    Ищем ВСЕ даты в документе ГПЗУ с указанием страниц.
    Возвращает словарь с найденными датами и метаинформацией.
    """
    print("Начинаем поиск дат в ГПЗУ...")
    
    # Теперь возвращает список кортежей (дата, страница)
    dates_with_pages = _find_all_dates_with_text_search(GPZU_filename)
    
    if not dates_with_pages:
        print("\nТекстовый поиск не дал результатов, пробуем визуальный...")
        dates_with_pages = _find_all_dates_visual(GPZU_filename)
    
    # Проверяем, есть ли даты старше 1.5 лет
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=547)  # ~1.5 года
    
    has_old_dates = False
    parsed_dates = []
    
    for date_str, page_num in dates_with_pages:
        try:
            date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            is_old = date_obj < cutoff_date
            parsed_dates.append({
                "date": date_str,
                "page": page_num, 
                "is_old": is_old,
                "parsed": date_obj.isoformat()
            })
            if is_old:
                has_old_dates = True
        except ValueError:
            parsed_dates.append({
                "date": date_str,
                "page": page_num,  
                "is_old": False,
                "parsed": None
            })
    
    # Сортируем: сначала "не старые", потом по дате (новые сначала)
    def sort_key(d):
        try:
            date_obj = datetime.strptime(d["date"], "%d.%m.%Y")
            return (0 if not d["is_old"] else 1, -date_obj.timestamp())
        except ValueError:
            return (2, 0)
    
    parsed_dates.sort(key=sort_key)
    
    result = {
        "dates": [d["date"] for d in parsed_dates],
        "dates_with_info": parsed_dates,
        "has_old_dates": has_old_dates,
        "total_found": len(dates_with_pages)
    }
    
    print(f"\nИтог: найдено дат: {len(dates_with_pages)}")
    for d in parsed_dates:
        old_marker = " (СТАРАЯ)" if d["is_old"] else ""
        print(f"  - {d['date']} (стр. {d['page']}){old_marker}")
    
    return result


def _find_all_dates_with_text_search(pdf_path):
    """
    Текстовый поиск ВСЕХ дат в документе.
    Возвращает set кортежей (дата, страница).
    """
    doc = fitz.open(pdf_path)
    all_dates = set() 
    
    print("  Выполняем текстовый поиск всех дат...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        title_pattern = r'ГРАДОСТРОИТЕЛЬНЫЙ\s+ПЛАН\s+ЗЕМЕЛЬНОГО\s+УЧАСТКА'
        title_match = re.search(title_pattern, text, re.IGNORECASE)
        
        if not title_match:
            continue
        
        print(f"Найден заголовок ГПЗУ на странице {page_num + 1}")
        
        # Собираем текст со страницы заголовка и следующих
        full_text = text[title_match.start():]
        for i in range(page_num + 1, min(page_num + 5, len(doc))):
            full_text += " " + doc[i].get_text()
        
        # Ищем даты по паттернам с метками
        date_patterns_with_labels = [
            r'Дата\s+выдачи\s*[:]?\s*(\d{2}\.\d{2}\.\d{4})',
            r'дата\s+выдачи\s*[:]?\s*(\d{2}\.\d{2}\.\d{4})',
            r'ДАТА\s+ВЫДАЧИ\s*[:]?\s*(\d{2}\.\d{2}\.\d{4})',
            r'Выдана\s*[:]?\s*(\d{2}\.\d{2}\.\d{4})',
            r'выданного\s*(\d{2}\.\d{2}\.\d{4})'
        ]
        
        for pattern in date_patterns_with_labels:
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                print(match)
                date = match.group(1)
                # Определяем, на какой странице эта дата
                date_page = _find_date_page(doc, page_num, match.start(), full_text)
                print(f"  Найдена дата: {date} (стр. {date_page})")
                all_dates.add((date, date_page))
    
    doc.close()
    return all_dates


def _find_date_page(doc, start_page, position_in_full_text, full_text):
    """
    Определяет номер страницы, на которой находится дата.
    """
    # Считаем количество символов до позиции даты
    text_before_date = full_text[:position_in_full_text]
    
    current_page = start_page
    accumulated_text = ""
    
    # Текст страницы, с которой начали
    page_text = doc[start_page].get_text()
    accumulated_text = page_text
    
    # Если дата на первой странице
    if position_in_full_text < len(page_text):
        return start_page + 1
    
    # Ищем на следующих страницах
    for i in range(start_page + 1, min(start_page + 5, len(doc))):
        prev_length = len(accumulated_text)
        page_text = doc[i].get_text()
        accumulated_text += " " + page_text
        
        if position_in_full_text < len(accumulated_text):
            return i + 1
    
    return start_page + 1


def _find_all_dates_visual(pdf_path):
    """
    Визуальный поиск дат с помощью VLM.
    Возвращает set кортежей (дата, страница).
    """
    doc = fitz.open(pdf_path)
    all_dates = set()  # (дата, страница)
    
    # Сначала находим страницу с заголовком
    title_page = None
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        
        prompt = """На этой странице есть текст «ГРАДОСТРОИТЕЛЬНЫЙ ПЛАН ЗЕМЕЛЬНОГО УЧАСТКА»?
Ответь только "ДА" или "НЕТ"."""
        
        try:
            client = ollama.Client(host=OLLAMA_URL, timeout=120.0)
            response = client.chat(
                model='qwen2.5vl:7b',
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [img_data],
                }],
                stream=False,
                options={'temperature': 0.1},
            )
            
            if response['message']['content'].strip().upper() == "ДА":
                title_page = page_num
                print(f"Заголовок найден на странице {page_num + 1}")
                break
        except Exception as e:
            print(f"Ошибка: {e}")
            continue
    
    if title_page is None:
        doc.close()
        return all_dates
    
    # Ищем даты на странице заголовка и следующих
    for page_num in range(title_page, min(title_page + 5, len(doc))):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        img_data = pix.tobytes("png")
        
        prompt = """Найди ВСЕ даты на этой странице, которые могут быть датами выдачи, утверждения или подготовки ГРАДОСТРОИТЕЛЬНОГО ПЛАНА ЗЕМЕЛЬНОГО УЧАСТКА.

Форматы дат: ДД.ММ.ГГГГ

Перечисли ВСЕ найденные даты, каждую с новой строки.
Если дат нет, напиши "НЕТ"."""
        
        try:
            client = ollama.Client(host=OLLAMA_URL, timeout=120.0)
            response = client.chat(
                model='qwen2.5vl:7b',
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [img_data],
                }],
                stream=False,
                options={'temperature': 0.1},
            )
            
            result = response['message']['content'].strip()
            print(f"Ответ VLM (стр. {page_num + 1}): {result}")
            
            if result.upper() != "НЕТ":
                dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', result)
                for date in dates:
                    try:
                        d, m, y = map(int, date.split('.'))
                        if 1 <= d <= 31 and 1 <= m <= 12 and 2000 <= y <= 2030:
                            all_dates.add((date, page_num + 1))  # ← Добавляем страницу
                            print(f"Найдена дата (визуально): {date} (стр. {page_num + 1})")
                    except ValueError:
                        pass
        except Exception as e:
            print(f"Ошибка: {e}")
            continue
    
    doc.close()
    return all_dates

def save_selected_date(date_str: str, output_folder: str=''):
    """Сохраняет выбранную/введённую дату в issuance_date.txt"""
    if not output_folder:
        with open('issuance_date.txt', 'w', encoding='utf-8') as f:
            f.write(date_str)
        print(f"Дата {date_str} сохранена в issuance_date.txt в корне")
    else:
        with open(f'{output_folder}/issuance_date.txt', 'w', encoding='utf-8') as f:
            f.write(date_str)
        print(f"Дата {date_str} сохранена в issuance_date.txt в корне")