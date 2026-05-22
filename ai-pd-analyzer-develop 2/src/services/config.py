import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    ollama_url: str
    DOCUMENTS_PATH: str
    norms_model: str
    norms_model_qwen: str
    report_filename: str


def load_config() -> Config:
    return Config(
        ollama_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        DOCUMENTS_PATH=os.getenv("DOCUMENTS_PATH", "data/documents.json"),
        norms_model=os.getenv("NORMS_LLM_MODEL", "yandex/YandexGPT-5-Lite-8B-instruct-GGUF:latest"),
        norms_model_qwen=os.getenv("NORMS_LLM_MODEL_QWEN", "hf.co/GreenMap/qwen3.5-2b-ru-norm-link-extractor-GGUF:BF16"),
        report_filename=os.getenv("REPORT_FILENAME", "report.txt"),
    )
