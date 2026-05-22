import os
import shutil
import uuid
from typing import Any, Dict

from .gpuz import findDateInGPZU
from .json_saver import process_complex_json_to_csv
from .norms_actualizer import searchActualNorm, copyActualNorm
from .mopb_extractor import searchМОРВ
from .reference_parser import punktМОРВ
from .comparison import comparisionМОРВ


def process_mopb_validation(
    gpzu_pdf_path: str,
    mopb_pdf_path: str,
    output_dir: str = "outputs",
    perechen_pdf: str = "data/Perechen.pdf",
) -> Dict[str, Any]:
    sessionId = str(uuid.uuid4())
    session_output_dir = os.path.join(output_dir, sessionId)
    os.makedirs(session_output_dir, exist_ok=True)

    extracted_date = findDateInGPZU(gpzu_pdf_path)

    searchActualNorm(target_date=extracted_date, normsList=perechen_pdf)
    copyActualNorm()

    searchМОРВ(MOPB_PDF=mopb_pdf_path)
    punktМОРВ()
    comparisionМОРВ()

    result_files = []

    if os.path.exists("все_СП_результаты.json"):
        dest_path = os.path.join(session_output_dir, "все_СП_результаты.json")
        shutil.copy("все_СП_результаты.json", dest_path)
        result_files.append({
            "path": dest_path,
            "filename": "все_СП_результаты.json",
            "size": os.path.getsize(dest_path),
        })

    for file_path in process_complex_json_to_csv("MOPB_сравнение", session_output_dir):
        result_files.append({
            "path": file_path,
            "filename": os.path.basename(file_path),
            "size": os.path.getsize(file_path),
        })

    return {
        "extracted_date": extracted_date,
        "output_directory": session_output_dir,
        "files": result_files,
    }
