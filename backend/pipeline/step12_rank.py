from typing import Any, Dict, List

from logger import get_logger

logger = get_logger(__name__)


def _structured_resume_summary(candidate: Dict[str, Any]) -> str:
    """Build a plain-text resume summary string for frontend rendering."""
    parts = []

    headline = candidate.get("summary", "")
    if headline:
        parts.append(headline)

    experience = candidate.get("experience", [])
    if experience:
        exp_lines = []
        for e in experience[:3]:
            if isinstance(e, dict):
                title = e.get("title") or e.get("role") or ""
                company = e.get("company") or e.get("employer") or ""
                duration = e.get("duration") or e.get("dates") or e.get("period") or ""
                line = " | ".join(filter(None, [title, company, duration]))
            else:
                line = str(e)
            if line:
                exp_lines.append(line)
        if exp_lines:
            parts.append("Experience: " + "; ".join(exp_lines))

    projects = candidate.get("projects", [])
    if projects:
        proj_names = []
        for p in projects[:3]:
            if isinstance(p, dict):
                proj_names.append(p.get("name") or p.get("title") or "")
            else:
                proj_names.append(str(p))
        proj_names = [n for n in proj_names if n]
        if proj_names:
            parts.append("Projects: " + ", ".join(proj_names))

    education = candidate.get("education", [])
    if education:
        edu_lines = []
        for edu in education[:2]:
            if isinstance(edu, dict):
                degree = edu.get("degree") or ""
                institution = edu.get("institution") or edu.get("school") or ""
                line = " from ".join(filter(None, [degree, institution]))
            else:
                line = str(edu)
            if line:
                edu_lines.append(line)
        if edu_lines:
            parts.append("Education: " + "; ".join(edu_lines))

    certifications = candidate.get("certifications", [])
    if certifications:
        cert_names = []
        for c in certifications[:3]:
            if isinstance(c, dict):
                cert_names.append(c.get("name") or c.get("title") or "")
            else:
                cert_names.append(str(c))
        cert_names = [n for n in cert_names if n]
        if cert_names:
            parts.append("Certifications: " + ", ".join(cert_names))

    return " | ".join(parts) if parts else ""


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
