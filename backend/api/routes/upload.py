import asyncio
from html import escape
import textwrap
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

from api.dependencies import get_db, serialize_mongo
from config import settings
from logger import get_logger
from pipeline.orchestrator import run_upload_vectorization_pipeline
from pipeline.step1_ingest import UPLOADS_DIR, ingest_resume

import httpx

logger = get_logger(__name__)
router = APIRouter(tags=["upload"])


def _safe_pdf_filename(filename: str | None) -> str:
    cleaned = (filename or "resume.pdf").split("/")[-1].replace('"', "").strip() or "resume.pdf"
    return cleaned if cleaned.lower().endswith(".pdf") else f"{cleaned}.pdf"


def _append_pdf_extension(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.lower().endswith(".pdf"):
        return url
    return urlunparse(parsed._replace(path=f"{parsed.path}.pdf"))


def _candidate_pdf_urls(url: str) -> list[str]:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="A valid http(s) PDF URL is required")

    candidates: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    original = urlunparse(parsed)
    add(original)
    if "/image/upload/" in original:
        add(original.replace("/image/upload/", "/raw/upload/"))
    if "/raw/upload/" in original:
        add(original.replace("/raw/upload/", "/image/upload/"))

    for candidate in list(candidates):
        add(_append_pdf_extension(candidate))
    return candidates


async def _fetch_pdf_bytes(url: str) -> bytes:
    errors: list[str] = []
    headers = {
        "Accept": "application/pdf,application/octet-stream,*/*",
        "User-Agent": "ATS-PDF-Proxy/1.0",
    }
    async with httpx.AsyncClient(timeout=settings.api_timeout_seconds, follow_redirects=True) as client:
        for candidate_url in _candidate_pdf_urls(url):
            try:
                response = await client.get(candidate_url, headers=headers)
            except httpx.HTTPError as exc:
                errors.append(f"{candidate_url}: {exc}")
                continue

            content_type = response.headers.get("content-type", "").lower()
            if response.status_code != 200:
                errors.append(f"{candidate_url}: HTTP {response.status_code}")
                continue

            content = response.content
            if content.lstrip().startswith(b"%PDF") or "application/pdf" in content_type:
                return content

            preview = content[:160].decode("utf-8", errors="ignore").replace("\n", " ")
            errors.append(f"{candidate_url}: non-PDF response ({content_type or 'unknown type'}) {preview!r}")

    logger.error("[ERROR] Unable to fetch PDF | attempts=%s", " | ".join(errors))
    raise HTTPException(status_code=502, detail="Resume PDF could not be loaded from storage")


def _pdf_response(content: bytes, filename: str | None = None) -> Response:
    safe_filename = _safe_pdf_filename(filename)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


def _pdf_from_text(text: str, filename: str | None = None) -> Response:
    import fitz

    safe_filename = _safe_pdf_filename(filename)
    document = fitz.open()
    page_width = 595
    page_height = 842
    margin = 48
    line_height = 14
    font_size = 10
    max_chars = 96

    page = document.new_page(width=page_width, height=page_height)
    y = margin
    title = safe_filename.removesuffix(".pdf")
    page.insert_text((margin, y), title, fontsize=14, fontname="helv", color=(0.07, 0.12, 0.2))
    y += 26

    def add_page():
        return document.new_page(width=page_width, height=page_height)

    for paragraph in (text or "").splitlines():
        wrapped_lines = textwrap.wrap(
            paragraph,
            width=max_chars,
            replace_whitespace=False,
            drop_whitespace=False,
        ) or [""]
        for line in wrapped_lines:
            if y > page_height - margin:
                page = add_page()
                y = margin
            page.insert_text((margin, y), line, fontsize=font_size, fontname="helv", color=(0.1, 0.12, 0.16))
            y += line_height
        y += 4

    content = document.write()
    document.close()
    return _pdf_response(content, safe_filename)


def _resume_pdf_fallback(resume: dict[str, Any]) -> Response | None:
    raw_text = resume.get("raw_text")
    if not raw_text:
        return None
    logger.warning(
        "[WARN] Serving generated PDF from extracted resume text | resume_id=%s",
        resume.get("resume_id"),
    )
    return _pdf_from_text(str(raw_text), resume.get("filename"))


