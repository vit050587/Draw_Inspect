import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import chardet

def process_complex_json_to_xlsx(
    input_folder: str,
    output_folder: str
) -> List[str]:
    """
    Специализированная функция для обработки JSON с результатами анализа документов.
    Разворачивает вложенные структуры в плоскую таблицу Excel.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    input_path = Path(input_folder)
    json_files = list(input_path.glob('*.json'))
    
    if not json_files:
        print(f"❌ JSON файлы не найдены в: {input_folder}")
        return []
    
    output_files = []
    
    for json_file in json_files:
        try:
            print(f"\n📄 Обработка: {json_file.name}")
            
            # Читаем JSON с автоопределением кодировки
            with open(json_file, 'rb') as f:
                raw = f.read()
                encoding = chardet.detect(raw)['encoding'] or 'utf-8'
            
            data = json.loads(raw.decode(encoding, errors='ignore'))
            
            # Создаем плоскую структуру
            rows = []
            
            # Извлекаем общую информацию
            base_info = {
                'doc_code': data.get('doc_code', ''),
                'norm_file': data.get('norm_file', ''),
                'total_references': data.get('total_references', 0),
                'skipped_no_numbers': data.get('skipped_no_numbers', 0),
                'processed': data.get('processed', 0),
                'found_in_norm': data.get('found_in_norm', 0),
                'not_found_in_norm': data.get('not_found_in_norm', 0)
            }
            
            # Обрабатываем результаты
            results = data.get('results', [])
            
            if not results:
                # Если нет результатов, сохраняем только общую информацию
                rows.append(base_info)
            else:
                # Для каждого результата создаем строку
                for result in results:
                    row = base_info.copy()
                    
                    # Добавляем поля из result
                    row['punkt'] = result.get('punkt', '')
                    row['page'] = result.get('page', '')
                    row['mopb_text'] = result.get('mopb_text', '').replace('\n', ' ').replace('\r', ' ')
                    row['status'] = result.get('status', '')
                    row['explanation'] = result.get('explanation', '').replace('\n', ' ').replace('\r', ' ')
                    
                    if result.get('punkt_number', ''):
                        row['punkt_number'] = 'пункт ' + result.get('punkt_number', '')
                        row['norm_text'] = result.get('norm_text', '')
                        row['comment'] = result.get('comment', '')
                        rows.append(row)
                    else:
                        # Обрабатываем ссылки на ФЗ
                        if result.get('article', ''):
                            detailed_row = row.copy()
                            detailed_row['fz_article'] = result.get('article', '')
                            detailed_row['fz_part'] = result.get('part', '')
                            detailed_row['fz_norm_text'] = result.get('norm_text', '').replace('\n', ' ').replace('\r', ' ') if result.get('norm_text', '') else ''
                            detailed_row['comment'] = result.get('comment', '')
                            rows.append(detailed_row)
                        else:
                            # Если нет ссылок, добавляем строку без них
                            row['fz_article'] = ''
                            row['fz_part'] = ''
                            row['fz_norm_text'] = ''
                            row['fz_references_count'] = 0
                            row['has_multiple_refs'] = False
                            row['comment'] = result.get('comment', '')
                            rows.append(row)
            
            # Создаем DataFrame
            df = pd.DataFrame(rows)
            
            # Очищаем данные
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].fillna('')
                    # Удаляем лишние пробелы
                    df[col] = df[col].apply(lambda x: ' '.join(str(x).split()) if x else '')

            titles_delete = ['total_references', 'skipped_no_numbers', 'processed',
                           'found_in_norm', 'not_found_in_norm', 'fz_references_count',
                           'has_multiple_refs']
            for title in titles_delete:
                try:
                    df = df.drop(title, axis=1)
                except:
                    pass
            
            df = df.rename(columns={
                'doc_code': 'Код документа', 
                'norm_file': 'Файл нормативного документа',
                'punkt': 'Цитата с ссылкой на НТД',
                'page': 'Страница проектной документации',
                'mopb_text': 'Текст проектной документации',
                'status': 'Соответствие норме',
                'explanation': 'Объяснение модели',
                'fz_article': 'Статья',
                'fz_part': 'Часть',
                'fz_norm_text': 'Текст нормы ФЗ',
                'punkt_number': 'Номера пунктов нормы',
                'norm_text': 'Текст нормы',
                'comment': 'Примечание'
            })

            mapping = {
                'ok': 'Соответствует',
                'not_ok': 'Не соответствует',
                'not_found': 'Не найден в норме',
                'error': 'Ошибка обработки'
                }

            try:
                df['Соответствие норме'] = df['Соответствие норме'].map(mapping)
            except:
                print('Не удалось найти поле статус')
            
            # Сохраняем в Excel
            excel_filename = f"{json_file.stem}_detailed.xlsx"
            excel_path = os.path.join(output_folder, excel_filename)
            
            # Сохранение в Excel с автонастройкой ширины колонок
            with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Детали', index=False)
                
                # Автонастройка ширины колонок
                worksheet = writer.sheets['Детали']
                for i, col in enumerate(df.columns):
                    # Вычисляем максимальную ширину
                    max_len = max(
                        df[col].astype(str).str.len().max(),
                        len(str(col))
                    ) + 2
                    # Ограничиваем максимальную ширину
                    max_len = min(max_len, 50)
                    worksheet.set_column(i, i, max_len)
            
            output_files.append(excel_path)
            
            print(f"  ✅ Сохранено: {excel_filename}")
            print(f"     Строк: {len(df)}, Колонок: {len(df.columns)}")
            print(f"     Колонки: {', '.join(df.columns.tolist())}")
            
            # Дополнительно создаем сводную таблицу
            if not df.empty:
                create_summary_excel(df, json_file.stem, output_folder)
            
        except Exception as e:
            print(f"  ❌ Ошибка при обработке {json_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    return output_files


def create_summary_excel(df: pd.DataFrame, base_name: str, output_folder: str):
    """
    Создает сводную таблицу Excel с агрегированной информацией.
    """
    try:
        # Группируем по пунктам
        if 'punkt' in df.columns and not df['punkt'].isna().all():
            summary = df.groupby(['doc_code', 'punkt']).agg({
                'page': 'first',
                'mopb_text': 'first',
                'status': 'first',
                'explanation': 'first',
                'fz_article': lambda x: ', '.join(x.unique()),
                'fz_references_count': 'first'
            }).reset_index()
            
            summary_filename = f"{base_name}_summary.xlsx"
            summary_path = os.path.join(output_folder, summary_filename)
            
            # Сохраняем в Excel
            with pd.ExcelWriter(summary_path, engine='xlsxwriter') as writer:
                summary.to_excel(writer, sheet_name='Сводка', index=False)
                
                # Автонастройка ширины колонок
                worksheet = writer.sheets['Сводка']
                for i, col in enumerate(summary.columns):
                    max_len = max(
                        summary[col].astype(str).str.len().max(),
                        len(str(col))
                    ) + 2
                    max_len = min(max_len, 50)
                    worksheet.set_column(i, i, max_len)
            
            print(f"     📊 Сводка сохранена: {summary_filename}")
    
    except Exception as e:
        print(f"     ⚠️ Не удалось создать сводку: {e}")


def create_simple_table(json_file_path: str, output_path: str) -> pd.DataFrame:
    """
    Создает упрощенную таблицу Excel из одного JSON файла.
    """
    # Читаем JSON
    with open(json_file_path, 'rb') as f:
        raw = f.read()
        encoding = chardet.detect(raw)['encoding'] or 'utf-8'
    
    data = json.loads(raw.decode(encoding, errors='ignore'))
    
    # Создаем простую таблицу
    rows = []
    
    for result in data.get('results', []):
        row = {
            'Пункт МОПБ': result.get('punkt', ''),
            'Страница': result.get('page', ''),
            'Соответствие норме': result.get('status', ''),
            'Текст МОПБ': result.get('mopb_text', '')[:200] + '...' if len(result.get('mopb_text', '')) > 200 else result.get('mopb_text', ''),
            'Статьи ФЗ': '',
            'Текст ФЗ': ''
        }
        
        # Добавляем ссылки на ФЗ
        fz_refs = result.get('fz_references', [])
        if fz_refs:
            articles = []
            texts = []
            for ref in fz_refs:
                article = ref.get('article', '')
                if article:
                    articles.append(f"ст. {article}")
                
                norm_text = ref.get('norm_text', '')
                if norm_text:
                    first_line = norm_text.split('\n')[0][:100]
                    texts.append(first_line)
            
            row['Статьи ФЗ'] = ', '.join(articles)
            row['Текст ФЗ'] = ' | '.join(texts)
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Сохраняем в Excel
    excel_path = output_path.replace('.csv', '.xlsx')
    with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Данные', index=False)
        
        # Автонастройка ширины колонок
        worksheet = writer.sheets['Данные']
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
            max_len = min(max_len, 50)
            worksheet.set_column(i, i, max_len)
    
    return df


def batch_process_json_files(
    input_folder: str,
    output_folder: str,
    create_detailed: bool = True,
    create_simple: bool = True,
    create_summary: bool = True
) -> Dict[str, List[str]]:
    """
    Пакетная обработка всех JSON файлов с сохранением в Excel.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    input_path = Path(input_folder)
    json_files = list(input_path.glob('*.json'))
    
    results = {
        'detailed': [],
        'simple': [],
        'summary': []
    }
    
    for json_file in json_files:
        print(f"\n📄 Обработка: {json_file.name}")
        
        try:
            # Читаем JSON
            with open(json_file, 'rb') as f:
                raw = f.read()
                encoding = chardet.detect(raw)['encoding'] or 'utf-8'
            
            data = json.loads(raw.decode(encoding, errors='ignore'))
            
            base_name = json_file.stem
            
            if create_simple:
                # Простая таблица Excel
                simple_path = os.path.join(output_folder, f"{base_name}_simple.xlsx")
                df_simple = create_simple_table(str(json_file), simple_path)
                results['simple'].append(simple_path)
                print(f"  ✅ Простая таблица: {len(df_simple)} строк")
            
            if create_detailed or create_summary:
                # Детальная обработка
                rows = []
                base_info = {
                    'doc_code': data.get('doc_code', ''),
                    'norm_file': data.get('norm_file', ''),
                    'total_references': data.get('total_references', 0),
                    'found_in_norm': data.get('found_in_norm', 0),
                    'not_found_in_norm': data.get('not_found_in_norm', 0)
                }
                
                for result in data.get('results', []):
                    row = base_info.copy()
                    row.update({
                        'punkt': result.get('punkt', ''),
                        'page': result.get('page', ''),
                        'status': result.get('status', ''),
                        'mopb_text': result.get('mopb_text', '').replace('\n', ' ')[:500],
                        'explanation': result.get('explanation', '').replace('\n', ' ')[:500]
                    })
                    
                    fz_refs = result.get('fz_references', [])
                    if fz_refs:
                        for fz_ref in fz_refs:
                            detailed_row = row.copy()
                            detailed_row.update({
                                'fz_article': fz_ref.get('article', ''),
                                'fz_part': fz_ref.get('part', ''),
                                'fz_norm_text': fz_ref.get('norm_text', '').replace('\n', ' ')[:1000]
                            })
                            rows.append(detailed_row)
                    else:
                        row.update({'fz_article': '', 'fz_part': '', 'fz_norm_text': ''})
                        rows.append(row)
                
                if create_detailed and rows:
                    df_detailed = pd.DataFrame(rows)
                    detailed_path = os.path.join(output_folder, f"{base_name}_detailed.xlsx")
                    
                    # Сохраняем в Excel
                    with pd.ExcelWriter(detailed_path, engine='xlsxwriter') as writer:
                        df_detailed.to_excel(writer, sheet_name='Детали', index=False)
                        
                        # Автонастройка ширины колонок
                        worksheet = writer.sheets['Детали']
                        for i, col in enumerate(df_detailed.columns):
                            max_len = max(df_detailed[col].astype(str).str.len().max(), len(str(col))) + 2
                            max_len = min(max_len, 50)
                            worksheet.set_column(i, i, max_len)
                    
                    results['detailed'].append(detailed_path)
                    print(f"  ✅ Детальная таблица: {len(df_detailed)} строк, {len(df_detailed.columns)} колонок")
                
                if create_summary and rows:
                    df = pd.DataFrame(rows)
                    if 'punkt' in df.columns:
                        summary = df.groupby('punkt').agg({
                            'page': 'first',
                            'status': 'first',
                            'fz_article': lambda x: ', '.join(set(str(i) for i in x if i))
                        }).reset_index()
                        
                        summary_path = os.path.join(output_folder, f"{base_name}_summary.xlsx")
                        
                        with pd.ExcelWriter(summary_path, engine='xlsxwriter') as writer:
                            summary.to_excel(writer, sheet_name='Сводка', index=False)
                            
                            # Автонастройка ширины колонок
                            worksheet = writer.sheets['Сводка']
                            for i, col in enumerate(summary.columns):
                                max_len = max(summary[col].astype(str).str.len().max(), len(str(col))) + 2
                                max_len = min(max_len, 50)
                                worksheet.set_column(i, i, max_len)
                        
                        results['summary'].append(summary_path)
                        print(f"  ✅ Сводная таблица: {len(summary)} групп")
        
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    return results


