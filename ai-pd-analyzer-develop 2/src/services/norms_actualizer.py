import fitz
import json
import os
import re
from datetime import datetime
import ollama
import shutil
import pandas as pd

from .config import load_config

_cfg = load_config()
OLLAMA_URL = _cfg.ollama_url
NORMS_MODEL = _cfg.norms_model

# ======== 2 ЭТАП ==========
def searchActualNorm(target_date:str, normsList: str, output_folder: str=''):
    # ИЩЕМ ДЛЯ НАЙДЕННОЙ АКТУАЛЬНОЙ ДАТЫ ПЕРЕЧЕНЬ АКТУАЛЬНЫХ ДОКУМЕНТОВ
    print("ЗАПУСК ПОЛНОГО АНАЛИЗА НЕСКОЛЬКИХ СП")
    #SOURCE_PDF = "Perechen.xlsx"
    #DATE_FILE = "issuance_date.txt"
    #target_date = get_target_date()
    SP_LIST = [
        "СП 1.13130",
        "СП 2.13130", 
        "СП 3.13130",
        "СП 4.13130",
        "СП 6.13130",
        "СП 7.13130",
        "СП 8.13130", 
        "СП 10.13130",
        "СП 54.13330",
        "СП 59.13330",
        "СП 60.13330",
        "СП 113.13330", 
        "СП 118.13330",
        "СП 156.13130",
        "СП 253.1325800",
        "СП 256.1325800",
        "СП 484.1311500", 
        "СП 485.1311500",
        "СП 486.1311500",
        "СП 477.1325800"
    ]


    
    results = {}

    for sp_code in SP_LIST:
        answer = get_actual_sp(target_date, sp_code, normsList)
        results[sp_code] = answer
        if not answer:
            print('Документа нет в перечне -> загружаем файл по умолчанию')
    
    _save_summary(results, target_date, output_folder)
    
    print("\n" + "="*80)
    print("РАБОТА ЗАВЕРШЕНА")
    print("="*80)


def _save_summary(results, target_date, output_folder=''):
    
    summary = {
        'target_date': target_date,
        'results': {}
    }

    SP_NOT_IN_PERECHEN = ["СП 54.13330",
                          "СП 59.13330",
                          "СП 118.13330",
                          "СП 253.1325800",
                          "СП 256.1325800"
                            ]
    
    
    for sp_code, answer in results.items():
        if answer:
            summary['results'][sp_code] = {
                'version': answer['version'],
                'full_name': answer.get('full_name', ''),
                'changes': answer.get('changes', ''),
                'period_start': answer['period_start'],
                'period_end': answer['period_end'],
            }
        elif not answer and sp_code in SP_NOT_IN_PERECHEN:
            summary['results'][sp_code] = {
                'version': sp_code,
                'full_name': sp_code,
                'changes': '',
                'period_start': 'Документ не найден в перечне, взят файл по умолчанию',
                'period_end': 'Документ не найден в перечне, взят файл по умолчанию',
            }
            
    if not output_folder:
        filename = "все_СП_результаты.json"
    else:
        filename = os.path.join(output_folder, "все_СП_результаты.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\nСводка сохранена в {filename}")
   
    print("СВОДКА ПО ВСЕМ СП")
    
    for sp_code, data in summary['results'].items():
        print(f"\n{sp_code}:")
        print(f"   {data['version']}")
        if data.get('full_name'):
            print(f"   {data['full_name']}")
        if data.get('changes'):
            print(f"   {data['changes']}")
        print(f"   Период: {data['period_start']} — {data['period_end']}")

def parse_end_date(date_value):
    if isinstance(date_value, str) and date_value == "До внесения изменений":
        return pd.Timestamp.max
    else:
        if pd.isna(date_value):
            return pd.Timestamp.max
        return pd.to_datetime(date_value, dayfirst=True)

def get_df_perechen(norm_list):
    return pd.read_excel(norm_list)


def get_all_versions(sp_code, norm_df):
    sp_version_df = norm_df[norm_df['Документ'].str.contains(sp_code, na=False)]
    return sp_version_df

def get_actual_doc(target_date, sp_df):
    if isinstance(target_date, str):
        target_date = pd.to_datetime(target_date, dayfirst=True)  
    
    df = sp_df.copy()
    
    df['Дата начала'] = pd.to_datetime(df['Дата начала'], dayfirst=True)
    df['Дата окончания'] = pd.to_datetime(df['Дата окончания'], dayfirst=True, errors='coerce')
    
    df['Дата_окончания_parsed'] = df['Дата окончания'].apply(parse_end_date)
    
    mask = (df['Дата начала'] <= target_date) & (df['Дата_окончания_parsed'] > target_date)
    current_docs = df[mask]
    
    if len(current_docs) == 0:
        return pd.Series()
    
    # Если несколько документов, возвращаем последний по дате начала
    return current_docs.sort_values('Дата начала', ascending=False).iloc[0]

