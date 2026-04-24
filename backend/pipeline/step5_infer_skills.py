import json
from typing import Any, Dict, List

from llm.json_validator import parse_json_response
from llm.prompts import SKILL_INFERENCE_PROMPT
from llm.router import LLMRouter
from logger import get_logger

logger = get_logger(__name__)


def _explicit_skill_items(skills: List[Any]) -> List[Dict[str, Any]]:
    items = []
    for item in skills or []:
        if isinstance(item, dict):
            skill = item.get("skill")
            source = item.get("source", "resume")
            confidence = item.get("confidence", 1.0)
        else:
            skill = str(item)
            source = "resume"
            confidence = 1.0
        if skill:
            items.append({"skill": str(skill), "source": source, "confidence": float(confidence)})
    return items


async def infer_skills(
    *,
    resume_id: str,
    candidate_profile: Dict[str, Any],
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 5] Inferring skills from enriched profile...")
    router = llm_router or LLMRouter()
    explicit = _explicit_skill_items(candidate_profile.get("skills", []))
    context = {
        "skills": explicit,
        "projects": candidate_profile.get("projects", []),
        "experience": candidate_profile.get("experience", []),
        "github_data": candidate_profile.get("github_data", {}),
        "leetcode_data": candidate_profile.get("leetcode_data", {}),
    }
    logger.debug(
        "[DEBUG] Input context: %s explicit skills + %s GitHub repos + %s projects",
        len(explicit),
        len((candidate_profile.get("github_data") or {}).get("top_repositories", [])),
        len(candidate_profile.get("projects", [])),
    )
    try:
        response = await router.generate(
            SKILL_INFERENCE_PROMPT.format(candidate_context=json.dumps(context, default=str)),
            task="skill_inference",
        )
        inferred = await parse_json_response(
            response,
            repair_callback=lambda repair_prompt: router.generate(repair_prompt, task="repair"),
            resume_id=resume_id,
        )
    except Exception as exc:
        logger.warning("[WARN] Skill inference failed — continuing with explicit skills | resume_id=%s | error=%s", resume_id, exc)
        inferred = []

    seen = {item["skill"].strip().lower() for item in explicit}
    merged = list(explicit)
    accepted = []
    for item in inferred or []:
        skill = str(item.get("skill", "")).strip()
        confidence = float(item.get("confidence", 0.0) or 0.0)
        if not skill or confidence < 0.6 or skill.lower() in seen:
            continue
        merged.append(
            {
                "skill": skill,
                "source": item.get("source", "experience"),
                "confidence": confidence,
            }
        )
        accepted.append((skill, confidence))
        seen.add(skill.lower())

    top = ", ".join(f"{skill}({confidence:.2f})" for skill, confidence in accepted[:3])
    logger.info("[SUCCESS] Inferred %s additional skills | top: %s", len(accepted), top or "none")
    logger.info("[INFO] Final skill count: %s (%s explicit + %s inferred)", len(merged), len(explicit), len(accepted))
    candidate_profile["skills"] = merged
    return candidate_profile
