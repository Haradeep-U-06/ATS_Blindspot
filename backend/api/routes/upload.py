from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from api.dependencies import get_db, serialize_mongo
from logger import get_logger
from pipeline.orchestrator import run_upload_vectorization_pipeline
from pipeline.step1_ingest import ingest_resume

logger = get_logger(__name__)
router = APIRouter(tags=["upload"])


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
