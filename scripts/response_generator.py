"""
Модуль формирования сводного ответа пользователю на основе JSON-отчетов анализа страниц.
Загружает все отчеты из папки сессии, агрегирует данные и формирует подробный суммирующий ответ.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict


def load_session_reports(session_folder: str) -> List[Dict[str, Any]]:
    """
    Загружает все JSON-отчеты анализа страниц из папки сессии.
    
    Args:
        session_folder: Путь к папке сессии (например, uploads/15fcc465-...)
        
    Returns:
        Список загруженных отчетов
    """
    reports = []
    session_path = Path(session_folder)
    
    if not session_path.exists():
        print(f"⚠️ Папка сессии не найдена: {session_folder}")
        return reports
    
    # Ищем все файлы analysis_page_*.json
    report_files = sorted(session_path.glob("analysis_page_*.json"))
    
    for report_file in report_files:
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                reports.append(report)
                print(f"✅ Загружен отчет: {report_file.name}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки отчета {report_file.name}: {e}")
    
    print(f"📊 Всего загружено отчетов: {len(reports)}")
    return reports


def extract_findings_from_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Извлекает находки из одного отчета анализа страницы.
    
    Args:
        report: JSON-отчет анализа страницы
        
    Returns:
        Список находок с информацией о странице и файле
    """
    findings = []
    
    # Получаем базовую информацию
    page_num = report.get('page_num', 1)
    source_file = report.get('source_file', 'неизвестно')
    user_query = report.get('user_query', '')
    
    # Извлекаем found_objects
    found_objects = report.get('found_objects', [])
    
    if found_objects and isinstance(found_objects, list):
        for obj in found_objects:
            finding = {
                'object_name': obj.get('name', 'Неизвестный объект'),
                'dimensions': obj.get('dimensions', 'размеры не указаны'),
                'material': obj.get('material', 'материал не указан'),
                'page_number': page_num,
                'source_file': source_file,
                'user_query': user_query
            }
            findings.append(finding)
    
    return findings


