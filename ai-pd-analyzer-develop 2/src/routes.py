import io
import json
import os
import zipfile
import pandas as pd
from flask import (
    Blueprint, current_app, request,
    send_file, send_from_directory,
    jsonify
)
from werkzeug.utils import secure_filename
from .services.session_manager import SessionManager
from .schemas import (
    HealthResponse, ErrorResponse,
    SessionListResponse, SessionFull, SessionStatus,
    UploadFirstResponse, UploadSecondResponse,
    RestoreResponse, DeleteResponse, SessionFile,
)

bp = Blueprint("main", __name__, url_prefix="/fire")

_manager: SessionManager | None = None


def _get_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager(
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            output_folder=current_app.config["OUTPUT_FOLDER"],
            sessions_file=current_app.config["SESSIONS_FILE"],
            perechen_pdf='data/Perechen.xlsx',
        )
    return _manager


def _ok(schema_instance):
    from flask import Response
    return Response(
        schema_instance.model_dump_json(exclude_none=False, by_alias=True),
        status=200,
        mimetype="application/json",
    )


def _err(schema_instance, status: int):
    from flask import Response
    return Response(
        schema_instance.model_dump_json(by_alias=True),
        status=status,
        mimetype="application/json",
    )


# ------- HTML -------

@bp.route("/", methods=["GET"])
def index():
    from flask import render_template
    return render_template("index.html")


# ------- API -------

@bp.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """
    Список всех сессий обработки.
    ---
    tags:
      - sessions
    responses:
      200:
        description: Массив сессий
        schema:
          type: object
          properties:
            sessions:
              type: array
              items:
                $ref: '#/definitions/SessionFull'
    definitions:
      SessionFile:
        type: object
        properties:
          path:
            type: string
          filename:
            type: string
          size:
            type: integer
          downloadUrl:
            type: string
      SessionFull:
        type: object
        properties:
          sessionId:
            type: string
          createdAt:
            type: string
          status:
            type: string
          firstFileName:
            type: string
          secondFileName:
            type: string
          extractedDate:
            type: string
          files:
            type: array
            items:
              $ref: '#/definitions/SessionFile'
          error:
            type: string
    """
    raw = _get_manager().list_sessions()
    sessions = [SessionFull(**s) for s in raw]
    return _ok(SessionListResponse(sessions=sessions))


@bp.route("/api/upload_first", methods=["POST"])
def api_upload_first():
    """
    Загрузка и обработка ГПЗУ (первый документ).
    ---
    tags:
      - upload
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: PDF-файл ГПЗУ
    responses:
      200:
        description: Файл принят, сессия создана
        schema:
          type: object
          properties:
            sessionId:
              type: string
              example: "3fa85f64-5717-4562-b3fc-2c963f66afa6"
            extractedDate:
              type: string
              example: "2023-01-15"
            status:
              type: string
              example: processing_norms
            message:
              type: string
      400:
        description: Ошибка валидации запроса
        schema:
          type: object
          properties:
            detail:
              type: string
      500:
        description: Ошибка обработки файла
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    if "file" not in request.files:
        return _err(ErrorResponse(detail="Файл не передан"), 400)
    f = request.files["file"]
    if not f.filename:
        return _err(ErrorResponse(detail="Пустое имя файла"), 400)

    filename = secure_filename(f.filename) or "gpzu.pdf"
    saved_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    base, ext = os.path.splitext(saved_path)
    i = 0
    while os.path.exists(saved_path):
        i += 1
        saved_path = f"{base}_{i}{ext}"
    f.save(saved_path)

    try:
        result = _get_manager().start_first(original_name=f.filename, saved_path=saved_path)
    except Exception as exc:
        return _err(ErrorResponse(detail=f"Ошибка обработки ГПЗУ: {exc}"), 500)
    return _ok(UploadFirstResponse(**result))


@bp.route("/api/upload_second", methods=["POST"])
def api_upload_second():
    """
    Загрузка и обработка МОРВ (второй документ).
    ---
    tags:
      - upload
    consumes:
      - multipart/form-data
    parameters:
      - name: sessionId
        in: query
        type: string
        required: true
        description: ID сессии, полученный при загрузке ГПЗУ
      - name: file
        in: formData
        type: file
        required: true
        description: PDF-файл МОРВ
    responses:
      200:
        description: Файл принят, обработка запущена
        schema:
          type: object
          properties:
            sessionId:
              type: string
            status:
              type: string
              example: processing_second
      400:
        description: Ошибка валидации или неверный статус сессии
        schema:
          type: object
          properties:
            detail:
              type: string
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    sessionId = request.args.get("sessionId")
    if not sessionId:
        return _err(ErrorResponse(detail="sessionId обязателен"), 400)
    if "file" not in request.files:
        return _err(ErrorResponse(detail="Файл не передан"), 400)

    f = request.files["file"]
    if not f.filename:
        return _err(ErrorResponse(detail="Пустое имя файла"), 400)

    filename = secure_filename(f.filename) or "mopb.pdf"
    saved_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"], f"{sessionId}_{filename}"
    )
    f.save(saved_path)

    try:
        result = _get_manager().start_second(
            sessionId, original_name=f.filename, saved_path=saved_path
        )
    except KeyError:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    except Exception as exc:
        return _err(ErrorResponse(detail=str(exc)), 400)
    return _ok(UploadSecondResponse(**result))


