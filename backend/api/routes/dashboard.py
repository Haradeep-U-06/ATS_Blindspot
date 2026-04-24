from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import get_db, serialize_mongo
from logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(db: Any = Depends(get_db)) -> dict:
    logger.info("[INFO] Building HR dashboard overview")
    total_jobs = await db.jobs.count_documents({})
    total_candidates = await db.candidates.count_documents({})
    total_resumes = await db.resumes.count_documents({})
    completed_resumes = await db.resumes.count_documents({"status": "completed"})
    failed_resumes = await db.resumes.count_documents({"status": {"$in": ["failed", "parse_failed"]}})
    latest_jobs = await db.jobs.find({}).sort("created_at", -1).limit(5).to_list(length=5)
    top_scores = await db.scores.find({}).sort("final_score", -1).limit(10).to_list(length=10)
    logger.info("[SUCCESS] Dashboard overview ready | jobs=%s | candidates=%s", total_jobs, total_candidates)
    return serialize_mongo(
        {
            "total_jobs": total_jobs,
            "total_candidates": total_candidates,
            "total_resumes": total_resumes,
            "completed_resumes": completed_resumes,
            "failed_resumes": failed_resumes,
            "latest_jobs": latest_jobs,
            "top_scores": top_scores,
        }
    )
