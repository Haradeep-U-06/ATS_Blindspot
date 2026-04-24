from typing import Any, Dict, List

from logger import get_logger

logger = get_logger(__name__)


def _structured_resume_summary(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "headline": candidate.get("summary", ""),
        "experience": candidate.get("experience", []),
        "projects": candidate.get("projects", []),
        "education": candidate.get("education", []),
        "certifications": candidate.get("certifications", []),
    }


def _score_breakdown(score: Dict[str, Any]) -> Dict[str, Any]:
    details = score.get("subscores_detail", {}) or {}
    return {
        "base_score": score.get("base_score", 0),
        "preferred_bonus": score.get("preferred_bonus", 0),
        "experience_score": score.get("experience_score", 0),
        "enrichment_score": score.get("enrichment_score", 0),
        "penalties": score.get("penalties", 0),
        "required_skill_score": score.get("base_score", 0),
        "preferred_skill_score": score.get("preferred_bonus", 0),
        "evidence_quality_score": score.get("experience_score", 0),
        "required_weighted_match": details.get("required_weighted_match", 0),
        "preferred_weighted_match": details.get("preferred_weighted_match", 0),
        "evidence_quality": details.get("evidence_quality", 0),
        "confidence_score": details.get("confidence_score", 0),
        "penalty_detail": details.get("penalty_detail", "none"),
        "formula": details.get("formula", {}),
    }


async def rank_candidates(
    *,
    db: Any,
    job_id: str,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    logger.info("[STEP 12] Ranking candidates for job | job_id=%s", job_id)
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    skip = (page - 1) * page_size
    total = await db.scores.count_documents({"job_id": job_id})
    logger.info("[INFO] Found %s candidates for this JD", total)

    cursor = db.scores.find({"job_id": job_id}).sort("final_score", -1).skip(skip).limit(page_size)
    scores: List[Dict[str, Any]] = await cursor.to_list(length=page_size)
    ranked = []
    for index, score in enumerate(scores, start=skip + 1):
        candidate = await db.candidates.find_one({"candidate_id": score["candidate_id"]}) or {}
        subscores_detail = score.get("subscores_detail", {}) or {}
        ranked.append(
            {
                "rank": index,
                "candidate_id": score["candidate_id"],
                "name": candidate.get("name", ""),
                "email": candidate.get("email", ""),
                "summary": candidate.get("summary", ""),
                "resume_summary": _structured_resume_summary(candidate),
                "skills": candidate.get("skills", []),
                "final_score": score.get("final_score", 0),
                "recommendation": score.get("recommendation"),
                "pros": score.get("strengths", []),
                "cons": score.get("gaps", []),
                "strengths": score.get("strengths", []),
                "gaps": score.get("gaps", []),
                "overall_explanation": score.get("overall_explanation", ""),
                "skill_scores": subscores_detail.get("skill_scores", []),
                "skill_matches": score.get("skill_matches", []),
                "score_breakdown": _score_breakdown(score),
            }
        )
    if ranked:
        logger.info(
            "[SUCCESS] Ranking complete | top_candidate=%s (%.1f) | bottom=%s (%.1f)",
            ranked[0]["name"],
            ranked[0]["final_score"],
            ranked[-1]["name"],
            ranked[-1]["final_score"],
        )
    else:
        logger.info("[SUCCESS] Ranking complete | no candidates yet")
    return {"job_id": job_id, "page": page, "page_size": page_size, "total": total, "candidates": ranked}
