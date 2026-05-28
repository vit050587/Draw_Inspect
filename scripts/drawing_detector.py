"""
Модуль детекции страниц с чертежами.
Использует логику определения чертежей по размеру страницы (> 30см).
Сохраняются ТОЛЬКО страницы с чертежами (большая сторона > 30см).
Все страницы сохраняются как отдельные PDF файлы с коррекцией ориентации.
"""

import os
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any

# Пороговый размер для определения чертежа (большая сторона в см)
# A4 = 29.7см, A3 = 42см, A2 = 59.4см
# Устанавливаем порог 30см - всё что больше A4 считается чертежом
DRAWING_MIN_SIZE_CM = 30.0


def correct_page_orientation(page: fitz.Page) -> int:
    """
    Определяет и корректирует ориентацию страницы.
    Все чертежи должны быть в альбомной ориентации (ширина > высоты).
    
    Логика:
    1. Получаем физические размеры страницы в см.
    2. Учитываем page.rotation для определения фактической видимой ориентации.
    3. Если видимая ширина < видимой высоты, значит страница портретная -> нужно повернуть на 90°.
    4. Возвращаем угол поворота для insert_pdf(rotate=...), чтобы получить итоговую альбомную ориентацию.
    """
    # Получаем текущий rotation страницы из PDF метаданных
    current_rotation = page.rotation
    
    # Получаем "сырые" размеры страницы в пунктах (без учета rotation)
    # page.rect всегда возвращает размеры в базовой системе координ страницы
    raw_width_pt = page.rect.width
    raw_height_pt = page.rect.height
    
    # Вычисляем фактические видимые размеры с учетом текущего rotation
    # Если страница повернута на 90 или 270 градусов, то визуально ширина и высота меняются местами
    if current_rotation in [90, 270]:
        visible_width_pt = raw_height_pt
        visible_height_pt = raw_width_pt
    else:
        visible_width_pt = raw_width_pt
        visible_height_pt = raw_height_pt
    
    # Конвертируем в см для наглядности (1 pt = 1/72 inch, 1 inch = 2.54 cm)
    visible_width_cm = visible_width_pt * 2.54 / 72
    visible_height_cm = visible_height_pt * 2.54 / 72
    
    print(f"      📏 Размеры: {visible_width_cm:.1f}x{visible_height_cm:.1f}см (rotation={current_rotation}°)")
    
    # Определяем необходимость поворота
    # Цель: ширина должна быть больше высоты (альбомная ориентация)
    rotation_adjustment = 0
    
    if visible_width_cm < visible_height_cm:
        # Страница фактически портретная, нужно повернуть на 90° по часовой стрелке
        rotation_adjustment = 90
        print(f"      📐 Страница портретная, требуется поворот на 90°")
    else:
        # Страница уже альбомная
        print(f"      ✅ Страница уже в альбомной ориентации")
        
        # Если у страницы есть встроенный rotation != 0, но она визуально альбомная,
        # мы можем захотеть сбросить rotation в 0 в выходном файле.
        # insert_pdf(rotate=X) добавляет поворот X к существующему rotation.
        # Чтобы получить итоговый rotation=0, нужно передать (360 - current_rotation) % 360
        if current_rotation != 0:
            rotation_adjustment = (360 - current_rotation) % 360
            print(f"      🔄 Компенсация встроенного rotation {current_rotation}° -> {rotation_adjustment}°")
        else:
            rotation_adjustment = 0
            
    return rotation_adjustment


