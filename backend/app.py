from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import uuid
import json
import shutil

# Add parent directory to path for scripts imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.drawing_detector import extract_all_pages_to_pdf
from scripts.drawing_classifier import classify_drawings, get_relevant_categories_for_question
from scripts.page_analyzer import analyze_pages
from scripts.response_generator import generate_response

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    
    # Извлекаем все страницы из PDF как отдельные PDF файлы
    all_pages = []
    for filepath in saved_paths:
        if filepath.lower().endswith('.pdf'):
            pages = extract_all_pages_to_pdf(filepath, session_folder)
            all_pages.extend(pages)
        else:
            # Предполагаем, что это изображение
            all_pages.append({
                'path': filepath,
                'page_num': 1,
                'source_file': os.path.basename(filepath)
            })
    
    # Классифицируем чертежи и распределяем по папкам
    classifications = classify_drawings(all_pages, session_folder)
    
    # Сохраняем информацию о классификации
    classification_info = {
        'session_id': session_id,
        'total_pages': len(all_pages),
        'classifications': classifications
    }
    
    classification_path = os.path.join(session_folder, 'classifications.json')
    with open(classification_path, 'w', encoding='utf-8') as f:
        json.dump(classification_info, f, ensure_ascii=False, indent=2)
    
    return jsonify({
        'session_id': session_id,
        'total_pages': len(all_pages),
        'classifications': {cat: len(imgs) for cat, imgs in classifications.items()}
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
    
    # Загружаем информацию о классификации
    classification_path = os.path.join(session_folder, 'classifications.json')
    if not os.path.exists(classification_path):
        return jsonify({'error': 'Classifications not found'}), 404
    
    with open(classification_path, 'r', encoding='utf-8') as f:
        classification_data = json.load(f)
    
    classifications = classification_data['classifications']
    
    # Определяем релевантные категории для вопроса
    relevant_categories = get_relevant_categories_for_question(question)
    
    # Собираем изображения из релевантных категорий
    images_to_analyze = []
    for category in relevant_categories:
        if category in classifications:
            images_to_analyze.extend(classifications[category])
    
    # Если нет релевантных изображений, берем все
    if not images_to_analyze:
        for category, images in classifications.items():
            images_to_analyze.extend(images)
    
    # Анализируем страницы с использованием gemma4:31b
    analysis_results = analyze_pages(images_to_analyze, question, session_folder)
    
    # Генерируем ответ пользователю
    response_data = generate_response(analysis_results, question)
    
    # Сохраняем результаты анализа и ответ
    results_path = os.path.join(session_folder, 'results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'question': question,
            'relevant_categories': relevant_categories,
            'analysis_results': analysis_results,
            'response': response_data
        }, f, ensure_ascii=False, indent=2)
    
    # Обновляем статус в request.json
    with open(request_info_path, 'w', encoding='utf-8') as f:
        json.dump({
            'session_id': session_id,
            'question': question,
            'status': 'completed'
        }, f, ensure_ascii=False, indent=2)
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
