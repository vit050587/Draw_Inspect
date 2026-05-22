from datetime import datetime
from .config import load_config
from .gpuz import findDateInGPZU
from .norms_actualizer import searchActualNorm, copyActualNorm
from .mopb_extractor import searchМОРВ
from .reference_parser import punktМОРВ
from .comparison import comparisionМОРВ

OLLAMA_URL = load_config().ollama_url


def parse_date(date_str):
    if not date_str or date_str == "бессрочно" or "внесения" in date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d.%m.%Y")
    except Exception:
        return None


def processDocument(fileGPZU: str, normsList: str, MOPB_PDF: str):
    date = findDateInGPZU(fileGPZU)
    try:
        datetime.strptime(date, "%d.%m.%Y")
    except Exception as e:
        print(f"Ошибка при получении даты {e}")
        return False

    searchActualNorm(target_date=date, normsList=normsList)
    copyActualNorm()
    searchМОРВ(MOPB_PDF=MOPB_PDF)
    punktМОРВ()
    comparisionМОРВ()
    return True
