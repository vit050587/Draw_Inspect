import os
import json
import ollama
import re
import docx

from .config import load_config
from .documents_registry import is_fz_document

OLLAMA_URL = load_config().ollama_url
NORMS_MODEL = load_config().norms_model

# ======== 6 ЭТАП ==========
def comparisionМОРВ(progress_callback=None, output_folder=''):
    # СРАВНИВАЕМ проектный документ с актуальными нормами
    # Используем punkt_numbers для СП и fz_references для 123-ФЗ

    MOPB_FOLDER = os.path.join(output_folder, "MOPB_ссылки_с_номерами")
    NORMS_FOLDER = os.path.join(output_folder, "Актуальные_нормы")
    OUTPUT_FOLDER = os.path.join(output_folder, "MOPB_сравнение")

    DOC_FILE_MAP = {
        'СП 1.13130': 'СП 1.13130',
        'СП 2.13130': 'СП 2.13130',
        'СП 3.13130': 'СП 3.13130',
        'СП 4.13130': 'СП 4.13130',
        'СП 6.13130': 'СП 6.13130',
        'СП 7.13130': 'СП 7.13130',
        'СП 8.13130': 'СП 8.13130',
        'СП 9.13130': 'СП 9.13130',
        'СП 10.13130': 'СП 10.13130',
        'СП 54.13330': 'СП 54.13330',
        'СП 59.13330': 'СП 59.13330',
        'СП 60.13330': 'СП 60.13330',
        'СП 113.13330': 'СП 113.13330',
        'СП 118.13330': 'СП 118.13330',
        'СП 156.13130': 'СП 156.13130',
        'СП 253.1325800': 'СП 253.1325800',
        'СП 256.1325800': 'СП 256.1325800',
        'СП 484.1311500': 'СП 484.1311500',
        'СП 485.1311500': 'СП 485.1311500',
        'СП 486.1311500': 'СП 486.1311500',
        'СП 477.1325800': 'СП 477.1325800',
        'ГОСТ Р 53296': 'ГОСТ Р 53296',
        'ГОСТ 12.1.004': 'ГОСТ 12.1.004',
        'ГОСТ 34305': 'ГОСТ 34305-2017',
        'ГОСТ 31251': 'ГОСТ 31251-2008',
        'ГОСТ Р 56177': 'ГОСТ Р 56177-2014',
        'Постановление Правительства РФ от 16.02.2008 N 87': 'Постановление Правительства РФ от 16.02.2008 N 87',
        'Постановление Правительства РФ от 16.09.2020 N 1479': 'Постановление Правительства РФ от 16.09.2020 N 1479',
        '123-ФЗ': 'Федеральный закон от 22.07.2008 N 123-ФЗ',
        '384-ФЗ': 'Федеральный закон от 30.12.2009 N 384-ФЗ',
        '69-ФЗ': 'Федеральный закон от 21.12.1994 N 69-ФЗ',
        '184-ФЗ': 'Федеральный закон от 27.12.2002 N 184-ФЗ',
        'Специальные технические условия': 'Специальные технические условия'
    }
     
    print("СРАВНЕНИЕ ВСЕХ ДОКУМЕНТОВ С АКТУАЛЬНЫМИ НОРМАМИ")
    print("="*80)
    print(f"  Используются данные из папки: {MOPB_FOLDER}")
 
    json_files = [
        os.path.join(MOPB_FOLDER, "MOPB_СП_1.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_2.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_3.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_4.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_6.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_7.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_8.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_9.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_10.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_54.13330_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_59.13330_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_60.13330_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_113.13330_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_118.13330_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_156.13130_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_253.1325800_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_256.1325800_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_484.1311500_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_485.1311500_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_486.1311500_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_СП_477.1325800_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_ГОСТ_Р_53296_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_ГОСТ_12.1.004_91_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_ГОСТ_34305_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_ГОСТ_31251_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_ГОСТ_Р_56177_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_Постановление_Правительства_N_87_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_Постановление_Правительства_N_1479_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_123_ФЗ_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_69_ФЗ_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_384_ФЗ_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_184_ФЗ_пункты_полные.json"),
        os.path.join(MOPB_FOLDER, "MOPB_Специальные_технические_условия_пункты_полные.json")
    ]

    total_files = len(json_files)

    if progress_callback:
        progress_callback(0.0, f"Найдено {total_files} файлов для сравнения")
        
    doc_code = ''

    results = []

    for i, json_file in enumerate(json_files):
        if os.path.exists(json_file):
            file_progress = (i + 1) / total_files
            # Определение кода документа
            doc_code = None
            if "СП_1.13130" in json_file:
                doc_code = "СП 1.13130"
            elif "СП_2.13130" in json_file:
                doc_code = "СП 2.13130"
            elif "СП_3.13130" in json_file:
                doc_code = "СП 3.13130"
            elif "СП_4.13130" in json_file:
                doc_code = "СП 4.13130"
            elif "123_ФЗ" in json_file:
                doc_code = "123-ФЗ"
            elif "СП_6.13130" in json_file:
                doc_code = "СП 6.13130"
            elif "СП_7.13130" in json_file:
                doc_code = "СП 7.13130"
            elif "СП_8.13130" in json_file:
                doc_code = "СП 8.13130"
            elif "СП_9.13130" in json_file:
                doc_code = "СП 9.13130"
            elif "СП_10.13130" in json_file:
                doc_code = "СП 10.13130"
            elif "СП_54.13330" in json_file:
                doc_code = "СП 54.13330"
            elif "СП_59.13330" in json_file:
                doc_code = "СП 59.13330"
            elif "СП_60.13330" in json_file:
                doc_code = "СП 60.13330"
            elif "СП_113.13330" in json_file:
                doc_code = "СП 113.13330"
            elif "СП_118.13330" in json_file:
                doc_code = "СП 118.13330"
            elif "СП_156.13130" in json_file:
                doc_code = "СП 156.13130"
            elif "СП_253.1325800" in json_file:
                doc_code = "СП 253.1325800"
            elif "СП_256.1325800" in json_file:
                doc_code = "СП 256.1325800"
            elif "СП_484.1311500" in json_file:
                doc_code = "СП 484.1311500"
            elif "СП_485.1311500" in json_file:
                doc_code = "СП 485.1311500"
            elif "СП_486.1311500" in json_file:
                doc_code = "СП 486.1311500"
            elif "СП_477.1325800" in json_file:
                doc_code = "СП 477.1325800"
            elif "ГОСТ_Р_53296" in json_file:
                doc_code = "ГОСТ Р 53296"
            elif "ГОСТ_12.1.004" in json_file:
                doc_code = "ГОСТ 12.1.004"
            elif "ГОСТ_34305" in json_file:
                doc_code = "ГОСТ 34305"
            elif "ГОСТ_31251" in json_file:
                doc_code = "ГОСТ 31251"
            elif "ГОСТ_Р_56177" in json_file:
                doc_code = "ГОСТ Р 56177"
            elif "Постановление_Правительства_N_87" in json_file:
                doc_code = "Постановление Правительства РФ от 16.02.2008 N 87"
            elif "Постановление_Правительства_N_1479" in json_file:
                doc_code = "Постановление Правительства РФ от 16.09.2020 N 1479"
            elif "69_ФЗ" in json_file:
                doc_code = "69-ФЗ"
            elif "384_ФЗ" in json_file:
                doc_code = "384-ФЗ"
            elif "184_ФЗ" in json_file:
                doc_code = "184-ФЗ"
            elif "Специальные_технические_условия" in json_file:
                doc_code = "Специальные технические условия"
            
            if doc_code:

                if progress_callback:
                    progress_callback(
                        file_progress, 
                        f"Сравнение {doc_code} ({i + 1}/{total_files})"
                    )

                result = _process_document_comparison(doc_code, json_file, NORMS_FOLDER, OUTPUT_FOLDER, doc_file_map=DOC_FILE_MAP)
                if result:
                    results.append(result)
        else:
            print(f"Файл не найден: {json_file}")

    if progress_callback:
        progress_callback(0.95, "Формирование итоговой статистики...")
    
    print("ИТОГОВАЯ СТАТИСТИКА")
    
    total_refs = 0
    total_found = 0
    total_not_found = 0
    total_skipped = 0
    
    for r in results:
        print(f"\n{r['doc_code']}:")
        print(f"   Всего обработано ссылок: {r['total']}")
        print(f"     Найдено в норме: {r['found']}")
        print(f"     Не найдено в норме: {r['not_found']}")
        print(f"     Пропущено (нет номеров): {r['skipped']}")
        print(f"     {r['file']}")
        
        total_refs += r['total']
        total_found += r['found']
        total_not_found += r['not_found']
        total_skipped += r['skipped']
    
    print("\n" + "="*80)
    print("СВОДКА:")
    print(f"   Всего проанализировано ссылок: {total_refs}")
    print(f"    Найдено в нормах: {total_found}")
    print(f"    Не найдено в нормах: {total_not_found}")
    print(f"    Пропущено (нет номеров): {total_skipped}")

    if progress_callback:
        progress_callback(1.0, f"Сравнение завершено. Обработано {len(results)} документов, {total_refs} ссылок")
    
    print("РАБОТА ЗАВЕРШЕНА")


