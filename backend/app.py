from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import uuid
import json
import shutil

# Add parent directory to path for scripts imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.drawing_detector import extract_drawing_pages_to_pdf
from scripts.page_analyzer import analyze_pages
from scripts.response_generator import generate_response
from scripts.element_classifier import classify_elements

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Отдаем файлы из папки data для frontend
@app.route('/data/<path:filename>')
def serve_data(filename):
    # Для class.json используем специальную обработку (файл в формате JSON Lines)
    if filename == 'class.json':
        data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'class.json')
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            # Удаляем пробелы по краям и запятые в конце каждой строки, парсим как JSON Lines
            cleaned_lines = [line.strip().rstrip(',') for line in lines if line.strip()]
            data = [json.loads(line) for line in cleaned_lines]
            return jsonify(data)
        except Exception as e:
            return jsonify({'error': f'Failed to parse class.json: {str(e)}'}), 500
    
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'data'), filename)

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    session_id = str(uuid.uuid4())
    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    os.makedirs(session_folder, exist_ok=True)
    
    # Сохраняем запрос пользователя (будет добавлен позже в /api/analyze)
    request_info_path = os.path.join(session_folder, 'request.json')
    with open(request_info_path, 'w', encoding='utf-8') as f:
        json.dump({'session_id': session_id, 'status': 'files_uploaded'}, f, ensure_ascii=False, indent=2)
    
    saved_paths = []
    for file in files:
        if file.filename:
            filepath = os.path.join(session_folder, file.filename)
            file.save(filepath)
            saved_paths.append(filepath)
    
    # Извлекаем ТОЛЬКО страницы с чертежами из PDF как отдельные PDF файлы
    all_pages = []
    for filepath in saved_paths:
        if filepath.lower().endswith('.pdf'):
            pages = extract_drawing_pages_to_pdf(filepath, session_folder)
            all_pages.extend(pages)
        else:
            # Предполагаем, что это изображение
            all_pages.append({
                'path': filepath,
                'page_num': 1,
                'source_file': os.path.basename(filepath)
            })
    
    # Сохраняем информацию о найденных страницах
    pages_info = {
        'session_id': session_id,
        'total_pages': len(all_pages),
        'pages': all_pages
    }
    
    pages_info_path = os.path.join(session_folder, 'pages_info.json')
    with open(pages_info_path, 'w', encoding='utf-8') as f:
        json.dump(pages_info, f, ensure_ascii=False, indent=2)
    
    return jsonify({
        'session_id': session_id,
        'total_pages': len(all_pages)
    })

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('question')
    
    if not session_id or not question:
        return jsonify({'error': 'Missing session_id or question'}), 400
    
    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    if not os.path.exists(session_folder):
        return jsonify({'error': 'Session not found'}), 404
    
    # Сохраняем вопрос пользователя в request.json
    request_info_path = os.path.join(session_folder, 'request.json')
    with open(request_info_path, 'w', encoding='utf-8') as f:
        json.dump({
            'session_id': session_id,
            'question': question,
            'status': 'analyzing'
        }, f, ensure_ascii=False, indent=2)
    
    # Загружаем информацию о страницах
    pages_info_path = os.path.join(session_folder, 'pages_info.json')
    if not os.path.exists(pages_info_path):
        return jsonify({'error': 'Pages info not found'}), 404
    
    with open(pages_info_path, 'r', encoding='utf-8') as f:
        pages_data = json.load(f)
    
    all_pages = pages_data['pages']
    
    # Анализируем ВСЕ страницы с чертежами
    analysis_results = analyze_pages(all_pages, question, session_folder)
    
    # Сохраняем результаты анализа для последующего использования
    analysis_results_path = os.path.join(session_folder, 'analysis_results.json')
    with open(analysis_results_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)
    
    # Генерируем ответ пользователю - передаем session_folder и question
    response_data = generate_response(session_folder, question)
    
    # Классифицируем найденные элементы по справочнику
    elements_json_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'elements.json')
    classification_result = classify_elements(session_folder, elements_json_path)
    
    # Сохраняем результаты анализа и ответ
    results_path = os.path.join(session_folder, 'results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'question': question,
            'analysis_results': analysis_results,
            'response': response_data,
            'classification': classification_result
        }, f, ensure_ascii=False, indent=2)
    
    # Обновляем статус в request.json
    with open(request_info_path, 'w', encoding='utf-8') as f:
        json.dump({
            'session_id': session_id,
            'question': question,
            'status': 'completed'
        }, f, ensure_ascii=False, indent=2)
    
    # Добавляем информацию о классификации в ответ
    response_data['classification'] = classification_result
    
    return jsonify(response_data)

@app.route('/api/download/<session_id>/<filename>')
def download_file(session_id, filename):
    """Скачивание файлов классификации (Excel, JSON)"""
    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    if not os.path.exists(session_folder):
        return jsonify({'error': 'Session not found'}), 404
    
    file_path = os.path.join(session_folder, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_from_directory(session_folder, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
