import json
from functools import lru_cache

from .config import load_config

DOCUMENTS_PATH = load_config().DOCUMENTS_PATH


@lru_cache(maxsize=1)
def load_documents():
    with open(DOCUMENTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _documents_by_code():
    return {doc["code"]: doc for doc in load_documents()}


def get_document_by_code(doc_code):
    return _documents_by_code().get(doc_code)


def is_fz_document(doc_code):
    doc = get_document_by_code(doc_code)
    return bool(doc and doc.get("category") == "fz")
