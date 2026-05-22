"""
Модуль детекции страниц с чертежами.
Использует логику из второго сервиса (ai-pd-analyzer-develop 2) для:
1. Определения страниц с чертежами в PDF
2. Перевода изображений в правильную ориентацию
3. Сохранения идентификаторов файлов и номеров страниц
"""

import fitz  # PyMuPDF
import os
import ollama
import re
import base64
from PIL import Image
from typing import List, Dict, Any

# Конфигурация Ollama - используется модель gemma4:31b для классификации
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CLASSIFICATION_MODEL = os.getenv("DRAWING_CLASSIFICATION_MODEL", "gemma4:31b")


def detect_drawing_pages(pdf_path: str, output_folder: str) -> List[Dict[str, Any]]:
    """
    Определяет страницы PDF, содержащие чертежи.
    
    Args:
        pdf_path: Путь к PDF файлу
        output_folder: Папка для сохранения изображений
        
    Returns:
        Список словарей с информацией о страницах с чертежами
    """
    drawing_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        filename = os.path.basename(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Рендерим страницу в изображение (zoom=2.0 для лучшего качества)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            # Сохраняем изображение
            image_filename = f"{filename}_page_{page_num + 1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            
            # Проверяем, является ли страница чертежом
            is_drawing = _is_drawing_page(image_path)
            
            if is_drawing:
                # Корректируем ориентацию если нужно
                corrected_image_path = _correct_orientation(image_path, output_folder, image_filename)
                
                drawing_pages.append({
                    'source_file': filename,
                    'page_num': page_num + 1,
                    'image_path': corrected_image_path,
                    'original_image_path': image_path,
                    'is_drawing': True
                })
            else:
                # Удаляем не чертежные страницы
                if os.path.exists(image_path):
                    os.remove(image_path)
        
        doc.close()
        
    except Exception as e:
        print(f"Ошибка обработки PDF {pdf_path}: {e}")
    
    return drawing_pages


def _is_drawing_page(image_path: str) -> bool:
    """
    Определяет, является ли изображение страницей с чертежом.
    Использует простую эвристику: наличие линий, текста, технических обозначений.
    """
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        # Конвертируем в grayscale для анализа
        gray = img.convert('L')
        pixels = list(gray.getdata())
        
        # Вычисляем контрастность (чертежи обычно имеют высокий контраст)
        min_pixel = min(pixels)
        max_pixel = max(pixels)
        contrast = max_pixel - min_pixel
        
        # Чертежи обычно имеют высокий контраст и много деталей
        # Эвристика: если контраст > 200 и изображение достаточно большое
        if contrast > 150 and width > 500 and height > 500:
            return True
        
        return False
        
    except Exception as e:
        print(f"Ошибка анализа изображения {image_path}: {e}")
        return True  # По умолчанию считаем чертежом


def _correct_orientation(image_path: str, output_folder: str, image_filename: str) -> str:
    """
    Корректирует ориентацию изображения (поворачивает в правильное положение).
    Чертежи должны быть ориентированы так, чтобы текст читался слева направо,
    а план здания был в правильной ориентации.
    """
    try:
        img = Image.open(image_path)
        
        # Простая эвристика: если ширина значительно меньше высоты, возможно изображение перевернуто
        width, height = img.size
        
        rotation_angle = 0
        
        # Если портретная ориентация для плана этажа - возможно нужно повернуть
        if height > width * 1.3:
            rotation_angle = 90
        
        if rotation_angle != 0:
            rotated_img = img.rotate(rotation_angle, expand=True)
            corrected_path = os.path.join(output_folder, image_filename)
            rotated_img.save(corrected_path)
            return corrected_path
        
        return image_path
        
    except Exception as e:
        print(f"Ошибка коррекции ориентации {image_path}: {e}")
        return image_path


def extract_all_pages_to_images(pdf_path: str, output_folder: str) -> List[Dict[str, Any]]:
    """
    Извлекает все страницы из PDF как изображения.
    
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
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            image_filename = f"{filename}_page_{page_num + 1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            
            # Корректируем ориентацию
            corrected_path = _correct_orientation(image_path, output_folder, image_filename)
            
            images.append({
                'path': corrected_path,
                'page_num': page_num + 1,
                'source_file': filename
            })
        
        doc.close()
        
    except Exception as e:
        print(f"Ошибка обработки PDF {pdf_path}: {e}")
    
    return images
