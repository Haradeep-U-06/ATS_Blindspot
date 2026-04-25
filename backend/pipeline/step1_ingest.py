import asyncio
import io
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, UploadFile

from db.models import ResumeDocument, model_to_dict, new_id
from logger import get_logger

logger = get_logger(__name__)

# Directory where resume files are saved on disk
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "resumes"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


async def _save_to_local(raw_bytes: bytes, filename: str, resume_id: str) -> str:
    """Save resume bytes to local disk and return the backend URL to serve it."""
    suffix = Path(filename).suffix.lower() or ".pdf"
    local_path = UPLOADS_DIR / f"{resume_id}{suffix}"
    await asyncio.to_thread(local_path.write_bytes, raw_bytes)
    logger.info("[STORAGE] Saved file locally | path=%s", local_path)
    # Return a backend-served URL that the frontend will use
    return f"http://localhost:8000/resume/{resume_id}/pdf"


async def ingest_resume(file: UploadFile, db: Any) -> Dict[str, Any]:
    logger.info("[STEP 1] Receiving resume upload...")
    filename = file.filename or "resume.pdf"
    supported_extensions = (".pdf", ".docx", ".txt")
    if not filename.lower().endswith(supported_extensions):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, or TXT resumes are allowed")

    raw_bytes = await file.read()
    size = len(raw_bytes)
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    logger.info("[INFO] File validated | filename=%s | size=%sKB", filename, max(1, size // 1024))
    resume_id = new_id("resume")

    logger.info("[INFO] Saving resume to local disk | resume_id=%s", resume_id)
    file_url = await _save_to_local(raw_bytes, filename, resume_id)
    logger.info("[SUCCESS] Resume stored locally | resume_id=%s", resume_id)

    document = ResumeDocument(
        resume_id=resume_id,
        filename=filename,
        cloudinary_url=file_url,   # reusing the existing field — now points to local URL
    )
    await db.resumes.insert_one(model_to_dict(document))
    logger.info("[INFO] MongoDB record created | status=uploaded | resume_id=%s", resume_id)
    return {
        "resume_id": resume_id,
        "cloudinary_url": file_url,
        "raw_bytes": raw_bytes,
        "filename": filename,
    }