@bp.route("/api/session/<sessionId>/status", methods=["GET"])
def api_status(sessionId: str):
    """
    Краткий статус сессии.
    ---
    tags:
      - sessions
    parameters:
      - name: sessionId
        in: path
        type: string
        required: true
        description: ID сессии
    responses:
      200:
        description: Статус сессии
        schema:
          type: object
          properties:
            sessionId:
              type: string
            status:
              type: string
              enum:
                - dates_found
                - manual_date_needed
                - processing_norms
                - awaiting_second
                - processing_second
                - stu_required
                - completed
                - error
            extractedDate:
              type: string
            error:
              type: string
            progress:
              type: number
            progress_message:
              type: string
            stu_required:
              type: boolean
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    s = _get_manager().get(sessionId)
    if not s:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    
    return jsonify({
        "sessionId": s["sessionId"],
        "status": s["status"],
        "extracted_date": s.get("extracted_date"),
        "error": s.get("error"),
        "progress": s.get("progress", 0),
        "progress_message": s.get("progress_message", ""),
        "stu_required": s.get("status") == "stu_required"
    })


@bp.route("/api/session/<sessionId>", methods=["GET"])
def api_session(sessionId: str):
    """
    Полные данные сессии.
    ---
    tags:
      - sessions
    parameters:
      - name: sessionId
        in: path
        type: string
        required: true
        description: ID сессии
    responses:
      200:
        description: Данные сессии
        schema:
          $ref: '#/definitions/SessionFull'
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    s = _get_manager().get(sessionId)
    if not s:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    return _ok(SessionFull(**s))


@bp.route("/api/session/<sessionId>", methods=["DELETE"])
def api_delete_session(sessionId: str):
    """
    Удаление сессии и всех связанных файлов.
    ---
    tags:
      - sessions
    parameters:
      - name: sessionId
        in: path
        type: string
        required: true
        description: ID сессии
    responses:
      200:
        description: Сессия удалена
        schema:
          type: object
          properties:
            deleted:
              type: boolean
              example: true
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    ok = _get_manager().delete(sessionId)
    if not ok:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    return _ok(DeleteResponse(deleted=True))


@bp.route("/api/session/<sessionId>/restore", methods=["POST"])
def api_restore_session(sessionId: str):
    """
    Восстановить базовую информацию о сессии (для переподключения фронтенда).
    ---
    tags:
      - sessions
    parameters:
      - name: sessionId
        in: path
        type: string
        required: true
        description: ID сессии
    responses:
      200:
        description: Базовая информация о сессии
        schema:
          type: object
          properties:
            sessionId:
              type: string
            extractedDate:
              type: string
            firstFileName:
              type: string
            status:
              type: string
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    try:
        result = _get_manager().restore(sessionId)
    except KeyError:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    return _ok(RestoreResponse(**result))