def _process_document_comparison(doc_code, json_file, norms_folder, output_folder, doc_file_map):
    """
    Сравнивает ссылки одного документа с нормой.
    Каждая ссылка обрабатывается отдельно, даже если содержит несколько пунктов.
    """
    print("\n" + "="*80)
    print(f"СРАВНЕНИЕ {doc_code}")
    print("="*80)
    
    session_dir = output_folder.replace('MOPB_сравнение', '')
    print('путь к файлу с датой', session_dir)

    loaded_code, references = _load_mopb_data(json_file)
    if loaded_code is None:
        print(f"Пропускаем {doc_code} - файл не найден")
        return None


    if doc_code == "Специальные технические условия":
        stu = True if _find_norm_file(doc_code, norms_folder, doc_file_map) else False
    else:
        stu = False

    norm_file = _find_norm_file(doc_code, norms_folder, doc_file_map)
    if not norm_file and doc_code != "Специальные технические условия":
        print(f"Файл нормы для {doc_code} не найден")
        return None
    if doc_code == "Специальные технические условия" and stu and not norm_file:
        print(f"Файл нормы для СТУ не найден")
        return None
    if doc_code == "Специальные технические условия" and stu and norm_file:
        print(f'СТУ найдены, идём дальше')
        pass
    if doc_code == "Специальные технические условия" and not stu and not norm_file:
        print(f'СТУ не загружены и не должны быть')
        pass
        
    norm_text = _read_docx_file(norm_file)
    if not norm_text and doc_code != "Специальные технические условия":
        print(f'В документе для {doc_code} не найдено текста')
        return None
    
    print("СРАВНЕНИЕ ПУНКТОВ")
    
    results = []
    found_count = 0
    not_found_count = 0
    skipped_count = 0
    
    for i, ref in enumerate(references, 1):
        mopb_text = ref['full_paragraph']
        page_number = ref.get('page', None)
        
        if is_fz_document(doc_code):
            # Для 123-ФЗ обрабатываем каждую статью/часть отдельно
            if 'fz_references' in ref and ref['fz_references']:
                fz_refs = ref['fz_references']
                
                if len(fz_refs) == 0:
                    skipped_count += 1
                    print(f"\n{i}. Пропускаем (нет статей): {ref.get('punkt', '')}")
                    continue
                
                # Обрабатываем каждую ссылку на статью отдельно
                for fz_ref in fz_refs:
                    article = fz_ref.get('article')
                    part = fz_ref.get('part')
                    
                    if not article:
                        print(f"\n{i}. Пропускаем (нет номера статьи): {ref.get('punkt', '')}")
                        continue
                    
                    punkt_display = f"статья {article}" + (f", часть {part}" if part else "")
                    
                    print(f"\n{i}. {doc_code} {punkt_display}")
                    print(f"Текст из MOPB:")
                    print(f"{mopb_text[:200]}..." if len(mopb_text) > 200 else mopb_text)
                    print()
                    
                    # Ищем текст пункта в норме
                    norm_punkt_text = _extract_norm_punkt(norm_text, article, doc_code, part)
                    
                    if not norm_punkt_text:
                        print(f"  {punkt_display} НЕ НАЙДЕН в норме!")
                        not_found_count += 1
                        
                        result_item = {
                            'punkt': ref.get('punkt', ''),
                            'page': page_number,
                            'mopb_text': mopb_text,
                            'norm_text': None,
                            'status': 'not_found',
                            'explanation': f'{punkt_display} отсутствует в норме',
                            'article': article,
                            'part': part,
                            'comment': ""
                        }
                        results.append(result_item)
                        continue
                    
                    found_count += 1
                    
                    print("Анализ соответствия...")
                    punkt_info = {
                        'article': article,
                        'part': part,
                        'punkt': ref.get('punkt', '')
                    }
                    result = _compare_with_llm(mopb_text, norm_punkt_text, doc_code, punkt_info, output_folder=session_dir)
                    
                    if result.get('status') == 'ok':
                        print(f"  {result.get('explanation', 'Соответствует')}")
                    elif result.get('status') == 'not_ok':
                        print(f"  {result.get('explanation', 'Не соответствует')}")
                    else:
                        print(f"  Ошибка анализа")
                    
                    if doc_code == '384-ФЗ' and part == '17' and article == '17':
                        comment = 'Проверить наличие обоснования в соответствии с ч.6 ст.15.'
                    else:
                        comment = ''

                    result_item = {
                        'punkt': ref.get('punkt', ''),
                        'page': page_number,
                        'mopb_text': mopb_text,
                        'norm_text': norm_punkt_text,
                        'status': result.get('status', 'error'),
                        'explanation': result.get('explanation', ''),
                        'article': article,
                        'part': part,
                        'comment': comment
                    }
                    results.append(result_item)
            else:
                skipped_count += 1
                print(f"\n{i}. Пропускаем (нет поля fz_references): {ref.get('punkt', '')}")
                continue
                
        else:
            # Для СП и других документов
            if 'punkt_numbers' in ref and ref['punkt_numbers']:
                punkt_numbers = ref['punkt_numbers']
                
                if len(punkt_numbers) == 0:
                    skipped_count += 1
                    print(f"\n{i}. Пропускаем (нет номеров пунктов): {ref.get('punkt', '')}")
                    continue
                
                # Обрабатываем каждый пункт отдельно
                for punkt_num in punkt_numbers:
                    punkt_display = f"пункт {punkt_num}"
                    
                    print(f"\n{i}. {doc_code} {punkt_display}")
                    print(f"Текст из MOPB:")
                    print(f"{mopb_text[:200]}..." if len(mopb_text) > 200 else mopb_text)
                    print()

                    if not stu and doc_code == "Специальные технические условия":
                        result_item = {
                            'punkt': ref.get('punkt', ''),
                            'page': page_number,
                            'mopb_text': mopb_text,
                            'norm_text': None,
                            'status': 'not_found',
                            'explanation': f'Файл СТУ не загружен',
                            'punkt_number': punkt_num,
                            'comment': ''
                        }
                        results.append(result_item)
                        continue

                    
                    # Ищем текст пункта в норме
                    norm_punkt_text = _extract_norm_punkt(norm_text, punkt_num, doc_code)
                    
                    if not norm_punkt_text:
                        print(f"  {punkt_display} НЕ НАЙДЕН в норме!")
                        not_found_count += 1
                        
                        result_item = {
                            'punkt': ref.get('punkt', ''),
                            'page': page_number,
                            'mopb_text': mopb_text,
                            'norm_text': None,
                            'status': 'not_found',
                            'explanation': f'{punkt_display} отсутствует в норме',
                            'punkt_number': punkt_num,
                            'comment': ''
                        }
                        results.append(result_item)
                        continue
                    
                    found_count += 1
                    
                    print("Анализ соответствия...")
                    punkt_info = {
                        'punkt_number': punkt_num,
                        'punkt': ref.get('punkt', '')
                    }
                    result = _compare_with_llm(mopb_text, norm_punkt_text, doc_code, punkt_info, output_folder=session_dir)
                    
                    if result.get('status') == 'ok':
                        print(f"  {result.get('explanation', 'Соответствует')}")
                    elif result.get('status') == 'not_ok':
                        print(f"  {result.get('explanation', 'Не соответствует')}")
                    else:
                        print(f"  Ошибка анализа")
                    
                    result_item = {
                        'punkt': ref.get('punkt', ''),
                        'page': page_number,
                        'mopb_text': mopb_text,
                        'norm_text': norm_punkt_text,
                        'status': result.get('status', 'error'),
                        'explanation': result.get('explanation', ''),
                        'punkt_number': punkt_num,
                        'comment': ''
                    }
                    results.append(result_item)
            else:
                skipped_count += 1
                print(f"\n{i}. Пропускаем (нет поля punkt_numbers): {ref.get('punkt', '')}")
                continue
    
    print(f"\nСтатистика для {doc_code}:")
    print(f"   Всего ссылок: {len(references)}")
    print(f"     Пропущено (нет номеров): {skipped_count}")
    print(f"     Обработано пунктов: {len(results)}")
    print(f"     Найдено в норме: {found_count}")
    print(f"     Не найдено в норме: {not_found_count}")
    
    os.makedirs(output_folder, exist_ok=True)
    output_file = os.path.join(output_folder, f"{doc_code.replace(' ', '_').replace('-', '_')}_сравнение.json")
    
    output = {
        'doc_code': doc_code,
        'norm_file': os.path.basename(norm_file) if norm_file else 'Файл не был загружен',
        'total_references': len(references),
        'skipped_no_numbers': skipped_count,
        'processed': len(results),
        'found_in_norm': found_count,
        'not_found_in_norm': not_found_count,
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\nРезультат сохранен в {output_file}")
    
    return {
        'doc_code': doc_code,
        'total': len(results),
        'found': found_count,
        'not_found': not_found_count,
        'skipped': skipped_count,
        'file': output_file
    }

def _compare_with_llm(mopb_text, norm_text, doc_code, punkt_info, output_folder=''):
    """
    Сравнивает текст из проекта с текстом нормы (всегда один пункт)
    """

    date_path = os.path.join(output_folder, 'issuance_date.txt')
    try:
        with open(date_path, 'r', encoding='utf-8') as f:
            actual_date = f.readline().strip()
    except:
        print("Файл с датой не найден")
        actual_date = ''

    if is_fz_document(doc_code):
        if punkt_info.get('part'):
            doc_name = f"Федеральный закон № {doc_code}, часть {punkt_info['part']}, статья {punkt_info['article']}"
            punkt_number = f"часть {punkt_info['part']}, статья {punkt_info['article']}"
        else:
            doc_name = f"Федеральный закон № {doc_code}, статья {punkt_info['article']}"
            punkt_number = f"статья {punkt_info['article']}"
    else:
        punkt_number = punkt_info.get('punkt_number', punkt_info.get('punkt', ''))
        doc_name = f"{doc_code}, пункт {punkt_number}"
    
    prompt = f"""Ты — эксперт по нормативно-технической документации по противопожарной безопасности. Твоя задача — верифицировать корректность ссылки на норму в тексте проекта.
ОТВЕЧАЙ ТОЛЬКО И ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ.

НОРМАТИВНЫЙ ДОКУМЕНТ: {doc_name}
В некоторых случаях Федеральный закон {doc_code} может называться не Федеральный закон, а технический регламент. Главное, что №{doc_code}
ПУНКТ: {punkt_number}

ТЕКСТ НОРМЫ (актуальная редакция): 
{norm_text}

ТЕКСТ ИЗ ПРОЕКТА (MOPB):
{mopb_text}

Ищи в норме информацию актуальную на {actual_date}

Найди ПУНКТ {punkt_number} НОРМАТИВНОГО ДОКУМЕНТА {doc_name} в тексте проекта и определи к какому участку текста проекта относится этот пункт. Далее работай только с этим участком текста.
Определи точно участок текста нормы, который относится к данному пункту. Это может быть как весь ТЕКСТ НОРМЫ, так и его часть. Далее работай только с этим участком текста.

ПРАВИЛА ПРОВЕРКИ (читай в порядке убывания важности):

1. ГЛАВНЫЙ КРИТЕРИЙ — СМЫСЛ. Оценивай, соответствует ли суть нормы сути фрагмента проекта. Они должны говорить об одном и том же предмете.

2. Если в тексте нормы указано, что необходимо предпринимать некоторые технические решения для обеспечения чего-либо, то в тексте проекта могут быть реализованы конкретные меры. В этом случае сравнивай по контексту и общему смыслу.
Например, если в тексте нормы указано о необходимости обеспечивать планировочные решения (в том числе лестниц и пролетов) для эвакуации населения, а в тексте проекта указаны конкретные параметры лестниц (планировочные решения), то это ОК.

3. ПРОВЕРКА ПУНКТА. Если в тексте проекта указан конкретный пункт (например, «п. 5.3») и он относится к {doc_name}, то:
   - Убедись, что такой пункт существует в переданном тексте нормы.
   - Убедись, что пункт не помечен как «утратил силу» или «не действует» и указанная дата утраты действия наступила до {actual_date}.
   - Если пункта нет или он утратил силу → статус not_ok.
   - Если в тексте несколько ссылок на разные документы, то сверяй только с тем, который {doc_name}. Например, "согласно СП 52.13330.2016, п. 4.3.12 СП 1.13130.2020.", то сравнивай только с п. 4.3.12 СП 1.13130.2020.
   - Может быть указан диапазон пунктов, но проверяться тоько по одному из пунктов, например, "согласно п. 3.1-3.3", то пункт 3.2., входит в этот диапазон
   - Может быть указано несколько пунктов, но проверяться только по одному из них. Главное, чтобы пункт точно был указан

4. ДРУГИЕ ДОКУМЕНТЫ ИГНОРИРУЙ. Если в тексте проекта упоминаются иные ГОСТы, СНиПы, СанПиНы, СП и т.п., считай, что они не влияют на оценку текущей ссылки. Также не ищи связи указанного документа {doc_name} и других документов, указанных в тексте.
ЕСЛИ УКАЗАНЫ ДРУГИЕ ПУНКТЫ, КРОМЕ {punkt_number}, И ТЫ СЧИТАЕШЬ, ЧТО ОНИ ОТНОСЯТСЯ К ТОМУ ЖЕ ДОКУМЕНТУ, ТО ИГНОРИРУЙ ИХ.
В тексте нормы тоже могут быть ссылки на другие документы, игнорируй эти ссылки. В том числе текст нормы может быть указан в редакции другого нормативного акта. Это OK.
Не принимай решение о несоответствии, исходя из упоминания документов, и не упоминай его в ответе.

5. НЕ ТРЕБУЙ ПОЛНОТЫ ЦИТИРОВАНИЯ. Проект может использовать только часть нормы, один аспект или давать общую отсылку — это НОРМАЛЬНО. Статус ok.

6. Если в тексте проекта указаны числовые значения, уточняющие текст нормы, или конкретные решения, соответствующие контексту, то это OK.

7. Таблицы могут иметь нумерацию в тексте нормы отличающуюся от текста проекта. Это ok, не обращай на это внимание.

8. ОШИБКОЙ СЧИТАЕТСЯ ТОЛЬКО:
   - Прямое противоречие (в проекте написано иначе, чем требует норма).
   - Ссылка на несуществующий/утративший силу пункт.
   - Смысловое несоответствие (норма про одно, а текст проекта про другое).

КЛЮЧЕВОЕ ПРАВИЛО:
Частичное соответствие = полное соответствие. Неполнота раскрытия нормы в проектной документации является нормой проектирования, а не ошибкой.

ПРИМЕРЫ:

ОК:
- Проект: «Расстояние между эвакуационными выходами должно соответствовать п. 4.2.3»
  Норма в п. 4.2.3: «Расстояние между выходами должно быть не более 25 м»
  → Статус ok (требование выполнено, даже если проект не указал цифру 25 м)

ОК (частичное использование):
- Проект: «Пожарные отсеки должны быть оборудованы АПС по п. 6.1»
  Норма в п. 6.1: содержит 5 подпунктов о типах помещений, порогах срабатывания, контроле линий связи
  → Статус ok (проект отсылает к норме корректно, не обязан перечислять всё)

NOT_OK (противоречие):
- Проект: «Допускается не устанавливать АПС в помещениях категории А по п. 5.2»
  Норма в п. 5.2: «Помещения категории А в обязательном порядке оснащаются АПС»
  → Статус not_ok

NOT_OK (не та тема):
- Проект: «Время эвакуации должно соответствовать п. 7.1»
  Норма в п. 7.1: «Толщина стен противопожарных отсеков должна быть не менее 150 мм»
  → Статус not_ok

NOT_OK (пункта нет или утратил силу):
- Проект ссылается на п. 4, а в переданном тексте нормы п. 4 помечен как «Утратил силу»
  → Статус not_ok

Ответ дай строго в формате JSON без пояснений вне JSON:
{{
    "status": "ok" или "not_ok",
    "explanation": "краткое пояснение (1-3 предложения)"
}}
"""
    
    try:
        client = ollama.Client(host=OLLAMA_URL, timeout=120.0)
        response = client.chat(
            model="gpt-oss:20b",
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            options={'temperature': 0.1, 'num_predict': 2048}
        )
        
        result_text = response['message']['content']
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            try:
                client = ollama.Client(host=OLLAMA_URL, timeout=60.0)
                response = client.chat(
                                        model=NORMS_MODEL,
                                        messages=[{'role': 'user', 'content': prompt}],
                                        stream=False,
                                        options={'temperature': 0.1, 'num_predict': 2048}
                                        )
        
                result_text = response['message']['content']
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    return {"status": "error", "explanation": "Не удалось распарсить ответ LLM"}
            except Exception as e:
                return {"status": "error", "explanation": f"Ошибка LLM: {e}"}
            
    except Exception as e:
        print('Не получилось выполнить запрос к модели, пробуем ещё раз')
        try:
            client = ollama.Client(host=OLLAMA_URL, timeout=60.0)
            response = client.chat(
                model=NORMS_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                stream=False,
                options={'temperature': 0.1, 'num_predict': 2048}
            )
        
            result_text = response['message']['content']
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"status": "error", "explanation": "Не удалось распарсить ответ LLM"}
        except Exception as e:
            return {"status": "error", "explanation": f"Ошибка LLM: {e}"}