def get_actual_sp(target_date, sp_code, norm_list):
    df_all = get_df_perechen(norm_list)
    df_sp = get_all_versions(sp_code, df_all)
    actual_sp = get_actual_doc(target_date, df_sp)

    
    if not actual_sp.empty:
        return get_json_sp(actual_sp)
    else:
        return {}


def get_json_sp(row):

    version = re.findall(r'СП \d+\.\d+\.\d{4}', row['Документ'])

    changes = re.findall(r'\(.+\)?', row['Документ'])

    result = {
        "version": version[0] if version else "",
        "full_name": row['Документ'] if row['Документ'] else "",
        "changes": changes[0] if changes else "",
        "period_start": row['Дата начала'].strftime('%d.%m.%Y') if isinstance(row['Дата начала'], pd.Timestamp) else row['Дата начала'],
        "period_end": row['Дата окончания'].strftime('%d.%m.%Y') if isinstance(row['Дата окончания'], pd.Timestamp) else 'бессрочно'
    }
    print(result)
    return result



# ======== 3 ЭТАП ==========
def copyActualNorm(output_folder=''):
    # КОПИРУЕМ НАЙДЕННЫЕ АКТУАЛЬНЫЕ НОРМЫ в папку Актуальные_нормы
    NORMS_FOLDER = "norms"
    if output_folder:
        OUTPUT_FOLDER = os.path.join(output_folder, "Актуальные_нормы")
        RESULTS_FILE = os.path.join(output_folder, "все_СП_результаты.json")
        
    else:
        OUTPUT_FOLDER = "Актуальные_нормы"
        RESULTS_FILE = "все_СП_результаты.json"
    

    print("="*80)
    print("ЗАПУСК КОПИРОВАНИЯ АКТУАЛЬНЫХ НОРМ")
    print("="*80)
    
    actual_versions = _load_actual_versions(RESULTS_FILE)
    if not actual_versions:
        return
    
    norms_files = _scan_norms_folder(NORMS_FOLDER)
    if not norms_files:
        print("\nПапка norms пуста или не найдена!")
        return
    
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    clear_folder(OUTPUT_FOLDER)
    
    sp_matches = _find_matching_files(actual_versions, norms_files)
    sp_copied = []
    for match in sp_matches:
        result = _copy_file_to_folder(match, OUTPUT_FOLDER, match['sp_code'])
        if result:
            sp_copied.append(result)
            print(f"   {result['new']}")
    
    print(f"\nСкопировано файлов СП: {len(sp_copied)}")
    
    fz_list = ["69-ФЗ",
               "123-ФЗ",
               "184-ФЗ",
               "384-ФЗ",
               "ГОСТ 12.1.004",
               "ГОСТ 31251",
               "ГОСТ 34305",
               "ГОСТ Р 53296",
               "ГОСТ Р 56177",
               "Постановление Правительства РФ от 16.02.2008 N 87",
               "Постановление Правительства РФ от 16.09.2020 N 1479"]
    for fz in fz_list:
        print("\n" + "="*80)
        print(f"ПОИСК {fz}")
        print("="*80)
        doc_file = ''
        for doc_norm in norms_files:
            if fz in doc_norm['name'] :
                doc_file = doc_norm['name']
        if doc_file:
            print(doc_file)
            fz_file = {
                    'name': fz,
                    'file': doc_file,
                    'version_info': {
                        'full_name': doc_file.replace('.docx', '')
                    }
                    }
        else:
            print(f'Для {fz} не удалось найти файл')
        
        if fz_file:
            fz_copied = False
            source = f'norms/{fz_file["file"]}'
            filename = fz_file["file"]
    
            new_filename = f"{fz} - {filename}"
            destination = os.path.join(OUTPUT_FOLDER, new_filename)
            print(f"\nНайден файл {fz}: {fz_file['name']}")
            try:
                shutil.copy2(source, destination)
                fz_copied = True
            except Exception as e:
                print(f"   Ошибка копирования {filename}: {e}")
            if fz_copied:
                print(f"{fz} скопирован")
        else:
            print(f"\nФайл {fz} не найден")
    
    _create_readme(OUTPUT_FOLDER, sp_matches, sp_copied, fz_file, fz_copied)
    
    _show_summary(sp_matches, sp_copied, fz_file, fz_copied, OUTPUT_FOLDER)
    
    print("\n" + "="*80)
    print("РАБОТА ЗАВЕРШЕНА")
    print("="*80)

def clear_folder(folder_path):
    """
    Удаляет все файлы в папке, но сохраняет саму папку и подпапки
    """
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # Удаляет файлы и ссылки
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Удаляет подпапки и их содержимое
        except Exception as e:
            print(f'Ошибка при удалении {file_path}: {e}')