@bp.route("/api/session/<sessionId>/download/<path:filename>", methods=["GET"])
def api_download_file(sessionId: str, filename: str):
    """
    Скачать конкретный файл результата из сессии.
    ---
    tags:
      - files
    parameters:
      - name: sessionId
        in: path
        type: string
        required: true
        description: ID сессии
      - name: filename
        in: path
        type: string
        required: true
        description: Имя файла
    produces:
      - application/octet-stream
    responses:
      200:
        description: Файл для скачивания
      404:
        description: Файл не найден
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    path = _get_manager().file_path(sessionId, filename)
    if not path or not os.path.exists(path):
        return _err(ErrorResponse(detail="Файл не найден"), 404)
    directory, name = os.path.split(path)
    return send_from_directory(directory, name, as_attachment=True)

@bp.route('/api/confirm_date', methods=['POST'])
def confirm_date():
    """Подтверждение выбранной или введённой вручную даты."""
    try:
        session_id = request.form.get('sessionId')
        selected_date = request.form.get('selected_date')
        
        if not session_id:
            return jsonify({"detail": "sessionId обязателен"}), 400
        if not selected_date:
            return jsonify({"detail": "selected_date обязателен"}), 400
        
        result = _get_manager().confirm_date(session_id, selected_date)
        return jsonify(result)
    except KeyError as e:
        return jsonify({"detail": str(e)}), 404
    except RuntimeError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        return jsonify({"detail": str(e)}), 500


def _json_to_table(data) -> tuple[list, list]:
    """Конвертирует JSON-данные в (headers, rows) для предпросмотра."""

    # Формат все_СП_результаты.json: {"results": {"КодДок": {...}, ...}, ...}
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], dict):
        top_info = {k: v for k, v in data.items() if k != "results"}
        rows_out = []
        for doc_code, doc_info in data["results"].items():
            row = {"Код документа": doc_code}
            if isinstance(doc_info, dict):
                row.update(doc_info)
            else:
                row["Значение"] = str(doc_info)
            if top_info:
                row.update({f"[{k}]": str(v) for k, v in top_info.items()})
            rows_out.append(row)
        df = pd.DataFrame(rows_out).fillna("")
        return df.columns.tolist(), df.astype(str).values.tolist()

    # Формат MOPB_сравнение/*.json: {"results": [...], ...}
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
        top_fields = {k: v for k, v in data.items() if k != "results"}
        rows_out = []
        for item in data["results"]:
            row = dict(top_fields)
            if isinstance(item, dict):
                # Вложенные списки (fz_references, norm_texts) сворачиваем в строку
                for k, v in item.items():
                    if isinstance(v, (list, dict)):
                        row[k] = json.dumps(v, ensure_ascii=False)
                    else:
                        row[k] = v
            else:
                row["значение"] = str(item)
            rows_out.append(row)
        df = pd.DataFrame(rows_out).fillna("")
        return df.columns.tolist(), df.astype(str).values.tolist()

    # Список объектов
    if isinstance(data, list) and data and isinstance(data[0], dict):
        df = pd.DataFrame(data).fillna("")
        for col in df.columns:
            df[col] = df[col].apply(
                lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            )
        return df.columns.tolist(), df.astype(str).values.tolist()

    # Плоский список
    if isinstance(data, list):
        return ["значение"], [[str(v)] for v in data]

    # Произвольный dict — одна строка
    if isinstance(data, dict):
        headers = list(data.keys())
        row = [json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)
               for v in data.values()]
        return headers, [row]

    return ["данные"], [[str(data)]]


@bp.route("/api/session/<session_id>/preview/<path:filename>", methods=["GET"])
def api_preview_file(session_id: str, filename: str):
    """
    Предпросмотр содержимого xlsx/csv/json файла в формате JSON.
    ---
    tags:
      - files
    parameters:
      - name: session_id
        in: path
        type: string
        required: true
        description: ID сессии
      - name: filename
        in: path
        type: string
        required: true
        description: Имя файла
    responses:
      200:
        description: Содержимое файла
        schema:
          type: object
          properties:
            filename:
              type: string
            headers:
              type: array
              items:
                type: string
            rows:
              type: array
              items:
                type: array
                items:
                  type: string
      404:
        description: Файл не найден
        schema:
          type: object
          properties:
            detail:
              type: string
      400:
        description: Формат не поддерживается
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    path = _get_manager().file_path(session_id, filename)
    if not path or not os.path.exists(path):
        return _err(ErrorResponse(detail="Файл не найден"), 404)

    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".xlsx", ".xls", ".csv", ".json"):
        return _err(ErrorResponse(detail="Предпросмотр доступен только для xlsx/csv/json"), 400)

    try:
        if ext == ".csv":
            df = pd.read_csv(path)
            df = df.fillna("")
            headers = df.columns.tolist()
            rows = df.astype(str).values.tolist()

        elif ext == ".json":
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            headers, rows = _json_to_table(data)

        else:
            df = pd.read_excel(path)
            df = df.fillna("")
            headers = df.columns.tolist()
            rows = df.astype(str).values.tolist()

    except Exception as exc:
        return _err(ErrorResponse(detail=f"Не удалось прочитать файл: {exc}"), 400)

    from flask import Response
    payload = json.dumps(
        {"filename": filename, "headers": headers, "rows": rows},
        ensure_ascii=False,
    )
    return Response(payload, status=200, mimetype="application/json")


