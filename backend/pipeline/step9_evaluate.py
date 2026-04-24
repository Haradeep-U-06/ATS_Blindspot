import json
from typing import Any, Dict

from llm.exceptions import JSONRepairError, LLMUnavailableError
from llm.json_validator import parse_json_response
from llm.prompts import EVALUATION_PROMPT
from llm.router import LLMRouter
from logger import get_logger

logger = get_logger(__name__)


def _skill_names(items: list[Any]) -> set[str]:
    names = set()
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("skill", "")
        else:
            value = item
        if value:
            names.add(str(value).strip().lower())
    return names


def _fallback_evaluate_candidate(candidate_profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    logger.warning("[WARN] LLM unavailable for contextual evaluation — using deterministic evaluator")
    candidate_skills = _skill_names(candidate_profile.get("skills", []))
    required = job.get("required_skills", []) or []
    preferred = job.get("preferred_skills", []) or []
    skill_matches = []
    matched_required = 0
    for item in required + preferred:
        skill = str(item.get("skill", "")).strip()
        has_skill = skill.lower() in candidate_skills
        if has_skill and item in required:
            matched_required += 1
        skill_matches.append(
            {
                "skill": skill,
                "candidate_has": has_skill,
                "confidence": 0.85 if has_skill else 0.0,
                "notes": "Matched from parsed resume skills" if has_skill else "Not found in parsed resume skills",
            }
        )

    required_count = max(1, len(required))
    required_ratio = matched_required / required_count
    experience_match = {
        "years_required": int(job.get("experience_years_min", 0) or 0),
        "years_candidate": 0,
        "match_score": 0.7 if required_ratio >= 0.5 else 0.35,
    }
    if required_ratio >= 0.8:
        recommendation = "strong_fit"
    elif required_ratio >= 0.5:
        recommendation = "moderate_fit"
    elif required_ratio > 0:
        recommendation = "weak_fit"
    else:
        recommendation = "no_fit"

    strengths = [item["skill"] for item in skill_matches if item["candidate_has"]][:5]
    gaps = [item["skill"] for item in skill_matches if not item["candidate_has"]][:5]
    return {
        "overall_match_summary": (
            f"Deterministic evaluation found {matched_required}/{len(required)} required skills. "
            "This score was generated without an LLM because no provider was available."
        ),
        "skill_matches": skill_matches,
        "experience_match": experience_match,
        "strengths": strengths,
        "gaps": gaps,
        "recommendation": recommendation,
        "confidence": 0.65,
    }


async def evaluate_candidate(
    *,
    resume_id: str,
    candidate_profile: Dict[str, Any],
    job: Dict[str, Any],
    rag_context: str,
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 9] Evaluating candidate against JD...")
    logger.info("[INFO] Context: %s RAG chunks + full candidate profile", rag_context.count("\n\n") + 1 if rag_context else 0)
    router = llm_router or LLMRouter()
    logger.info("[INFO] Calling Gemini for contextual evaluation...")
    try:
        response = await router.generate(
            EVALUATION_PROMPT.format(
                candidate_profile=json.dumps(candidate_profile, default=str),
                job_description=json.dumps(job, default=str),
                rag_context=rag_context,
            ),
            task="evaluation",
        )
        evaluation = await parse_json_response(
            response,
            repair_callback=lambda repair_prompt: router.generate(repair_prompt, task="repair"),
            resume_id=resume_id,
        )
    except (LLMUnavailableError, JSONRepairError) as exc:
        logger.warning("[WARN] Candidate LLM evaluation failed — fallback active | resume_id=%s | error=%s", resume_id, exc)
        evaluation = _fallback_evaluate_candidate(candidate_profile, job)
    logger.info("[SUCCESS] Evaluation complete | recommendation=%s", evaluation.get("recommendation"))
    skill_matches = evaluation.get("skill_matches", []) or []
    matched = sum(1 for item in skill_matches if item.get("candidate_has"))
    logger.debug(
        "[DEBUG] skill_matches=%s/%s | experience_match=%s",
        matched,
        len(skill_matches),
        (evaluation.get("experience_match") or {}).get("match_score"),
    )
    return evaluation
