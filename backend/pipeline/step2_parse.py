import io
import re
from typing import Optional

import httpx

from config import settings
from logger import get_logger

logger = get_logger(__name__)


def _normalize_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _download_pdf(url: str) -> bytes:
    if url.startswith("mock://"):
        raise ValueError("Raw PDF bytes are required for mock Cloudinary URLs")
    async with httpx.AsyncClient(timeout=settings.api_timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _extract_with_pymupdf(raw_pdf_bytes: bytes) -> tuple[str, int]:
    import fitz

    doc = fitz.open(stream=raw_pdf_bytes, filetype="pdf")
    try:
        text = "\n".join(page.get_text("text") for page in doc)
        return text, doc.page_count
    finally:
        doc.close()


def _extract_with_pdfplumber(raw_pdf_bytes: bytes) -> tuple[str, int]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw_pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text, len(pdf.pages)


async def extract_text_from_pdf(
    *,
    resume_id: str,
    raw_pdf_bytes: Optional[bytes] = None,
    cloudinary_url: Optional[str] = None,
) -> str:
    logger.info("[STEP 2] Extracting text from PDF...")
    if raw_pdf_bytes is None:
        if not cloudinary_url:
            raise ValueError("Either raw_pdf_bytes or cloudinary_url is required")
        raw_pdf_bytes = await _download_pdf(cloudinary_url)

    text = ""
    pages = 0
    try:
        logger.info("[INFO] Using PyMuPDF parser | resume_id=%s", resume_id)
        text, pages = _extract_with_pymupdf(raw_pdf_bytes)
        if len(text.strip()) < 100:
            logger.warning("[WARN] PyMuPDF returned <100 chars — switching to pdfplumber")
            raise ValueError("PyMuPDF extracted too little text")
        logger.info("[SUCCESS] Extracted %s pages | %s characters", pages, len(text))
    except Exception as first_error:
        try:
            logger.info("[INFO] pdfplumber fallback active | resume_id=%s", resume_id)
            text, pages = _extract_with_pdfplumber(raw_pdf_bytes)
            logger.info("[SUCCESS] pdfplumber extracted %s characters", len(text))
        except Exception as second_error:
            logger.warning(
                "[WARN] PDF parsers failed — attempting text decode fallback | resume_id=%s | error=%s",
                resume_id,
                second_error or first_error,
            )
            text = raw_pdf_bytes.decode("utf-8", errors="ignore")
            pages = 1

    normalized = _normalize_text(text)
    logger.debug("[DEBUG] Whitespace normalized | final_length=%s", len(normalized))
    if not normalized:
        raise ValueError("No text could be extracted from resume PDF")
    logger.info("[SUCCESS] Extracted %s pages | %s characters", pages, len(normalized))
    return normalized
