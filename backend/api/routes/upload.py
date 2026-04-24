from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from api.dependencies import get_db, serialize_mongo
from logger import get_logger
from pipeline.orchestrator import run_full_pipeline
from pipeline.step1_ingest import ingest_resume

logger = get_logger(__name__)
router = APIRouter(tags=["upload"])


@router.post("/upload/resume")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: Optional[str] = Form(default=None),
    db: Any = Depends(get_db),
) -> dict:
    if job_id:
        job = await db.jobs.find_one({"job_id": job_id})
        if not job:
            raise HTTPException(status_code=404, detail="job_id not found")
    result = await ingest_resume(file, db)
    if job_id:
        background_tasks.add_task(run_full_pipeline, result["resume_id"], job_id, result["raw_bytes"], db)
        logger.info("[INFO] Background pipeline task queued | resume_id=%s | job_id=%s", result["resume_id"], job_id)
    return {
        "resume_id": result["resume_id"],
        "cloudinary_url": result["cloudinary_url"],
        "status": "uploaded",
        "pipeline_started": bool(job_id),
    }


@router.get("/status/{resume_id}")
async def get_resume_status(resume_id: str, db: Any = Depends(get_db)) -> dict:
    resume = await db.resumes.find_one({"resume_id": resume_id})
    if not resume:
        raise HTTPException(status_code=404, detail="resume_id not found")
    return serialize_mongo(resume)
