import asyncio
import io
from typing import Any, Dict

from fastapi import HTTPException, UploadFile

from config import settings
from db.models import ResumeDocument, model_to_dict, new_id
from logger import get_logger

logger = get_logger(__name__)


async def _upload_to_cloudinary(raw_bytes: bytes, filename: str, resume_id: str) -> str:
    if not (
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    ):
        logger.warning("[WARN] Cloudinary credentials missing — using mock storage URL | resume_id=%s", resume_id)
        return f"mock://cloudinary/{resume_id}/{filename}"

    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )

    def _call() -> Dict[str, Any]:
        return cloudinary.uploader.upload(
            io.BytesIO(raw_bytes),
            resource_type="raw",
            public_id=f"resumes/{resume_id}",
            filename=filename,
            overwrite=True,
        )

    result = await asyncio.to_thread(_call)
    return result.get("secure_url") or result.get("url")


async def ingest_resume(file: UploadFile, db: Any) -> Dict[str, Any]:
    logger.info("[STEP 1] Receiving resume upload...")
    filename = file.filename or "resume.pdf"
    if not filename.lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF resumes are allowed")

    raw_bytes = await file.read()
    size = len(raw_bytes)
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if size > settings.max_resume_size_bytes:
        raise HTTPException(status_code=413, detail="Resume exceeds 10MB limit")

    logger.info("[INFO] File validated | filename=%s | size=%sKB", filename, max(1, size // 1024))
    resume_id = new_id("resume")
    logger.info("[INFO] Uploading to Cloudinary...")
    cloudinary_url = await _upload_to_cloudinary(raw_bytes, filename, resume_id)
    logger.info("[SUCCESS] Resume stored | resume_id=%s | url=%s", resume_id, cloudinary_url)

    document = ResumeDocument(
        resume_id=resume_id,
        filename=filename,
        cloudinary_url=cloudinary_url,
    )
    await db.resumes.insert_one(model_to_dict(document))
    logger.info("[INFO] MongoDB record created | status=uploaded | resume_id=%s", resume_id)
    return {
        "resume_id": resume_id,
        "cloudinary_url": cloudinary_url,
        "raw_bytes": raw_bytes,
        "filename": filename,
    }
