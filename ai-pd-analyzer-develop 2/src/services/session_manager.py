from __future__ import annotations
import json
import os
import shutil
import threading
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import re

from .gpuz import findDateInGPZU, save_selected_date
from .norms_actualizer import searchActualNorm, copyActualNorm
from .mopb_extractor import searchМОРВ, _check_stu
from .reference_parser import punktМОРВ
from .comparison import comparisionМОРВ, _make_all_errors_file
from .json_saver import process_complex_json_to_xlsx, json_to_excel_all_docs, _process_all_errors_file


class SessionManager:
    """Управление сессиями обработки ГПЗУ/МОРВ."""

    def __init__(
        self,
        upload_folder: str,
        output_folder: str,
        sessions_file: str,
        perechen_pdf: str,
        max_concurrent_tasks: int = 5,  # Максимум одновременных обработок
    ):
        self.upload_folder = upload_folder
        self.output_folder = output_folder
        self.sessions_file = sessions_file
        self.perechen_pdf = perechen_pdf
        self.max_concurrent_tasks = max_concurrent_tasks
        
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._state_lock = threading.Lock()
        
        # Семафор для ограничения количества одновременных задач
        self._task_semaphore = threading.Semaphore(max_concurrent_tasks)
        
        # Отдельные события для каждой сессии (для потокобезопасности)
        self._session_locks: Dict[str, threading.Lock] = {}
        
        self._load()

    # ----- персистентность -----
    def _load(self) -> None:
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    self._sessions = json.load(f)
            except Exception:
                self._sessions = {}

    def _save(self) -> None:
        """Сохранение с защитой"""
        import time
        
        os.makedirs(os.path.dirname(self.sessions_file) or ".", exist_ok=True)
        
        for attempt in range(5):
            try:
                # Пишем напрямую, без временных файлов
                with open(self.sessions_file, "w", encoding="utf-8") as f:
                    json.dump(self._sessions, f, ensure_ascii=False, indent=2)
                break
            except PermissionError:
                if attempt < 5:
                    time.sleep(0.2)
            except Exception as e:
                print(f"Ошибка сохранения sessions.json: {e}")
                break

    def _get_session_lock(self, sessionId: str) -> threading.Lock:
        """Получить или создать блокировку для конкретной сессии"""
        with self._state_lock:
            if sessionId not in self._session_locks:
                self._session_locks[sessionId] = threading.Lock()
            return self._session_locks[sessionId]

    # ----- базовые операции -----
    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._state_lock:
            items = [dict(s) for s in self._sessions.values()]
        items_correct = []
        for item in items:
            if item.get('sessionId', ''):
                items_correct.append(item)
        items_correct.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        for s in items_correct:
            self._decorate_files(s)
        return items_correct

    def get(self, sessionId: str) -> Optional[Dict[str, Any]]:
        with self._state_lock:
            s = self._sessions.get(sessionId)
            if not s:
                return None
            s = dict(s)
        self._decorate_files(s)
        return s

    def _update(self, sessionId: str, **fields: Any) -> None:
        with self._state_lock:
            s = self._sessions.setdefault(sessionId, {})
            s.update(fields)
            self._save()

    def delete(self, sessionId: str) -> bool:
        # Сначала удаляем из памяти
        with self._state_lock:
            s = self._sessions.pop(sessionId, None)
            if not s:
                return False
            # Удаляем блокировку сессии
            self._session_locks.pop(sessionId, None)
            self._save()

        # Потом удаляем файлы (без блокировки)
        session_dir = os.path.join(self.output_folder, sessionId)
        if os.path.isdir(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
        for p in (s.get("first_file_path"), s.get("second_file_path")):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        return True

    # ----- создание файлов и запуск обработки -----
    def start_first(self, original_name: str, saved_path: str) -> Dict[str, Any]:
        """Запускает обработку ГПЗУ: поиск всех дат."""
        sessionId = str(uuid.uuid4())
        session = {
            "sessionId": sessionId,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "dates_found",  
            "first_file_name": original_name,
            "first_file_path": saved_path,
            "second_file_name": None,
            "second_file_path": None,
            "extracted_date": None,
            "dates_info": None, 
            "files": [],
            "error": None,
            "progress": 0,
            "progress_message": "",
        }
        with self._state_lock:
            self._sessions[sessionId] = session
            self._save()

        # Извлекаем все даты (это быстро, можно синхронно)
        try:
            dates_result = findDateInGPZU(saved_path)
        except Exception as exc:
            self._update(sessionId, status="error", error=f"GPZU: {exc}")
            raise
        
        # Сохраняем информацию о датах
        self._update(
            sessionId,
            dates_info=dates_result,
            status="dates_found"
        )

        return {
            "sessionId": sessionId,
            "dates_info": dates_result,
            "status": "dates_found",
            "message": f"Найдено дат: {len(dates_result['dates'])}. Выберите нужную.",
        }

    def confirm_date(self, sessionId: str, selected_date: str) -> Dict[str, Any]:
        """Пользователь выбрал дату, запускаем актуализацию норм."""
        with self._state_lock:
            s = self._sessions.get(sessionId)
            if not s:
                raise KeyError("Сессия не найдена")
            if s["status"] not in ("dates_found", "manual_date_needed"):
                raise RuntimeError(f"Неверный статус: {s['status']}")
            
            s["extracted_date"] = selected_date
            s["status"] = "processing_norms"
            s["progress"] = 0
            s["progress_message"] = "Запуск актуализации норм..."
            self._save()
        
        # Сохраняем выбранную дату
        session_dir = os.path.join(self.output_folder, sessionId)
        os.makedirs(session_dir, exist_ok=True)
        save_selected_date(selected_date, output_folder=session_dir)
        
        # Запускаем фоновую актуализацию норм (без глобальной блокировки)
        threading.Thread(
            target=self._process_norms_bg,
            args=(sessionId, selected_date),
            daemon=True,
        ).start()
        
        return {
            "sessionId": sessionId,
            "extracted_date": selected_date,
            "status": "processing_norms",
            "message": "Дата подтверждена. Начинаем актуализацию норм…",
        }

    def start_second(
        self, sessionId: str, original_name: str, saved_path: str
    ) -> Dict[str, Any]:
        """Запускает фоновую обработку проектной документации."""
        with self._state_lock:
            s = self._sessions.get(sessionId)
            if not s:
                raise KeyError("Сессия не найдена")
            if s["status"] != "awaiting_second":
                raise RuntimeError(
                    f"Сессия в статусе '{s['status']}' - нельзя начать обработку МОРВ"
                )
            s["second_file_name"] = original_name
            s["second_file_path"] = saved_path
            s["status"] = "processing_second"
            s["progress"] = 0
            s["progress_message"] = "Запуск обработки проекта..."
            self._save()

        threading.Thread(
            target=self._process_mopb_bg,
            args=(sessionId, saved_path),
            daemon=True,
        ).start()

        return {"sessionId": sessionId, "status": "processing_second"}

    def restore(self, sessionId: str) -> Dict[str, Any]:
        s = self.get(sessionId)
        if not s:
            raise KeyError("Сессия не найдена")
        return {
            "sessionId": s["sessionId"],
            "extracted_date": s.get("extracted_date"),
            "first_file_name": s.get("first_file_name"),
            "status": s.get("status"),
        }

    # ----- фоновые задачи (БЕЗ глобальной блокировки) -----
    def _process_norms_bg(self, sessionId: str, extracted_date: str) -> None:
        """Фоновая актуализация норм (может выполняться параллельно)"""
        # Ждём семафор (ограничение количества одновременных задач)
        acquired = self._task_semaphore.acquire(timeout=30)
        if not acquired:
            self._update(sessionId, status="error", error="Слишком много задач, попробуйте позже")
            return
        
        try:
            session_dir = os.path.join(self.output_folder, sessionId)
            
            self._update_progress(sessionId, 10, "Поиск актуальных норм...")
            searchActualNorm(
                target_date=extracted_date, 
                normsList=self.perechen_pdf,
                output_folder=session_dir
            )
            
            self._update_progress(sessionId, 50, "Копирование норм...")
            os.makedirs(session_dir, exist_ok=True)
            copyActualNorm(session_dir)
            
            self._update_progress(sessionId, 80, "Формирование Excel...")
            json_to_excel_all_docs(
                os.path.join(session_dir, "все_СП_результаты.json"), 
                os.path.join(session_dir, "все_СП_результаты.xlsx")
            )
            
            norms_result = "все_СП_результаты.xlsx"
            dest = os.path.join(session_dir, norms_result)
            if os.path.exists(dest):
                with self._state_lock:
                    self._sessions[sessionId].setdefault("files", []).append({
                        "path": dest,
                        "filename": norms_result,
                        "size": os.path.getsize(dest),
                    })
                    self._save()

            self._update(sessionId, status="awaiting_second", progress=100)
            
        except Exception as exc:
            traceback.print_exc()
            self._update(sessionId, status="error", error=str(exc))
        finally:
            self._task_semaphore.release()

    def _process_mopb_bg(self, sessionId: str, mopb_path: str) -> None:
        """Фоновая обработка МОРВ (может выполняться параллельно)"""
        acquired = self._task_semaphore.acquire(timeout=30)
        if not acquired:
            self._update(sessionId, status="error", error="Слишком много задач, попробуйте позже")
            return
        
        session_dir = os.path.join(self.output_folder, sessionId)
        
        try:
            session_lock = self._get_session_lock(sessionId)
            
            # Этап 1: Извлечение текста (0-30%)
            self._update_progress(sessionId, 0, "Начало извлечения текста из PDF...")
            searchМОРВ(
                MOPB_PDF=mopb_path,
                progress_callback=lambda p, msg: self._update_progress(
                    sessionId, 
                    int(p * 30),
                    f"Извлечение текста: {msg}"
                ),
                output_folder=session_dir
            )
            
            # Этап 2: Разбор пунктов (30-60%)
            self._update_progress(sessionId, 30, "Разбор пунктов документации...")
            punktМОРВ(
                progress_callback=lambda p, msg: self._update_progress(
                    sessionId,
                    30 + int(p * 30),
                    f"Анализ пунктов: {msg}"
                ),
                output_folder=session_dir
            )
            
            stu_flag = _check_stu(input_folder=session_dir)
            
            # Если обнаружены СТУ - приостанавливаем обработку
            if stu_flag:
                self._update(
                    sessionId, 
                    status="stu_required", 
                    progress=60,
                    progress_message="Обнаружены СТУ, требуется загрузка файла"
                )
                return  # Приостанавливаем обработку
            
            # Если СТУ нет - продолжаем обработку
            self._continue_mopb_processing(sessionId, session_dir)
            
        except Exception as exc:
            traceback.print_exc()
            self._update(sessionId, status="error", error=str(exc))
        finally:
            self._task_semaphore.release()

    def _continue_mopb_processing(self, sessionId: str, session_dir: str) -> None:
        """Продолжение обработки МОРВ после проверки СТУ"""

        stu_flag = _check_stu(input_folder=session_dir)
        try:
            # Этап 3: Сравнение с нормами (60-90%)
            self._update_progress(sessionId, 60, "Сравнение с нормативной базой...")
            comparisionМОРВ(
                progress_callback=lambda p, msg: self._update_progress(
                    sessionId,
                    60 + int(p * 30),
                    f"Сравнение: {msg}"
                ),
                output_folder=session_dir
            )
            
            # Этап 4: Сохранение результатов (90-100%)
            self._update_progress(sessionId, 90, "Формирование файлов результатов...")
            
            os.makedirs(session_dir, exist_ok=True)
            
            new_files = []
            
            _make_all_errors_file(session_dir)
            file_path = _process_all_errors_file(session_dir)
            new_files.append({
                "path": file_path,
                "filename": os.path.basename(file_path),
                "size": os.path.getsize(file_path),
            })
            
            for file_path in process_complex_json_to_xlsx(
                os.path.join(session_dir, "MOPB_сравнение"), session_dir
            ):
                new_files.append({
                    "path": file_path,
                    "filename": os.path.basename(file_path),
                    "size": os.path.getsize(file_path),
                })
            
            new_files_sorted = sorted(new_files, key=self.get_sort_key)
            
            self._update_progress(sessionId, 98, "Сортировка и финализация...")
            
            with self._state_lock:
                files = self._sessions[sessionId].setdefault("files", [])
                existing = {f["filename"] for f in files}
                for f in new_files_sorted:
                    if f["filename"] not in existing:
                        files.append(f)
                self._sessions[sessionId]["status"] = "completed"
                self._sessions[sessionId]["progress"] = 100
                self._save()
                
        except Exception as exc:
            traceback.print_exc()
            self._update(sessionId, status="error", error=str(exc))

    def upload_stu(self, sessionId: str, file_path: str) -> Dict[str, Any]:
        """Загрузка файла СТУ и продолжение обработки"""
        with self._state_lock:
            s = self._sessions.get(sessionId)
            if not s:
                raise KeyError("Сессия не найдена")
            if s["status"] != "stu_required":
                raise RuntimeError(f"Неверный статус для загрузки СТУ: {s['status']}")
            
            s["status"] = "processing_second"
            s["progress"] = 60
            s["progress_message"] = "СТУ загружен, продолжаем обработку..."
            self._save()
        
        session_dir = os.path.join(self.output_folder, sessionId)
        actual_norms_dir = os.path.join(session_dir, "Актуальные_нормы")
        os.makedirs(actual_norms_dir, exist_ok=True)
        
        # Копируем файл СТУ в папку с актуальными нормами
        stu_filename = "Специальные технические условия - " + os.path.basename(file_path)
        stu_dest = os.path.join(actual_norms_dir, stu_filename)
        shutil.copy2(file_path, stu_dest)
        
        # Запускаем продолжение обработки в фоне
        threading.Thread(
            target=self._continue_mopb_processing,
            args=(sessionId, session_dir),
            daemon=True,
        ).start()
        
        return {
            "sessionId": sessionId,  
            "status": "processing_second", 
            "continue_processing": True
    }

    def skip_stu(self, sessionId: str) -> Dict[str, Any]:
        """Пропуск загрузки СТУ и продолжение обработки"""
        with self._state_lock:
            s = self._sessions.get(sessionId)
            if not s:
                raise KeyError("Сессия не найдена")
            if s["status"] != "stu_required":
                raise RuntimeError(f"Неверный статус для пропуска СТУ: {s['status']}")
            
            s["status"] = "processing_second"
            s["progress"] = 60
            s["progress_message"] = "СТУ пропущен, продолжаем обработку..."
            self._save()
        
        session_dir = os.path.join(self.output_folder, sessionId)
        
        # Запускаем продолжение обработки в фоне
        threading.Thread(
            target=self._continue_mopb_processing,
            args=(sessionId, session_dir),
            daemon=True,
        ).start()
        
        return {
            "sessionId": sessionId, 
            "status": "processing_second", 
            "continue_processing": True
        }


    # ----- утилиты -----
    def _decorate_files(self, session: Dict[str, Any]) -> None:
        """Добавляет download_url каждому файлу для фронтенда."""
        sid = session.get("sessionId")
        for f in session.get("files", []):
            f["download_url"] = f"/fire/api/session/{sid}/download/{f['filename']}"

    def file_path(self, sessionId: str, filename: str) -> Optional[str]:
        s = self.get(sessionId)
        if not s:
            return None
        for f in s.get("files", []):
            if f["filename"] == filename:
                return f["path"]
        return None

    def session_dir(self, sessionId: str) -> str:
        return os.path.join(self.output_folder, sessionId)
    
    def _update_progress(self, sessionId: str, progress: int, message: str) -> None:
        """Обновление прогресса обработки (потокобезопасно)"""
        with self._state_lock:
            if sessionId in self._sessions:
                self._sessions[sessionId]["progress"] = progress
                self._sessions[sessionId]["progress_message"] = message
                self._save()

    def natural_sort_key(self, text):
        """Преобразует строку в кортеж для натуральной сортировки"""
        parts = re.split(r'(\d+)', text)
        key = []
        for part in parts:
            if part.isdigit():
                key.append(int(part))
            else:
                key.append(part)
        return tuple(key)

    def get_sort_key(self, item):
        filename = item["filename"]
        type_priority = {"Все": 0, "ФЗ": 1, "СП": 2, "ГОСТ": 3, "ПП": 4}
        
        if "_ФЗ" in filename:
            return (type_priority["ФЗ"], self.natural_sort_key(filename))
        elif filename.startswith("СП"):
            return (type_priority["СП"], self.natural_sort_key(filename))
        elif filename.startswith("ГОСТ"):
            return (type_priority["ГОСТ"], self.natural_sort_key(filename))
        elif filename.startswith("ПП"):
            return (type_priority["ПП"], self.natural_sort_key(filename))
        elif filename.startswith("Все"):
            return (type_priority["Все"], self.natural_sort_key(filename))
        else:
            return (999, self.natural_sort_key(filename))