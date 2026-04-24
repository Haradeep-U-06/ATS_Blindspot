import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

from db.models import ResumeStatus
from db.mongo import get_database
from llm.exceptions import JSONRepairError
from llm.router import LLMRouter
from logger import get_logger
from pipeline.step2_parse import extract_text_from_pdf
from pipeline.step3_structure import structure_resume
from pipeline.step4_enrich import enrich_profile
from pipeline.step5_infer_skills import infer_skills
from pipeline.step7_embed import generate_embeddings
from pipeline.step8_rag import run_rag_pipeline
from pipeline.step9_evaluate import evaluate_candidate
from pipeline.step10_score import score_candidate
from pipeline.step11_store import persist_results

logger = get_logger(__name__)
T = TypeVar("T")


async def _update_resume_status(db: Any, resume_id: str, status: ResumeStatus, error_message: str | None = None) -> None:
    await db.resumes.update_one(
        {"resume_id": resume_id},
        {"$set": {"status": status.value, "error_message": error_message}},
    )


async def _run_step(step_number: int, resume_id: str, func: Callable[[], Awaitable[T]]) -> T:
    started = time.perf_counter()
    logger.info("[PIPELINE] Starting step %s | resume_id=%s", step_number, resume_id)
    result = await func()
    logger.info(
        "[PIPELINE] Step %s complete | resume_id=%s | elapsed=%.2fs",
        step_number,
        resume_id,
        time.perf_counter() - started,
    )
    return result


async def run_full_pipeline(
    resume_id: str,
    job_id: str,
    raw_pdf_bytes: Optional[bytes] = None,
    db: Any | None = None,
    llm_router: LLMRouter | None = None,
) -> None:
    database = db if db is not None else get_database()
    router = llm_router or LLMRouter()
    total_started = time.perf_counter()
    logger.info("[PIPELINE] Full pipeline starting | resume_id=%s | job_id=%s", resume_id, job_id)
    try:
        resume = await database.resumes.find_one({"resume_id": resume_id})
        if not resume:
            raise ValueError(f"Resume not found: {resume_id}")
        job = await database.jobs.find_one({"job_id": job_id})
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        await _update_resume_status(database, resume_id, ResumeStatus.parsing)
        raw_text = await _run_step(
            2,
            resume_id,
            lambda: extract_text_from_pdf(
                resume_id=resume_id,
                raw_pdf_bytes=raw_pdf_bytes,
                cloudinary_url=resume.get("cloudinary_url"),
            ),
        )
        structured = await _run_step(
            3,
            resume_id,
            lambda: structure_resume(resume_id=resume_id, raw_text=raw_text, llm_router=router),
        )

        await _update_resume_status(database, resume_id, ResumeStatus.enriching)
        enrichment = await _run_step(
            4,
            resume_id,
            lambda: enrich_profile(resume_id=resume_id, structured_resume=structured),
        )
        candidate_profile = {**structured, **enrichment}
        candidate_profile = await _run_step(
            5,
            resume_id,
            lambda: infer_skills(resume_id=resume_id, candidate_profile=candidate_profile, llm_router=router),
        )

        await _update_resume_status(database, resume_id, ResumeStatus.scoring)
        embeddings = await _run_step(
            7,
            resume_id,
            lambda: generate_embeddings(resume_id=resume_id, candidate_profile=candidate_profile, job=job),
        )
        rag_result = await _run_step(
            8,
            resume_id,
            lambda: run_rag_pipeline(
                resume_id=resume_id,
                job_id=job_id,
                jd_text=embeddings["jd_text"],
                candidate_embedding=embeddings["candidate_embedding"],
            ),
        )
        evaluation = await _run_step(
            9,
            resume_id,
            lambda: evaluate_candidate(
                resume_id=resume_id,
                candidate_profile=candidate_profile,
                job=job,
                rag_context=rag_result["context"],
                llm_router=router,
            ),
        )
        score_result = await _run_step(
            10,
            resume_id,
            lambda: score_candidate(candidate_profile=candidate_profile, job=job, evaluation=evaluation),
        )
        persisted = await _run_step(
            11,
            resume_id,
            lambda: persist_results(
                db=database,
                resume_id=resume_id,
                candidate_profile=candidate_profile,
                job_id=job_id,
                evaluation=evaluation,
                score_result=score_result,
                candidate_embedding_b64=embeddings["candidate_embedding_b64"],
                jd_embedding_b64=embeddings["jd_embedding_b64"],
            ),
        )
        logger.info(
            "[PIPELINE] Full pipeline complete | resume_id=%s | total_elapsed=%.2fs | score=%.2f",
            resume_id,
            time.perf_counter() - total_started,
            persisted["score"]["final_score"],
        )
    except JSONRepairError as exc:
        await _update_resume_status(database, resume_id, ResumeStatus.parse_failed, str(exc))
        logger.error("[ERROR] Pipeline failed during JSON parsing | resume_id=%s | error=%s", resume_id, exc)
    except Exception as exc:
        await _update_resume_status(database, resume_id, ResumeStatus.failed, str(exc))
        logger.error("[ERROR] Pipeline failed | resume_id=%s | error=%s", resume_id, exc)