def _extract_norm_punkt(norm_text, punkt_value, doc_code, part=None):
    """Извлекает текст конкретного пункта из текста нормы"""
    lines = norm_text.split('\n')
    
    if is_fz_document(doc_code):
        article = punkt_value
        search_patterns = [
            f"Статья {article}",
            f"Статья {article}.",
            f"Статья{article}",
            f"Ст. {article}",
            f"Ст.{article}",
            f"ст. {article}",
        ]
        
        for i, line in enumerate(lines):
            line_clean = line.strip()
            for pattern in search_patterns:
                if line_clean.startswith(pattern):
                    article_text = line
                    
                    # Собираем текст статьи
                    for j in range(i+1, len(lines)):
                        next_line = lines[j].strip()
                        if not next_line:
                            continue
                        
                        if re.match(r'^Статья \d+', next_line) or re.match(r'^Ст\. \d+', next_line):
                            break
                        
                        article_text += '\n' + lines[j]
                    
                    # Если указана часть, пытаемся извлечь только её
                    if part:
                        try:
                            parts_nums = re.findall(r'(\d+)', str(part))
                            if (doc_code=="123-ФЗ")and(punkt_value=="2"):
                                # Статья 2 ФЗ №123 отличается по оформлению
                                parts = re.split(r'(\n[1-9]?[0-9](?:\s+-\s+[1-9]?[0-9])*[\.\)])', article_text)
                            else:
                                parts = re.split(r'(\n[1-9]?[0-9](?:\s+-\s+[1-9]?[0-9])*\.)', article_text)
                            #parts = re.split(r'(\n[1-9]?[0-9]\.)', article_text)
                            parts_nums_extracted = []
                            for part_temp in parts_nums:
                                try:
                                    parts_nums_extracted.append(int(part_temp))
                                except:
                                    return article_text
                            
                            if not parts_nums_extracted:
                                return article_text
                            
                            result = []
                            if parts[0]:
                                result.append(parts[0])
                            for idx in range(1, len(parts)-1, 2):
                                result.append(parts[idx] + parts[idx+1])
                            
                            article_lines = result
                            response = ''
                            for part_num in parts_nums_extracted:
                                for article_line in article_lines:
                                    if part_num < len(article_lines) and str(article_line).strip().startswith(str(part_num)):
                                        response += article_line
                            
                            if response and article_lines[0]:
                                return article_lines[0] + response
                            if response:
                                return response
                            else:
                                return article_text
                        except Exception as e:
                            print(f'Ошибка при извлечении части статьи: {e}')
                            return article_text
                    else:
                        return article_text
        
        return ""
    else:
        STOP_WORDS = ['ЗАРЕГИСТРИРОВАН', 'УТВЕРЖДЕН', 'ВВЕДЕН', 'ВНЕСЕН', 'РАЗРАБОТАН']
        punkt_clean = punkt_value.strip()

        for i, line in enumerate(lines):
            line_clean = line.strip()
            if not line_clean or any(word in line_clean for word in STOP_WORDS):
                continue
            
            if (line_clean.startswith(punkt_clean + ' ') or
                line_clean.startswith(punkt_clean + '.') or
                line_clean.startswith(punkt_clean + '. ') or
                line_clean == punkt_clean or
                line_clean.startswith(punkt_clean + '\xa0')):
                
                punkt_text = line
                
                for j in range(i+1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    
                    if next_line and next_line[0].isdigit():
                        first_part = next_line.split()[0] if next_line.split() else ""
                        first_part_clean = first_part.rstrip('.')
                        if first_part_clean.split('.')[0].isdigit() and first_part_clean.split('.')[0] != punkt_clean:
                            break
                    
                    punkt_text += '\n' + lines[j]
                
                return punkt_text
        
        return ""

def _load_mopb_data(json_file):
    """Загружает данные из JSON-файла MOPB"""
    print(f"ЗАГРУЗКА ДАННЫХ ИЗ {os.path.basename(json_file)}")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"Всего ссылок: {len(data['references'])}")
        return data['doc_code'], data['references']
    except FileNotFoundError:
        print(f"Файл не найден: {json_file}")
        return None, None
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        return None, None

