"""
Модуль детекции страниц с чертежами.
Использует логику определения чертежей по размеру страницы (> A3/A4).
Все страницы сохраняются как отдельные PDF файлы с коррекцией ориентации.
"""

import os
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any

# Пороговый размер для определения чертежа (большая сторона в см)
# A4 = 29.7см, A3 = 42см, A2 = 59.4см
# Устанавливаем порог 45см - всё что больше A3 считается чертежом
DRAWING_MIN_SIZE_CM = 45.0


def correct_page_orientation(page: fitz.Page) -> int:
    """
    Определяет и корректирует ориентацию страницы.
    Все чертежи должны быть в альбомной ориентации (ширина > высоты).
    Возвращает итоговый угол поворота (0, 90, 180, 270).
    """
    # Получаем текущую ориентацию из PDF
    rotation = page.rotation
    
    # Получаем размеры страницы с учетом текущего rotation
    rect = page.rect
    width = rect.width
    height = rect.height
    
    # Учитываем текущий rotation для определения фактической ориентации
    if rotation in [90, 270]:
        # При таком rotation ширина и высота меняются местами
        actual_width = height
        actual_height = width
    else:
        actual_width = width
        actual_height = height
    
    # Определяем, нужно ли повернуть для альбомной ориентации
    needs_landscape_rotation = 0
    if actual_width < actual_height:
        # Страница в портретной ориентации - нужно повернуть на 90°
        needs_landscape_rotation = 90
        print(f"      📐 Страница в портретной ориентации ({actual_width:.0f}x{actual_height:.0f}), поворачиваем на 90° для альбомной")
    
    # Итоговый угол поворота = исходный rotation + поворот для альбомной ориентации
    total_rotation = (rotation + needs_landscape_rotation) % 360
    
    if rotation != 0 and needs_landscape_rotation == 0:
        print(f"      🔄 Страница имеет rotation {rotation}°, исправляем")
    elif needs_landscape_rotation != 0:
        print(f"      🔄 Поворачиваем на {needs_landscape_rotation}° для альбомной ориентации")
    
    return total_rotation


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


def extract_all_pages_to_images(pdf_path: str, output_folder: str) -> List[Dict[str, Any]]:
    """
    Извлекает все страницы из PDF как изображения PNG.
    Все страницы сохраняются, ориентация корректируется для альбомного формата.
    
    Args:
        pdf_path: Путь к PDF файлу
        output_folder: Папка для сохранения изображений
        
    Returns:
        Список словарей с путями к изображениям и метаданными
    """
    images = []
    
    try:
        doc = fitz.open(pdf_path)
        filename = os.path.basename(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Определяем необходимую коррекцию ориентации
            rotation = correct_page_orientation(page)
            
            # Рендерим страницу в изображение с учетом поворота
            # Создаем матрицу с поворотом
            if rotation == 0:
                mat = fitz.Matrix(2.0, 2.0)
            else:
                # Поворачиваем страницу перед рендерингом
                mat = fitz.Matrix(2.0, 2.0).prerotate(rotation)
            
            pix = page.get_pixmap(matrix=mat)
            
            image_filename = f"{filename}_page_{page_num + 1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            
            # Получаем размеры в см
            w_cm = page.rect.width * 2.54 / 72
            h_cm = page.rect.height * 2.54 / 72
            
            images.append({
                'path': image_path,
                'page_num': page_num + 1,
                'source_file': filename,
                'size': f"{w_cm:.1f}x{h_cm:.1f}cm",
                'width_cm': w_cm,
                'height_cm': h_cm
            })
        
        doc.close()
        
        print(f"✅ Извлечено {len(images)} страниц из {filename}")
        return images
        
    except Exception as e:
        print(f"❌ Ошибка при извлечении страниц из {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
        return []