def json_to_excel_all_docs(json_filepath, excel_filepath=None):
    """
    Читает JSON из файла и конвертирует в Excel
    
    Args:
        json_filepath: путь к JSON файлу
        excel_filepath: путь для сохранения Excel (опционально)
    """
    # Определяем имя Excel файла если не указано
    if excel_filepath is None:
        json_path = Path(json_filepath)
        excel_filepath = json_path.with_suffix('.xlsx')
    
    print(f"📖 Чтение JSON из: {json_filepath}")
    
    # Читаем JSON
    json_path = Path(json_filepath)
    
    if not json_path.exists():
        print(f"❌ Файл не найден: {json_filepath}")
        print(f"   Текущая директория: {Path.cwd()}")
        print(f"   Доступные JSON файлы: {list(Path.cwd().glob('*.json'))}")
        return False
    
    try:
        # Читаем содержимое
        content = json_path.read_text(encoding='utf-8')
        
        if not content.strip():
            print("❌ Файл пустой")
            return False
        
        # Парсим JSON
        data = json.loads(content)
        
        # Проверяем структуру
        if 'results' not in data:
            print("⚠️ В JSON нет ключа 'results'")
            print(f"   Доступные ключи: {list(data.keys())}")
            return False
        
        target_date = data.get('target_date', '')
        results = data.get('results', {})
        
        print(f"✅ JSON загружен. Дата: {target_date}, Документов: {len(results)}")
        
        # Создаем данные для Excel
        rows = []
        for doc_code, doc_info in results.items():
            row = {
                "Дата выдачи ГПЗУ": target_date,
                "Код документа": doc_code,
                "Версия": doc_info.get("version", ""),
                "Полное наименование файла с НТД": doc_info.get("full_name", ""),
                "Изменения": doc_info.get("changes", ""),
                "Начало действия": doc_info.get("period_start", ""),
                "Окончание действия": doc_info.get("period_end", "")
            }
            rows.append(row)
        
        # Создаем DataFrame
        df = pd.DataFrame(rows)
        
        # Сохраняем в Excel
        with pd.ExcelWriter(excel_filepath, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Документы', index=False)
            
            # Автонастройка ширины колонок
            worksheet = writer.sheets['Документы']
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
                max_len = min(max_len, 50)
                worksheet.set_column(i, i, max_len)
        
        print(f"✅ Excel сохранен: {excel_filepath}")
        print(f"   Записано строк: {len(rows)}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка формата JSON: {e}")
        print(f"   Позиция ошибки: {e.pos}")
        print(f"   Содержимое файла:\n{content[:200]}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


# Пример использования
if __name__ == "__main__":
    # Пакетная обработка всех JSON в Excel
    result = batch_process_json_files(
        input_folder="input_json",
        output_folder="output_excel",
        create_detailed=True,
        create_simple=True,
        create_summary=True
    )
    
    print(f"\n✅ Обработка завершена!")
    print(f"   Детальных файлов: {len(result['detailed'])}")
    print(f"   Простых файлов: {len(result['simple'])}")
    print(f"   Сводных файлов: {len(result['summary'])}")

def _process_all_errors_file(output_dir):
    json_filepath = os.path.join(output_dir, 'Все_ошибки.json')
    excel_filepath = os.path.join(output_dir, 'Все_ошибки.xlsx')
    json_path = Path(json_filepath)
    content = json_path.read_text(encoding='utf-8')

    if not content.strip():
        print("❌ Файл пустой")
        df = pd.DataFrame()
        with pd.ExcelWriter(excel_filepath, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Документы', index=False)
        return excel_filepath
        
    # Парсим JSON
    data = json.loads(content)

    rows = []
    for d in data:
        row = {
                "Код документа": d.get('doc_code', ''),
                "Файл нормативного документа": d.get('norm_file', ''),
                "Цитата со ссылкой на НТД": d.get('punkt', ''),
                "Страница проектной документации": d.get('page', ''),
                "Текст проектной документации": d.get('mopb_text', ''),
                "Соответствие норме": d.get('status', ''),
                "Объяснение модели": d.get('explanation', ''),
                "Номера пунктов нормы": 'пункт ' + d.get('punkt_number', '') if d.get('punkt_number', '') else '',
                "Статья": d.get('article', ''),
                "Часть": d.get('part', ''),
                "Текст нормы": d.get('norm_text', ''),
                "Примечание": d.get('comment', '')
            }
        rows.append(row)

                # Создаем DataFrame
    df = pd.DataFrame(rows)
        
    mapping = {
                'ok': 'Соответствует',
                'not_ok': 'Не соответствует',
                'not_found': 'Не найден в норме',
                'error': 'Ошибка обработки'
                }

    try:
        df['Соответствие норме'] = df['Соответствие норме'].map(mapping)
    except:
        print('Не удалось найти поле статус')
        
                # Сохраняем в Excel
    with pd.ExcelWriter(excel_filepath, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Документы', index=False)
            
        # Автонастройка ширины колонок
        worksheet = writer.sheets['Документы']
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
            max_len = min(max_len, 50)
            worksheet.set_column(i, i, max_len)
        
    print(f"✅ Excel сохранен: {excel_filepath}")
    print(f"   Записано строк: {len(rows)}")
    return excel_filepath