def _resume_text_view(resume: dict[str, Any], message: str) -> HTMLResponse:
    filename = escape(resume.get("filename") or "resume")
    raw_text = escape(resume.get("raw_text") or "")
    title = escape(f"Resume - {resume.get('resume_id', '')}")
    if raw_text:
        body = f"<pre>{raw_text}</pre>"
    else:
        body = "<div class=\"empty\">No extracted resume text is available yet.</div>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #172033;
      background: #f7f8fb;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: #f7f8fb;
    }}
    header {{
      position: sticky;
      top: 0;
      padding: 18px 28px;
      border-bottom: 1px solid #dfe4ee;
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(10px);
    }}
    h1 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
    }}
    p {{
      margin: 6px 0 0;
      color: #677086;
      font-size: 14px;
    }}
    main {{
      max-width: 980px;
      margin: 24px auto;
      padding: 0 18px 36px;
    }}
    pre, .empty {{
      box-sizing: border-box;
      min-height: 70vh;
      margin: 0;
      padding: 28px;
      border: 1px solid #dfe4ee;
      border-radius: 10px;
      background: #ffffff;
      box-shadow: 0 18px 42px rgba(20, 32, 54, 0.08);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font: 14px/1.65 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }}
    .empty {{
      display: grid;
      place-items: center;
      color: #677086;
      font-family: inherit;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{filename}</h1>
    <p>{escape(message)}</p>
  </header>
  <main>{body}</main>
</body>
</html>"""
    return HTMLResponse(
        content=html,
        status_code=200,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/proxy-pdf")
async def proxy_pdf(url: str, filename: str | None = None):
    """Proxy a remote PDF as an inline browser-viewable document."""
    return _pdf_response(await _fetch_pdf_bytes(url), filename)


@router.post("/upload/resume")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: str = Form(...),
    github_url: Optional[str] = Form(default=None),
    leetcode_url: Optional[str] = Form(default=None),
    codeforces_url: Optional[str] = Form(default=None),
    codechef_url: Optional[str] = Form(default=None),
    db: Any = Depends(get_db),
) -> dict:
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    if job.get("application_window_closed"):
        raise HTTPException(status_code=409, detail="Application window is closed for this job")

    result = await ingest_resume(file, db)
    external_links = {
        "github": github_url,
        "leetcode": leetcode_url,
        "codeforces": codeforces_url,
        "codechef": codechef_url,
    }
    await db.resumes.update_one(
        {"resume_id": result["resume_id"]},
        {"$set": {"job_id": job_id, "external_links": external_links}},
    )
    background_tasks.add_task(
        run_upload_vectorization_pipeline,
        result["resume_id"],
        job_id,
        result["raw_bytes"],
        result["filename"],
        external_links,
        db,
    )
    logger.info("[INFO] Background vectorization task queued | resume_id=%s | job_id=%s", result["resume_id"], job_id)
    return {
        "resume_id": result["resume_id"],
        "job_id": job_id,
        "cloudinary_url": result["cloudinary_url"],
        "status": "uploaded",
        "processing": "parse_enrich_vectorize",
        "scoring_started": False,
    }


@router.get("/status/{resume_id}")
async def get_resume_status(resume_id: str, db: Any = Depends(get_db)) -> dict:
    resume = await db.resumes.find_one({"resume_id": resume_id})
    if not resume:
        raise HTTPException(status_code=404, detail="resume_id not found")
    return serialize_mongo(resume)


@router.get("/resume/{resume_id}")
async def get_resume_content(resume_id: str, db: Any = Depends(get_db)) -> dict:
    """Return PDF URL + extracted text so the frontend can display the resume."""
    resume = await db.resumes.find_one({"resume_id": resume_id})
    if not resume:
        raise HTTPException(status_code=404, detail="resume_id not found")
    return serialize_mongo({
        "resume_id":      resume_id,
        "filename":       resume.get("filename", "resume.pdf"),
        "cloudinary_url": resume.get("cloudinary_url"),
        "raw_text":       resume.get("raw_text"),
        "status":         resume.get("status"),
    })


@router.get("/resume/{resume_id}/pdf")
async def get_resume_pdf(resume_id: str, db: Any = Depends(get_db)) -> Response:
    """Serve the resume PDF from local disk, with extracted-text fallback."""
    resume = await db.resumes.find_one({"resume_id": resume_id})
    if not resume:
        raise HTTPException(status_code=404, detail="resume_id not found")

    # Look for the file on disk with any supported extension
    for suffix in (".pdf", ".docx", ".txt"):
        local_path = UPLOADS_DIR / f"{resume_id}{suffix}"
        if local_path.exists():
            content = await asyncio.to_thread(local_path.read_bytes)
            if suffix == ".pdf" or content.lstrip().startswith(b"%PDF"):
                return _pdf_response(content, resume.get("filename"))
            # For non-PDF files, render from extracted text
            break

    # Fallback: generate a PDF from the extracted raw_text
    fallback = _resume_pdf_fallback(resume)
    if fallback:
        return fallback
    raise HTTPException(status_code=404, detail="Resume file not found on disk")


@router.get("/resume/{resume_id}/view")
async def view_resume(resume_id: str, db: Any = Depends(get_db)) -> Response:
    """Open a browser-friendly resume page, with extracted text fallback for bad legacy PDF URLs."""
    resume = await db.resumes.find_one({"resume_id": resume_id})
    if not resume:
        raise HTTPException(status_code=404, detail="resume_id not found")

    cloudinary_url = resume.get("cloudinary_url")
    if cloudinary_url and not str(cloudinary_url).startswith("mock://"):
        try:
            return _pdf_response(await _fetch_pdf_bytes(cloudinary_url), resume.get("filename"))
        except HTTPException as exc:
            fallback = _resume_pdf_fallback(resume)
            if fallback:
                return fallback
            else:
                raise exc

    fallback = _resume_pdf_fallback(resume)
    if fallback:
        return fallback

    return _resume_text_view(
        resume,
        "The uploaded PDF file could not be loaded from storage, so this page is showing the extracted resume text.",
    )