def aggregate_findings(all_findings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Агрегирует находки по типам объектов, объединяя данные с разных страниц.
    
    Args:
        all_findings: Список всех находок из всех отчетов
        
    Returns:
        Словарь агрегированных данных по каждому типу объекта
    """
    aggregated = defaultdict(lambda: {
        'object_name': '',
        'dimensions_set': set(),
        'materials_set': set(),
        'pages': set(),
        'files': set()
    })
    
    for finding in all_findings:
        obj_name = finding['object_name']
        
        # Обновляем название объекта
        aggregated[obj_name]['object_name'] = obj_name
        
        # Собираем все уникальные значения
        if finding.get('dimensions') and finding['dimensions'] != 'размеры не указаны':
            aggregated[obj_name]['dimensions_set'].add(finding['dimensions'])
        
        if finding.get('material') and finding['material'] != 'материал не указан':
            aggregated[obj_name]['materials_set'].add(finding['material'])
        
        # Добавляем страницу и файл
        aggregated[obj_name]['pages'].add(finding['page_number'])
        aggregated[obj_name]['files'].add(finding['source_file'])
    
    return dict(aggregated)


def format_dimensions(dimensions_set: set) -> str:
    """Форматирует набор размеров в читаемую строку."""
    if not dimensions_set:
        return "размеры не указаны"
    return "; ".join(sorted(dimensions_set))


def format_materials(materials_set: set) -> str:
    """Форматирует набор материалов в читаемую строку."""
    if not materials_set:
        return "материал не указан"
    return "; ".join(sorted(materials_set))


def generate_summary_response(
    aggregated_data: Dict[str, Dict[str, Any]], 
    user_query: str,
    total_pages: int,
    total_files: set
) -> Dict[str, Any]:
    """
    Генерирует подробный сводный ответ на основе агрегированных данных.
    
    Args:
        aggregated_data: Агрегированные данные по объектам
        user_query: Исходный запрос пользователя
        total_pages: Общее количество обработанных страниц
        total_files: Множество файлов
        
    Returns:
        Словарь с ответом, находками и метаданными
    """
    if not aggregated_data:
        return {
            'answer': f"По запросу '{user_query}' ничего не найдено в предоставленных чертежах.",
            'findings': [],
            'page_references': [],
            'source_files': [],
            'summary': 'Объекты не найдены',
            'total_objects': 0,
            'total_pages': total_pages
        }
    
    # Формируем список находок для ответа
    findings_list = []
    answer_parts = []
    
    for obj_name, data in aggregated_data.items():
        # Формируем описание находки
        dimensions_str = format_dimensions(data['dimensions_set'])
        materials_str = format_materials(data['materials_set'])
        
        pages_list = sorted(data['pages'])
        files_list = sorted(data['files'])
        
        # Создаем запись находки
        finding = {
            'object_name': obj_name,
            'dimensions': dimensions_str,
            'material': materials_str,
            'pages': pages_list,
            'files': files_list
        }
        
        findings_list.append(finding)
        
        # Формируем часть ответа для этого объекта
        answer_part = f"• **{obj_name}**:\n"
        answer_part += f"  - Размеры: {dimensions_str}\n"
        answer_part += f"  - Материал: {materials_str}\n"
        
        # Форматируем страницы и файлы
        pages_str = ", ".join(map(str, pages_list))
        files_short = [f.split('/')[-1] if '/' in f else f for f in files_list]
        files_short_str = ", ".join(files_short[:3])
        if len(files_short) > 3:
            files_short_str += f" и еще {len(files_short) - 3} файл(а)"
        
        answer_part += f"  - Найден на страницах: {pages_str}\n"
        answer_part += f"  - Документы: {files_short_str}\n"
        
        answer_parts.append(answer_part)
    
    # Формируем полный ответ
    full_answer = f"По запросу \"{user_query}\" найдено {len(findings_list)} типа объектов:\n\n"
    full_answer += "\n".join(answer_parts)
    
    # Формируем резюме
    summary = (
        f"Всего найдено {len(findings_list)} типа объектов. "
        f"Обработано {total_pages} страниц из {len(total_files)} файла(ов). "
        f"Объекты распределены по страницам: {', '.join(map(str, sorted(set(p for d in aggregated_data.values() for p in d['pages']))))}"
    )
    
    return {
        'answer': full_answer,
        'findings': findings_list,
        'page_references': sorted(set(p for d in aggregated_data.values() for p in d['pages'])),
        'source_files': sorted(set(f for d in aggregated_data.values() for f in d['files'])),
        'summary': summary,
        'total_objects': len(findings_list),
        'total_pages': total_pages,
        'total_files_count': len(total_files)
    }


def generate_response(session_folder: str, user_query: Optional[str] = None) -> Dict[str, Any]:
    """
    Основная функция формирования ответа.
    Загружает все отчеты из сессии, агрегирует данные и формирует сводный ответ.
    
    Args:
        session_folder: Путь к папке сессии с JSON-отчетами
        user_query: Вопрос пользователя (опционально, берется из отчетов если не указан)
        
    Returns:
        Словарь с полным ответом, находками и метаданными
    """
    print(f"\n🔍 Начинаем формирование сводного ответа для сессии: {session_folder}")
    print("=" * 80)
    
    # Загружаем все отчеты из сессии
    reports = load_session_reports(session_folder)
    
    if not reports:
        return {
            'answer': "Не найдено отчетов анализа для формирования ответа.",
            'findings': [],
            'page_references': [],
            'source_files': [],
            'summary': 'Отчеты не найдены',
            'error': 'No reports found'
        }
    
    # Извлекаем все находки из всех отчетов
    all_findings = []
    all_files = set()
    all_pages = set()
    queries = set()
    
    for report in reports:
        findings = extract_findings_from_report(report)
        all_findings.extend(findings)
        
        if report.get('source_file'):
            all_files.add(report['source_file'])
        if report.get('page_num'):
            all_pages.add(report['page_num'])
        if report.get('user_query'):
            queries.add(report['user_query'])
    
    print(f"📈 Всего извлечено находок: {len(all_findings)}")
    print(f"📁 Всего файлов: {len(all_files)}")
    print(f"📄 Всего страниц: {len(all_pages)}")
    
    # Определяем запрос пользователя
    effective_query = user_query
    if not effective_query and queries:
        effective_query = list(queries)[0]  # Берем первый найденный запрос
    if not effective_query:
        effective_query = "анализ объектов"
    
    print(f"❓ Запрос пользователя: {effective_query}")
    
    # Агрегируем данные по объектам
    aggregated_data = aggregate_findings(all_findings)
    print(f"🎯 Уникальных типов объектов: {len(aggregated_data)}")
    
    # Генерируем сводный ответ
    response = generate_summary_response(
        aggregated_data=aggregated_data,
        user_query=effective_query,
        total_pages=len(all_pages),
        total_files=all_files
    )
    
    print("=" * 80)
    print("✅ Сводный ответ сформирован")
    
    return response


# Для совместимости со старым интерфейсом
def generate_response_legacy(analysis_results: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
    """
    Legacy-функция для обратной совместимости.
    Преобразует старый формат в новый и вызывает основную функцию.
    """
    # Извлекаем session_folder из analysis_results если возможно
    # Или просто используем агрегацию напрямую
    
    all_findings = []
    all_files = set()
    all_pages = set()
    
    for result in analysis_results:
        page_num = result.get('page_num', 1)
        source_file = result.get('source_file', 'unknown')
        found_objects = result.get('found_objects', [])
        
        all_pages.add(page_num)
        all_files.add(source_file)
        
        if found_objects and isinstance(found_objects, list):
            for obj in found_objects:
                finding = {
                    'object_name': obj.get('name', 'Неизвестный объект'),
                    'dimensions': obj.get('characteristics', {}).get('dimensions', 'размеры не указаны'),
                    'material': obj.get('characteristics', {}).get('material', 'материал не указан'),
                    'location': obj.get('characteristics', {}).get('location', ''),
                    'quantity': obj.get('characteristics', {}).get('quantity', ''),
                    'additional_params': obj.get('characteristics', {}).get('additional_params', ''),
                    'page_number': page_num,
                    'source_file': source_file,
                    'confidence': obj.get('confidence', 'medium'),
                    'user_query': question
                }
                all_findings.append(finding)
    
    aggregated_data = aggregate_findings(all_findings)
    
    return generate_summary_response(
        aggregated_data=aggregated_data,
        user_query=question,
        total_pages=len(all_pages),
        total_files=all_files
    )
