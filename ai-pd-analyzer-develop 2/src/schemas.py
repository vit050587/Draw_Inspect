from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ErrorResponse(CamelModel):
    detail: str


class HealthResponse(CamelModel):
    status: str


# ---------- файлы сессии ----------

class SessionFile(CamelModel):
    path: str
    filename: str
    size: int
    download_url: str


# ---------- сессия ----------

class SessionStatus(CamelModel):
    sessionId: str
    status: str
    extracted_date: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[int] = None
    progress_message: Optional[str] = None
    stu_required: Optional[bool] = Field(None, alias="stuRequired")


class SessionFull(CamelModel):
    sessionId: str
    created_at: Optional[str] = None
    status: str
    first_file_name: Optional[str] = None
    first_file_path: Optional[str] = None
    second_file_name: Optional[str] = None
    second_file_path: Optional[str] = None
    extracted_date: Optional[str] = None
    files: List[SessionFile] = []
    error: Optional[str] = None


class SessionListResponse(CamelModel):
    sessions: List[SessionFull]


# ---------- upload ----------

class UploadFirstResponse(CamelModel):
    sessionId: str
    extracted_date: Optional[str] = None
    dates_info: Optional[dict] = Field(None, alias='dates_info')
    status: str
    message: str


class UploadSecondResponse(CamelModel):
    sessionId: str
    status: str


# ---------- restore / delete ----------

class RestoreResponse(CamelModel):
    sessionId: str
    extracted_date: Optional[str] = None
    first_file_name: Optional[str] = None
    status: Optional[str] = None


class DeleteResponse(CamelModel):
    deleted: bool
