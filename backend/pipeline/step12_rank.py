from typing import Any, Dict, List

from logger import get_logger

logger = get_logger(__name__)


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
        ranked.append(
            {
                "rank": index,
                "candidate_id": score["candidate_id"],
                "name": candidate.get("name", ""),
                "email": candidate.get("email", ""),
                "summary": candidate.get("summary", ""),
                "skills": candidate.get("skills", []),
                "final_score": score.get("final_score", 0),
                "recommendation": score.get("recommendation"),
                "score_breakdown": {
                    "base_score": score.get("base_score", 0),
                    "preferred_bonus": score.get("preferred_bonus", 0),
                    "experience_score": score.get("experience_score", 0),
                    "enrichment_score": score.get("enrichment_score", 0),
                    "penalties": score.get("penalties", 0),
                },
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
