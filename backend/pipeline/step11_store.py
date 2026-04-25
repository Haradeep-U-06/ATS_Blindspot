import time
from typing import Any, Dict

from db.models import CandidateDocument, ResumeStatus, ScoreDocument, model_to_dict
from logger import get_logger

logger = get_logger(__name__)


async def persist_vectorized_candidate(
    *,
    db: Any,
    resume_id: str,
    job_id: str,
    raw_text: str,
    candidate_profile: Dict[str, Any],
    chunk_count: int,
) -> Dict[str, Any]:
    logger.info("[STEP 11] Persisting parsed/vectorized candidate | resume_id=%s", resume_id)
    existing_resume = await db.resumes.find_one({"resume_id": resume_id}) or {}
    candidate_id = existing_resume.get("candidate_id") or candidate_profile.get("candidate_id")
    candidate_doc = CandidateDocument(
        candidate_id=candidate_id or CandidateDocument(resume_id=resume_id).candidate_id,
        resume_id=resume_id,
        job_id=job_id,
        name=candidate_profile.get("name", ""),
        email=candidate_profile.get("email", ""),
        phone=candidate_profile.get("phone", ""),
        summary=candidate_profile.get("summary", ""),
        skills=candidate_profile.get("skills", []),
        experience=candidate_profile.get("experience", []),
        education=candidate_profile.get("education", []),
        projects=candidate_profile.get("projects", []),
        certifications=candidate_profile.get("certifications", []),
        github_username=candidate_profile.get("github_username"),
        leetcode_username=candidate_profile.get("leetcode_username"),
        codeforces_username=candidate_profile.get("codeforces_username"),
        codechef_username=candidate_profile.get("codechef_username"),
        external_links=candidate_profile.get("external_links", {}),
        github_data=candidate_profile.get("github_data", {}),
        leetcode_data=candidate_profile.get("leetcode_data", {}),
        codeforces_data=candidate_profile.get("codeforces_data", {}),
        codechef_data=candidate_profile.get("codechef_data", {}),
    )
    await db.candidates.update_one(
        {"candidate_id": candidate_doc.candidate_id},
        {"$set": model_to_dict(candidate_doc)},
        upsert=True,
    )
    await db.resumes.update_one(
        {"resume_id": resume_id},
        {
            "$set": {
                "candidate_id": candidate_doc.candidate_id,
                "job_id": job_id,
                "raw_text": raw_text,
                "chunk_count": chunk_count,
                "status": ResumeStatus.ready_for_evaluation.value,
                "error_message": None,
            }
        },
    )
    logger.info("[SUCCESS] Resume ready for evaluation | resume_id=%s | chunks=%s", resume_id, chunk_count)
    return {"candidate_id": candidate_doc.candidate_id, "resume_id": resume_id, "chunk_count": chunk_count}


async def persist_results(
    *,
    db: Any,
    resume_id: str,
    candidate_profile: Dict[str, Any],
    job_id: str,
    evaluation: Dict[str, Any],
    score_result: Any,
    candidate_embedding_b64: str | None = None,
    jd_embedding_b64: str | None = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    logger.info("[STEP 11] Persisting results to MongoDB...")
    existing_resume = await db.resumes.find_one({"resume_id": resume_id}) or {}
    candidate_id = existing_resume.get("candidate_id") or candidate_profile.get("candidate_id")

    candidate_doc = CandidateDocument(
        candidate_id=candidate_id or CandidateDocument(resume_id=resume_id).candidate_id,
        resume_id=resume_id,
        job_id=job_id,
        name=candidate_profile.get("name", ""),
        email=candidate_profile.get("email", ""),
        phone=candidate_profile.get("phone", ""),
        summary=candidate_profile.get("summary", ""),
        skills=candidate_profile.get("skills", []),
        experience=candidate_profile.get("experience", []),
        education=candidate_profile.get("education", []),
        projects=candidate_profile.get("projects", []),
        certifications=candidate_profile.get("certifications", []),
        github_username=candidate_profile.get("github_username"),
        leetcode_username=candidate_profile.get("leetcode_username"),
        codeforces_username=candidate_profile.get("codeforces_username"),
        codechef_username=candidate_profile.get("codechef_username"),
        external_links=candidate_profile.get("external_links", {}),
        github_data=candidate_profile.get("github_data", {}),
        leetcode_data=candidate_profile.get("leetcode_data", {}),
        codeforces_data=candidate_profile.get("codeforces_data", {}),
        codechef_data=candidate_profile.get("codechef_data", {}),
        embedding_b64=candidate_embedding_b64,
    )
    candidate_data = model_to_dict(candidate_doc)
    logger.info("[INFO] Upserting candidate | resume_id=%s", resume_id)
    await db.candidates.update_one(
        {"candidate_id": candidate_doc.candidate_id},
        {"$set": candidate_data},
        upsert=True,
    )

    score_doc = ScoreDocument(
        candidate_id=candidate_doc.candidate_id,
        resume_id=resume_id,
        job_id=job_id,
        final_score=score_result.final_score,
        ats_score=score_result.ats_score,
        rag_score=score_result.rag_score,
        keyword_score=score_result.keyword_score,
        confidence_score=score_result.confidence_score,
        base_score=score_result.base_score,
        preferred_bonus=score_result.preferred_bonus,
        experience_score=score_result.experience_score,
        problem_solving_score=score_result.problem_solving_score,
        consistency_score=score_result.consistency_score,
        penalties=score_result.penalties,
        recommendation=score_result.subscores_detail.get("recommendation", "unknown"),
        strengths=score_result.subscores_detail.get("matched_keywords", []),
        gaps=[],
        skill_matches=[],
        evidence_chunks={"top_chunks": score_result.subscores_detail.get("top_chunks", [])},
        overall_explanation="Determined mathematically via unified scoring pipeline.",
        subscores_detail={**score_result.subscores_detail, "jd_embedding_b64": jd_embedding_b64},
    )
    logger.info("[INFO] Writing score | score=%.2f | job_id=%s", score_doc.final_score, job_id)
    await db.scores.update_one(
        {"candidate_id": candidate_doc.candidate_id, "job_id": job_id},
        {"$set": model_to_dict(score_doc)},
        upsert=True,
    )

    logger.info("[INFO] Updating resume status -> completed")
    await db.resumes.update_one(
        {"resume_id": resume_id},
        {
            "$set": {
                "candidate_id": candidate_doc.candidate_id,
                "status": ResumeStatus.completed.value,
                "error_message": None,
            }
        },
    )
    logger.info("[SUCCESS] All documents persisted | elapsed=%.2fs", time.perf_counter() - started)
    return {"candidate_id": candidate_doc.candidate_id, "score": model_to_dict(score_doc)}
