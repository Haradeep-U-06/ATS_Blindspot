import time
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from db.models import ResumeStatus
from db.mongo import get_database
from llm.exceptions import JSONRepairError
from llm.router import LLMRouter
from logger import get_logger
from pipeline.step2_parse import extract_text_from_resume
from pipeline.step3_structure import structure_resume
from pipeline.step4_enrich import enrich_profile
from pipeline.step6_process_jd import process_job_description
from pipeline.step7_embed import vectorize_candidate_profile
from pipeline.step8_rag import run_rag_for_resume
from pipeline.step9_evaluate import evaluate_candidate
from pipeline.step10_score import score_candidate
from pipeline.step11_store import persist_results, persist_vectorized_candidate

logger = get_logger(__name__)
T = TypeVar("T")
EVALUATABLE_RESUME_STATUSES = [
    ResumeStatus.ready_for_evaluation.value,
    ResumeStatus.evaluating.value,
    ResumeStatus.completed.value,
]


async def _update_resume_status(db: Any, resume_id: str, status: ResumeStatus, error_message: str | None = None) -> None:
    await db.resumes.update_one(
        {"resume_id": resume_id},
        {"$set": {"status": status.value, "error_message": error_message}},
    )


async def _run_step(step_name: str, resume_id: str, func: Callable[[], Awaitable[T]]) -> T:
    started = time.perf_counter()
    logger.info("[STEP] %s | resume_id=%s", step_name, resume_id)
    result = await func()
    logger.info("[SUCCESS] %s | resume_id=%s | elapsed=%.2fs", step_name, resume_id, time.perf_counter() - started)
    return result


async def run_upload_vectorization_pipeline(
    resume_id: str,
    job_id: str,
    raw_resume_bytes: Optional[bytes] = None,
    filename: str = "resume.pdf",
    external_links: Optional[Dict[str, Optional[str]]] = None,
    db: Any | None = None,
) -> None:
    database = db if db is not None else get_database()
    total_started = time.perf_counter()
    logger.info("[INFO] Resume received | resume_id=%s | job_id=%s", resume_id, job_id)
    phase = ResumeStatus.uploaded
    try:
        resume = await database.resumes.find_one({"resume_id": resume_id})
        if not resume:
            raise ValueError(f"Resume not found: {resume_id}")
        job = await database.jobs.find_one({"job_id": job_id})
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        phase = ResumeStatus.parsing
        await _update_resume_status(database, resume_id, phase)
        raw_text = await _run_step(
            "Parsing resume with Python libraries",
            resume_id,
            lambda: extract_text_from_resume(
                resume_id=resume_id,
                filename=filename,
                raw_pdf_bytes=raw_resume_bytes,
                cloudinary_url=resume.get("cloudinary_url"),
            ),
        )
        structured = await _run_step(
            "Structuring explicit resume data without LLM",
            resume_id,
            lambda: structure_resume(
                resume_id=resume_id,
                raw_text=raw_text,
                external_links=external_links or {},
            ),
        )

        phase = ResumeStatus.enriching
        await _update_resume_status(database, resume_id, phase)
        enrichment = await _run_step(
            "Fetching external profiles",
            resume_id,
            lambda: enrich_profile(resume_id=resume_id, structured_resume=structured),
        )
        candidate_profile = {**structured, **enrichment}

        phase = ResumeStatus.vectorizing
        await _update_resume_status(database, resume_id, phase)
        vectorized = await _run_step(
            "Vectorizing resume and external data",
            resume_id,
            lambda: vectorize_candidate_profile(
                db=database,
                resume_id=resume_id,
                job_id=job_id,
                raw_text=raw_text,
                candidate_profile=candidate_profile,
            ),
        )
        await _run_step(
            "Persisting vectorized candidate",
            resume_id,
            lambda: persist_vectorized_candidate(
                db=database,
                resume_id=resume_id,
                job_id=job_id,
                raw_text=raw_text,
                candidate_profile=candidate_profile,
                chunk_count=vectorized["chunk_count"],
            ),
        )
        logger.info(
            "[INFO] Waiting for evaluation trigger | resume_id=%s | total_elapsed=%.2fs",
            resume_id,
            time.perf_counter() - total_started,
        )
    except Exception as exc:
        if phase == ResumeStatus.parsing or isinstance(exc, JSONRepairError):
            status = ResumeStatus.parse_failed
        elif phase == ResumeStatus.vectorizing:
            status = ResumeStatus.vector_failed
        else:
            status = ResumeStatus.failed
        await _update_resume_status(database, resume_id, status, str(exc))
        logger.error("[ERROR] Upload vectorization pipeline failed | resume_id=%s | error=%s", resume_id, exc)