@bp.route("/api/session/<sessionId>/download-all", methods=["GET"])
def api_download_all(sessionId: str):
    """
    Скачать все файлы результатов сессии одним ZIP-архивом.
    ---
    tags:
      - files
    parameters:
      - name: sessionId
        in: path
        type: string
        required: true
        description: ID сессии
    produces:
      - application/zip
    responses:
      200:
        description: ZIP-архив со всеми файлами сессии
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    s = _get_manager().get(sessionId)
    if not s:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in s.get("files", []):
            if os.path.exists(f["path"]):
                zf.write(f["path"], arcname=f["filename"])
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"session_{sessionId[:8]}.zip",
    )

@bp.route("/api/upload_stu", methods=["POST"])
def api_upload_stu():
    """
    Загрузить файл СТУ (Специальные Технические Условия) и продолжить обработку.
    ---
    tags:
      - upload
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: PDF-файл СТУ
      - name: sessionId
        in: formData
        type: string
        required: true
        description: ID сессии
    responses:
      200:
        description: Файл СТУ загружен, обработка продолжена
        schema:
          type: object
          properties:
            status:
              type: string
              example: processing_second
            continue_processing:
              type: boolean
              example: true
      400:
        description: Ошибка валидации или неверный статус сессии
        schema:
          type: object
          properties:
            detail:
              type: string
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    if "file" not in request.files:
        return _err(ErrorResponse(detail="Файл не передан"), 400)
    
    f = request.files["file"]
    if not f.filename:
        return _err(ErrorResponse(detail="Пустое имя файла"), 400)
    
    sessionId = request.form.get("sessionId")
    if not sessionId:
        return _err(ErrorResponse(detail="sessionId обязателен"), 400)
    
    if not f.filename.lower().endswith('.docx'):
        return _err(ErrorResponse(detail="Принимаются только DOCX файлы"), 400)
    
    # Сохраняем временно для передачи в менеджер
    filename = secure_filename(f.filename) or "stu.docx"
    saved_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"], f"stu_{sessionId}_{filename}"
    )
    base, ext = os.path.splitext(saved_path)
    i = 0
    while os.path.exists(saved_path):
        i += 1
        saved_path = f"{base}_{i}{ext}"
    f.save(saved_path)
    
    try:
        result = _get_manager().upload_stu(sessionId, saved_path)
    except KeyError:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    except RuntimeError as e:
        return _err(ErrorResponse(detail=str(e)), 400)
    except Exception as exc:
        return _err(ErrorResponse(detail=f"Ошибка загрузки СТУ: {exc}"), 500)
    
    return _ok(UploadSecondResponse(**result))


@bp.route("/api/skip_stu", methods=["POST"])
def api_skip_stu():
    """
    Пропустить загрузку СТУ и продолжить обработку.
    ---
    tags:
      - sessions
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            sessionId:
              type: string
              description: ID сессии
    responses:
      200:
        description: СТУ пропущен, обработка продолжена
        schema:
          type: object
          properties:
            status:
              type: string
              example: processing_second
            continue_processing:
              type: boolean
              example: true
      400:
        description: Ошибка валидации или неверный статус сессии
        schema:
          type: object
          properties:
            detail:
              type: string
      404:
        description: Сессия не найдена
        schema:
          type: object
          properties:
            detail:
              type: string
    """
    data = request.get_json(silent=True)
    if not data:
        return _err(ErrorResponse(detail="Тело запроса должно быть JSON"), 400)
    
    sessionId = data.get("sessionId")
    if not sessionId:
        return _err(ErrorResponse(detail="sessionId обязателен"), 400)
    
    try:
        result = _get_manager().skip_stu(sessionId)
    except KeyError:
        return _err(ErrorResponse(detail="Сессия не найдена"), 404)
    except RuntimeError as e:
        return _err(ErrorResponse(detail=str(e)), 400)
    except Exception as exc:
        return _err(ErrorResponse(detail=f"Ошибка: {exc}"), 500)
    
    return _ok(UploadSecondResponse(**result))
