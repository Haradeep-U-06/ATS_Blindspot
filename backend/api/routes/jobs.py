import json
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.dependencies import get_db, get_hr_user_id, serialize_mongo
from pipeline.orchestrator import EVALUATABLE_RESUME_STATUSES, run_job_evaluation
from pipeline.step12_rank import _score_breakdown, _structured_resume_summary, rank_candidates
from pipeline.step6_process_jd import create_job_record

router = APIRouter(tags=["jobs"])


class JobCreateRequest(BaseModel):
    jd_text: str = Field(..., min_length=20)
    hr_user_id: Optional[str] = None


JD_TEXT_FIELDS = ("jd_text", "job_description", "description", "raw_jd_text", "jd", "text")
HR_USER_FIELDS = ("hr_user_id", "hrUserId", "hr_id", "user_id")


def _coerce_body_to_dict(body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        return {"jd_text": body}
    raise HTTPException(status_code=400, detail="Request body must be a JSON object, form body, or raw JD text")


def _first_text(data: dict[str, Any], fields: tuple[str, ...]) -> Optional[str]:
    for field in fields:
        value = data.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


async def _parse_job_create_request(request: Request) -> JobCreateRequest:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            data = _coerce_body_to_dict(await request.json())
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        data = dict(await request.form())
    else:
        raw_body = (await request.body()).decode("utf-8", errors="ignore").strip()
        if not raw_body:
            data = {}
        else:
            try:
                data = _coerce_body_to_dict(json.loads(raw_body))
            except json.JSONDecodeError:
                data = {"jd_text": raw_body}

    jd_text = _first_text(data, JD_TEXT_FIELDS)
    if not jd_text:
        raise HTTPException(
            status_code=400,
            detail="jd_text is required. Send JSON with jd_text, job_description, description, raw_jd_text, jd, or text.",
        )
    if len(jd_text) < 20:
        raise HTTPException(status_code=400, detail="jd_text must be at least 20 characters")
    return JobCreateRequest(jd_text=jd_text, hr_user_id=_first_text(data, HR_USER_FIELDS))


@router.post("/jobs/create")
async def create_job(
    request: Request,
    db: Any = Depends(get_db),
    header_hr_user_id: str = Depends(get_hr_user_id),
) -> dict:
    payload = await _parse_job_create_request(request)
    job = await create_job_record(
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


@router.post("/jobs/{job_id}/evaluation/trigger")
async def trigger_evaluation(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Any = Depends(get_db),
) -> dict:
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    in_progress = await db.resumes.count_documents(
        {"job_id": job_id, "status": {"$in": ["parsing", "enriching", "vectorizing"]}}
    )
    if in_progress:
        raise HTTPException(status_code=409, detail=f"{in_progress} resumes are still being vectorized")

    ready_count = await db.resumes.count_documents({"job_id": job_id, "status": {"$in": EVALUATABLE_RESUME_STATUSES}})
    await db.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"application_window_closed": True, "evaluation_status": "queued", "evaluation_error": None}},
    )
    background_tasks.add_task(run_job_evaluation, job_id=job_id, db=db)
    return {
        "job_id": job_id,
        "application_window_closed": True,
        "evaluation_status": "queued",
        "resumes_to_evaluate": ready_count,
    }


@router.get("/jobs/{job_id}/evaluation/status")
async def get_evaluation_status(job_id: str, db: Any = Depends(get_db)) -> dict:
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    counts = {
        "uploaded": await db.resumes.count_documents({"job_id": job_id, "status": "uploaded"}),
        "processing": await db.resumes.count_documents({"job_id": job_id, "status": {"$in": ["parsing", "enriching", "vectorizing"]}}),
        "ready_for_evaluation": await db.resumes.count_documents({"job_id": job_id, "status": "ready_for_evaluation"}),
        "evaluating": await db.resumes.count_documents({"job_id": job_id, "status": "evaluating"}),
        "completed": await db.resumes.count_documents({"job_id": job_id, "status": "completed"}),
        "failed": await db.resumes.count_documents({"job_id": job_id, "status": {"$in": ["failed", "parse_failed", "vector_failed"]}}),
    }
    counts["eligible_for_evaluation"] = await db.resumes.count_documents({"job_id": job_id, "status": {"$in": EVALUATABLE_RESUME_STATUSES}})
    counts["total"] = sum(counts[key] for key in ("uploaded", "processing", "ready_for_evaluation", "evaluating", "completed", "failed"))
    return serialize_mongo(
        {
            "job_id": job_id,
            "application_window_closed": job.get("application_window_closed", False),
            "evaluation_status": job.get("evaluation_status", "not_started"),
            "evaluation_error": job.get("evaluation_error"),
            "resume_counts": counts,
            "candidate_count": await db.candidates.count_documents({"job_id": job_id}),
        }
    )


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
    if job.get("evaluation_status") not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=409, detail="Evaluation has not completed for this job")
    return serialize_mongo(await rank_candidates(db=db, job_id=job_id, page=page, page_size=page_size))


@router.get("/jobs/{job_id}/candidates/{candidate_id}")
async def get_candidate_dashboard(job_id: str, candidate_id: str, db: Any = Depends(get_db)) -> dict:
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate_id not found")
    score = await db.scores.find_one({"job_id": job_id, "candidate_id": candidate_id})
    if not score:
        raise HTTPException(status_code=404, detail="score not found for candidate/job")
    payload = {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "resume_id": candidate.get("resume_id"),
        "summary": {
            "name": candidate.get("name", ""),
            "email": candidate.get("email", ""),
            "phone": candidate.get("phone", ""),
            "resume_summary": candidate.get("summary", ""),
            "external_profiles": {
                "github": candidate.get("github_username"),
                "leetcode": candidate.get("leetcode_username"),
                "codeforces": candidate.get("codeforces_username"),
                "codechef": candidate.get("codechef_username"),
            },
        },
        "resume_summary": _structured_resume_summary(candidate),
        "final_score": score.get("final_score", 0),
        "skill_scores": (score.get("subscores_detail", {}) or {}).get("skill_scores", []),
        "skill_matches": score.get("skill_matches", []),
        "evidence_chunks": score.get("evidence_chunks", {}),
        "pros": score.get("strengths", []),
        "cons": score.get("gaps", []),
        "strengths": score.get("strengths", []),
        "weaknesses": score.get("gaps", []),
        "explanation": score.get("overall_explanation", ""),
        "score_breakdown": _score_breakdown(score),
    }
    return serialize_mongo(payload)