async def _evaluate_one_resume(
    *,
    database: Any,
    router: LLMRouter,
    resume: Dict[str, Any],
    job: Dict[str, Any],
    force: bool = False,
) -> Dict[str, Any]:
    resume_id = resume["resume_id"]
    job_id    = job["job_id"]

    # ── Score cache: skip LLM re-evaluation if a valid score already exists ──
    if not force:
        existing_score = await database.scores.find_one(
            {"resume_id": resume_id, "job_id": job_id, "final_score": {"$gt": 0}}
        )
        if existing_score:
            logger.info(
                "[CACHE] Valid score found — skipping re-evaluation | resume_id=%s | cached_score=%.2f",
                resume_id, existing_score.get("final_score", 0),
            )
            await _update_resume_status(database, resume_id, ResumeStatus.completed)
            return {"candidate_id": existing_score.get("candidate_id"), "score": existing_score}

    await _update_resume_status(database, resume_id, ResumeStatus.evaluating)
    candidate = await database.candidates.find_one({"resume_id": resume_id})
    if not candidate:
        raise ValueError(f"Candidate profile not found for resume: {resume_id}")

    rag_result = await _run_step(
        "Running per-resume RAG",
        resume_id,
        lambda: run_rag_for_resume(resume_id=resume_id, job=job),
    )
    evaluation = await _run_step(
        "Scoring candidate evidence with LLM",
        resume_id,
        lambda: evaluate_candidate(
            resume_id=resume_id,
            candidate_profile=candidate,
            job=job,
            rag_context=rag_result["context"],
            rag_evidence=rag_result,
            llm_router=router,
        ),
    )
    score_result = await _run_step(
        "Computing final score",
        resume_id,
        lambda: score_candidate(candidate_profile=candidate, job=job, evaluation=evaluation),
    )
    persisted = await _run_step(
        "Persisting score",
        resume_id,
        lambda: persist_results(
            db=database,
            resume_id=resume_id,
            candidate_profile=candidate,
            job_id=job_id,
            evaluation=evaluation,
            score_result=score_result,
        ),
    )
    return persisted


def _job_has_structured_requirements(job: Dict[str, Any]) -> bool:
    return bool(job.get("required_skills") or job.get("preferred_skills")) and job.get("title") != "Unprocessed Job Description"


async def run_job_evaluation(
    *,
    job_id: str,
    db: Any | None = None,
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    database = db if db is not None else get_database()
    router = llm_router or LLMRouter()
    logger.info("[STEP] HR triggered evaluation | job_id=%s", job_id)
    job = await database.jobs.find_one({"job_id": job_id})
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    in_progress = await database.resumes.count_documents(
        {"job_id": job_id, "status": {"$in": [ResumeStatus.parsing.value, ResumeStatus.enriching.value, ResumeStatus.vectorizing.value]}}
    )
    if in_progress:
        raise ValueError(f"{in_progress} resumes are still processing; evaluation cannot start yet")

    await database.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"application_window_closed": True, "evaluation_status": "processing", "evaluation_error": None}},
    )
    if _job_has_structured_requirements(job):
        structured_job = {
            **job,
            "application_window_closed": True,
            "evaluation_status": "processing",
            "evaluation_error": None,
        }
        logger.info("[INFO] Reusing structured JD requirements | job_id=%s", job_id)
    else:
        structured_job = await process_job_description(
            jd_text=job["raw_jd_text"],
            db=database,
            hr_user_id=job.get("hr_user_id", "default_hr"),
            job_id=job_id,
            llm_router=router,
            application_window_closed=True,
            evaluation_status="processing",
        )

    resumes = await database.resumes.find(
        {"job_id": job_id, "status": {"$in": EVALUATABLE_RESUME_STATUSES}}
    ).to_list(length=None)
    logger.info("[INFO] Evaluating %s resumes | job_id=%s", len(resumes), job_id)
    results = []
    failed = []
    for resume in resumes:
        try:
            results.append(await _evaluate_one_resume(database=database, router=router, resume=resume, job=structured_job))
        except Exception as exc:
            failed.append({"resume_id": resume.get("resume_id"), "error": str(exc)})
            await _update_resume_status(database, resume["resume_id"], ResumeStatus.failed, str(exc))
            logger.error("[ERROR] Candidate scoring failed | resume_id=%s | error=%s", resume.get("resume_id"), exc)

    status = "completed" if not failed else "completed_with_errors"
    await database.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"evaluation_status": status, "evaluation_error": None if not failed else str(failed)}},
    )
    logger.info("[SUCCESS] Job evaluation finished | job_id=%s | scored=%s | failed=%s", job_id, len(results), len(failed))
    return {"job_id": job_id, "status": status, "scored": len(results), "failed": failed}