def _show_summary(sp_matches, sp_copied, fz_file, fz_copied, output_folder):
    
    print("ИТОГОВАЯ СВОДКА")
  
    
    print(f"\nФайлы скопированы в папку: {output_folder}")
    print(f"\nНайдено и скопировано файлов СП: {len(sp_matches)}")
    
    for match, copied in zip(sp_matches, sp_copied):
        print(f"\n   {match['sp_code']}:")
        print(f"      {copied['new']}")
        print(f"      {copied['size']:.1f} KB")
    

def _create_readme(output_folder, sp_matches, sp_copied, fz_file, fz_copied):
  
    readme_path = os.path.join(output_folder, "README.txt")
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("АКТУАЛЬНЫЕ НОРМЫ\n")
        f.write("="*60 + "\n")
        f.write(f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n")
        
        f.write("СПИСОК ФАЙЛОВ:\n")
        f.write("-"*60 + "\n")
        
        for i, (match, copied) in enumerate(zip(sp_matches, sp_copied), 1):
            f.write(f"\n{i}. {match['sp_code']}\n")
            f.write(f"   Искали: {match['version_info']['search_key']}\n")
            f.write(f"   Найден: {match['version_info']['full_name']}\n")
            f.write(f"   Сохранен как: {copied['new']}\n")
            f.write(f"   Размер: {copied['size']:.1f} KB\n")
        
        
        f.write("\n" + "="*60 + "\n")
        total = len(sp_matches) + (1 if fz_copied else 0)
        f.write(f"Всего файлов: {total}")
    
    print(f"\nСоздан файл описания: {readme_path}")



def despacer(text):
    return text.replace(', ', ',').replace('- ', '-').replace('№ ', '№')

def _find_matching_files(actual_versions, norms_files):
    """
    Находит файлы, соответствующие актуальным версиям
    """
 
    print("ПОИСК ФАЙЛОВ СП")
     
    matches = []
    
    for sp_code, version_info in actual_versions.items():
        doc_file = ""
        print(version_info)
        print(f"\nИщем для {sp_code}:")
        print(f"   {version_info['search_key']}")
        for doc_norm in norms_files:
            if version_info['changes']:
                if version_info['version'] in doc_norm['name'] and despacer(version_info['changes']) in despacer(doc_norm['name']):
                    doc_file = doc_norm['name']
            else:
                if version_info['version'] in doc_norm['name'] and 'изм' not in doc_norm['name'] and version_info['status'] == 'actual':
                    doc_file = doc_norm['name']
                if version_info['version'] in doc_norm['name'] and version_info['status'] == 'default':
                    doc_file = doc_norm['name']
        if doc_file:
            print(doc_file)
            matches.append({
                    'sp_code': sp_code,
                    'file': doc_file,
                    'version_info': version_info
                    }
            )
        else:
            print(f'Для {sp_code} не удалось найти файл')

    return matches

def _scan_norms_folder(norms_path):
    print("СКАНИРОВАНИЕ ПАПКИ norms")
    
    if not os.path.exists(norms_path):
        print(f"Папка {norms_path} не найдена!")
        return []
    
    files = os.listdir(norms_path)
    files.sort()
    
    print(f"Найдено файлов: {len(files)}")
    
    file_list = []
    for file in files:
        file_path = os.path.join(norms_path, file)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path) / 1024
            file_list.append({
                'name': file,
                'path': file_path,
                'size': file_size
            })
            print(f"   {file} ({file_size:.1f} KB)")
    
    return file_list

def _copy_file_to_folder(file_info, output_folder, prefix):
     
    source = f'norms/{file_info["file"]}'
    filename = file_info['version_info']['full_name']
    
    new_filename = f"{prefix} - {filename}.docx"
    destination = os.path.join(output_folder, new_filename)
    
    try:
        shutil.copy2(source, destination)
        return {
            'original': filename,
            'new': new_filename,
            'size': os.path.getsize(source)
        }
    except Exception as e:
        print(f"   Ошибка копирования {filename}: {e}")
        return None
    
def _load_actual_versions(results_file):
    print("ЗАГРУЗКА АКТУАЛЬНЫХ ВЕРСИЙ")
    
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        actual_versions = {}
        
        for sp_code, version_data in data['results'].items():
            version = version_data['version']
            changes = version_data.get('changes', '')
            
            if changes and 'свод правил' not in changes.lower():
                full_name = f"{version} {changes}"
            else:
                full_name = version
            
            if 'по умолчанию' in version_data['period_end']:
                status = 'default'
            else:
                status = 'actual'
            
            actual_versions[sp_code] = {
                'version': version,
                'changes': changes,
                'full_name': full_name,
                'search_key': full_name,
                'doc_name': version_data.get('full_name', ''),
                'status': status
            }
            
            print(f"\n{sp_code}:")
            print(f"   Ищем: {full_name}")
        
        return actual_versions
        
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        return None