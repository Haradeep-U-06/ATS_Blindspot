from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_db, get_hr_user_id, serialize_mongo
from pipeline.step12_rank import rank_candidates
from pipeline.step6_process_jd import process_job_description

router = APIRouter(tags=["jobs"])


class JobCreateRequest(BaseModel):
    jd_text: str = Field(..., min_length=20)
    hr_user_id: Optional[str] = None


@router.post("/jobs/create")
async def create_job(
    payload: JobCreateRequest,
    db: Any = Depends(get_db),
    header_hr_user_id: str = Depends(get_hr_user_id),
) -> dict:
    job = await process_job_description(
        jd_text=payload.jd_text,
        db=db,
        hr_user_id=payload.hr_user_id or header_hr_user_id,
    )
    return serialize_mongo(job)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: Any = Depends(get_db)) -> dict:
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    return serialize_mongo(job)


@router.get("/jobs/{job_id}/candidates")
async def get_ranked_candidates(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Any = Depends(get_db),
) -> dict:
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    return serialize_mongo(await rank_candidates(db=db, job_id=job_id, page=page, page_size=page_size))
