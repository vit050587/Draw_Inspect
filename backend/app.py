from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import uuid

# Add parent directory to path for scripts imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.pdf_processor import extract_pages_to_images
from scripts.classifier import classify_drawings
from scripts.vlm_analyzer import analyze_with_vlm
from scripts.llm_responder import generate_response

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
    
    saved_paths = []
    for file in files:
        if file.filename:
            filepath = os.path.join(session_folder, file.filename)
            file.save(filepath)
            saved_paths.append(filepath)
    
    # Extract pages to images
    all_images = []
    for filepath in saved_paths:
        if filepath.lower().endswith('.pdf'):
            images = extract_pages_to_images(filepath, session_folder)
            all_images.extend(images)
        else:
            # Assume it's an image file
            all_images.append({
                'path': filepath,
                'page_num': 1,
                'source_file': os.path.basename(filepath)
            })
    
    # Classify drawings
    classifications = classify_drawings(all_images)
    
    return jsonify({
        'session_id': session_id,
        'total_pages': len(all_images),
        'classifications': classifications
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
    
    # Collect all image paths from session
    image_files = []
    for root, dirs, files in os.walk(session_folder):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, file))
    
    # Analyze with VLM
    vlm_results = analyze_with_vlm(image_files, question)
    
    # Generate structured response with LLM
    response_data = generate_response(vlm_results, question)
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