def detect_and_save_drawings(pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
    """
    Сканирует PDF, находит страницы с размером большей стороны > DRAWING_MIN_SIZE_CM.
    Сохраняет каждую такую страницу в отдельный PDF файл в папке output_dir/drawing_pages/.
    Страницы с портретной ориентацией автоматически поворачиваются в альбомную.
    
    Возвращает список словарей:
    [{'page_num': 5, 'file_path': '/path/to/dw_page_005.pdf', 'size': '42.0x29.7cm'}, ...]
    """
    drawings_dir = Path(output_dir) / "drawing_pages"
    drawings_dir.mkdir(parents=True, exist_ok=True)
    
    drawing_pages_info = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        print(f"🔍 Поиск чертежей в файле ({total_pages} стр.)... Критерий: > {DRAWING_MIN_SIZE_CM} см")
        
        for i in range(total_pages):
            page = doc[i]
            # Получаем размеры в пунктах и конвертируем в см
            w_cm = page.rect.width * 2.54 / 72
            h_cm = page.rect.height * 2.54 / 72
            max_side = max(w_cm, h_cm)
            
            if max_side > DRAWING_MIN_SIZE_CM:
                info = {
                    'page_num': i + 1,
                    'size': f"{w_cm:.1f}x{h_cm:.1f}cm",
                    'width_cm': w_cm,
                    'height_cm': h_cm
                }
                
                # Сохраняем страницу как отдельный PDF с коррекцией ориентации
                out_filename = f"dw_page_{i+1:03d}.pdf"
                out_pdf = drawings_dir / out_filename
                
                new_doc = fitz.open()
                
                # Определяем необходимую коррекцию ориентации
                rotation = correct_page_orientation(page)
                
                # Вставляем страницу с применением поворота
                new_doc.insert_pdf(doc, from_page=i, to_page=i, rotate=rotation)
                new_doc.save(str(out_pdf))
                new_doc.close()
                
                info['file_path'] = str(out_pdf)
                drawing_pages_info.append(info)
                print(f"   ✅ Стр. {i+1}: Чертеж ({info['size']}) -> {out_filename}")
        
        doc.close()
        
        if not drawing_pages_info:
            print("ℹ️ Чертежи не найдены (все страницы <= A4/A3)")
            
        return drawing_pages_info
        
    except Exception as e:
        print(f"❌ Ошибка при детекции чертежей: {e}")
        import traceback
        traceback.print_exc()
        return []


def extract_drawing_pages_to_pdf(pdf_path: str, output_folder: str) -> List[Dict[str, Any]]:
    """
    Извлекает ТОЛЬКО страницы с чертежами из PDF как отдельные PDF файлы.
    Чертежами считаются страницы с размером большей стороны > DRAWING_MIN_SIZE_CM (30см).
    Ориентация корректируется для альбомного формата.
    
    Args:
        pdf_path: Путь к PDF файлу
        output_folder: Папка для сохранения страниц
        
    Returns:
        Список словарей с путями к PDF файлам и метаданными (только чертежи)
    """
    pages = []
    
    try:
        doc = fitz.open(pdf_path)
        filename = os.path.basename(pdf_path)
        
        # Создаем папку для страниц
        pages_dir = Path(output_folder) / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔍 Поиск чертежей в файле {filename}... Критерий: > {DRAWING_MIN_SIZE_CM} см")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Получаем размеры в см
            w_cm = page.rect.width * 2.54 / 72
            h_cm = page.rect.height * 2.54 / 72
            max_side = max(w_cm, h_cm)
            
            # Проверяем, является ли страница чертежом
            if max_side <= DRAWING_MIN_SIZE_CM:
                print(f"   ⏭️ Стр. {page_num + 1}: Пропущено ({w_cm:.1f}x{h_cm:.1f}см) - не чертеж")
                continue
            
            # Определяем необходимую коррекцию ориентации
            rotation = correct_page_orientation(page)
            
            # Создаем новый PDF с одной страницей
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num, rotate=rotation)
            
            page_filename = f"{filename}_page_{page_num + 1}.pdf"
            page_path = pages_dir / page_filename
            new_doc.save(str(page_path))
            new_doc.close()
            
            pages.append({
                'path': str(page_path.absolute()),
                'page_num': page_num + 1,
                'source_file': filename,
                'size': f"{w_cm:.1f}x{h_cm:.1f}cm",
                'width_cm': w_cm,
                'height_cm': h_cm
            })
            print(f"   ✅ Стр. {page_num + 1}: Чертеж ({w_cm:.1f}x{h_cm:.1f}см) -> {page_filename}")
        
        doc.close()
        
        if not pages:
            print("ℹ️ Чертежи не найдены (все страницы <= A4)")
        else:
            print(f"✅ Найдено и сохранено {len(pages)} чертежей из {filename}")
        
        return pages
        
    except Exception as e:
        print(f"❌ Ошибка при извлечении чертежей из {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
        return []
