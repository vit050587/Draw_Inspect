import os
from flask import Flask
from flasgger import Swagger
from dotenv import load_dotenv


SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "AI PD Analyzer API",
        "version": "1.0.0",
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "consumes": ["application/json", "multipart/form-data"],
    "produces": ["application/json"],
    "tags": [
        {"name": "sessions", "description": "Управление сессиями обработки"},
        {"name": "upload", "description": "Загрузка файлов"},
        {"name": "files", "description": "Скачивание результатов"},
    ],
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/fire/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/fire/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/fire/docs",
}


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)

    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "1024")) * 1024 * 1024
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
    app.config["OUTPUT_FOLDER"] = os.getenv("OUTPUT_FOLDER", "outputs")
    app.config["SESSIONS_FILE"] = os.getenv("SESSIONS_FILE", "outputs/sessions.json")
    app.config["PERECHEN_PDF"] = os.getenv("PERECHEN_PDF", "data/Perechen.pdf")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    Swagger(app, template=SWAGGER_TEMPLATE, config=SWAGGER_CONFIG)

    return app
