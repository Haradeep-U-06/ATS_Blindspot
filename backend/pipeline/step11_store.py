import time
from typing import Any, Dict

from db.models import CandidateDocument, ResumeStatus, ScoreDocument, model_to_dict
from logger import get_logger

logger = get_logger(__name__)


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
        job_id=job_id,
        final_score=score_result.final_score,
        base_score=score_result.base_score,
        preferred_bonus=score_result.preferred_bonus,
        experience_score=score_result.experience_score,
        enrichment_score=score_result.enrichment_score,
        penalties=score_result.penalties,
        recommendation=evaluation.get("recommendation", "unknown"),
        strengths=evaluation.get("strengths", []),
        gaps=evaluation.get("gaps", []),
        skill_matches=evaluation.get("skill_matches", []),
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