def _find_norm_file(doc_code, norms_folder, doc_file_map):
    """Находит файл нормы по коду документа"""
    if not os.path.exists(norms_folder):
        print(f"Папка {norms_folder} не найдена")
        return None
    
    files = os.listdir(norms_folder)
    search_pattern = doc_file_map.get(doc_code, doc_code)
    
    print(f"\nПоиск файла для {doc_code}...")
    for file in files:
        if search_pattern in file:
            file_path = os.path.join(norms_folder, file)
            print(f"   Найден: {file}")
            return file_path
    
    print(f"   Файл не найден")
    return None

def _read_docx_file(file_path):
    """Читает текст из DOCX-файла"""
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        print(f"Прочитано строк: {len(full_text)}")
        return '\n'.join(full_text)
    except Exception as e:
        print(f"Ошибка чтения DOCX: {e}")
        return ""

def _make_all_errors_file(output_folder):
    """Функция для создания файла со всеми ошибками"""
    not_found_count = 0
    all_errors = []
    all_errors_file = os.path.join(output_folder, 'Все_ошибки.json')
    comparison_folder = os.path.join(output_folder, "MOPB_сравнение")
    if not comparison_folder:
        print('Не удалось найти папку с результатами сравнения')
        return None
    
    for filename in os.listdir(comparison_folder):
        if filename.endswith('.json'):
            filepath = os.path.join(comparison_folder, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for d in data.get('results', ''):
                    if d.get('status', '') and d.get('status', '') != 'ok':
                        if d.get('status', '') == 'not_found':
                            not_found_count += 1
                        d['doc_code'] = data.get('doc_code', '')
                        d['norm_file'] = data.get('norm_file', '')
                        all_errors.append(d)

    with open(all_errors_file, 'w', encoding='utf-8') as f:
        json.dump(all_errors, f, ensure_ascii=False, indent=2)
    
    return all_errors