import re
from typing import Any, Dict, List

from db.models import JobDocument, WeightedSkill, model_to_dict
from llm.exceptions import LLMUnavailableError
from llm.json_validator import JSONRepairError
from llm.json_validator import parse_json_response
from llm.prompts import JD_STRUCTURE_PROMPT
from llm.router import LLMRouter
from logger import get_logger

logger = get_logger(__name__)


def _normalize_weights(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for item in items or []:
        skill = str(item.get("skill", "")).strip()
        if skill:
            cleaned.append({"skill": skill, "weight": float(item.get("weight", 0.0) or 0.0)})
    if not cleaned:
        return []
    total = sum(item["weight"] for item in cleaned)
    if total <= 0:
        equal = 1.0 / len(cleaned)
        return [{**item, "weight": equal} for item in cleaned]
    return [{**item, "weight": item["weight"] / total} for item in cleaned]


def _fallback_process_jd(jd_text: str) -> Dict[str, Any]:
    logger.warning("[WARN] LLM unavailable for JD structuring — using deterministic JD parser")
    text = jd_text or ""
    lower = text.lower()
    known_skills = [
        "Python",
        "FastAPI",
        "Django",
        "Flask",
        "MongoDB",
        "PostgreSQL",
        "MySQL",
        "SQL",
        "REST APIs",
        "GraphQL",
        "Docker",
        "Kubernetes",
        "AWS",
        "Azure",
        "GCP",
        "CI/CD",
        "Redis",
        "Celery",
        "React",
        "Node.js",
        "JavaScript",
        "TypeScript",
        "Java",
        "Spring Boot",
        "Machine Learning",
        "LangChain",
        "FAISS",
    ]
    found = []
    for skill in known_skills:
        pattern = re.escape(skill.lower()).replace("\\ ", r"\s+")
        if re.search(rf"\b{pattern}\b", lower):
            found.append(skill)

    if not found:
        found = ["Communication", "Problem Solving"]

    required_count = min(max(1, len(found) - 2), len(found))
    required = [{"skill": skill, "weight": 1.0 / required_count} for skill in found[:required_count]]
    preferred_source = found[required_count:] or found[:1]
    preferred = [{"skill": skill, "weight": 1.0 / len(preferred_source)} for skill in preferred_source]

    exp_match = re.search(r"(\d+)\+?\s*(?:years|yrs)", lower)
    experience_years_min = int(exp_match.group(1)) if exp_match else 0

    title = "Backend Engineer" if "backend" in lower else "Software Engineer"
    if "frontend" in lower:
        title = "Frontend Engineer"
    if "full stack" in lower or "fullstack" in lower:
        title = "Full Stack Engineer"
    if "data" in lower:
        title = "Data Engineer"

    technical_hits = len([skill for skill in found if skill not in {"Communication", "Problem Solving"}])
    tech_ratio = 0.85 if technical_hits else 0.35

    return {
        "title": title,
        "required_skills": required,
        "preferred_skills": preferred,
        "experience_years_min": experience_years_min,
        "domain": title.replace(" Engineer", " Engineering"),
        "tech_vs_nontechnical_ratio": tech_ratio,
        "key_responsibilities": [
            "Deliver role responsibilities described in the job description",
            "Collaborate with team members and maintain production-quality work",
        ],
    }


async def process_job_description(
    *,
    jd_text: str,
    db: Any,
    hr_user_id: str = "default_hr",
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 6] Processing Job Description...")
    logger.info("[INFO] JD text length: %s chars", len(jd_text or ""))
    router = llm_router or LLMRouter()
    logger.info("[INFO] Calling Gemini for JD structuring...")
    try:
        response = await router.generate(JD_STRUCTURE_PROMPT.format(jd_text=jd_text), task="jd_structuring")
        parsed = await parse_json_response(
            response,
            repair_callback=lambda repair_prompt: router.generate(repair_prompt, task="repair"),
        )
    except (LLMUnavailableError, JSONRepairError) as exc:
        logger.warning("[WARN] JD LLM parsing failed — fallback active | error=%s", exc)
        parsed = _fallback_process_jd(jd_text)
    parsed["required_skills"] = _normalize_weights(parsed.get("required_skills", []))
    parsed["preferred_skills"] = _normalize_weights(parsed.get("preferred_skills", []))
    job = JobDocument(
        hr_user_id=hr_user_id,
        title=parsed.get("title", "Untitled Role"),
        raw_jd_text=jd_text,
        required_skills=[WeightedSkill(**item) for item in parsed.get("required_skills", [])],
        preferred_skills=[WeightedSkill(**item) for item in parsed.get("preferred_skills", [])],
        experience_years_min=int(parsed.get("experience_years_min", 0) or 0),
        domain=parsed.get("domain", ""),
        tech_vs_nontechnical_ratio=float(parsed.get("tech_vs_nontechnical_ratio", 1.0) or 1.0),
        key_responsibilities=parsed.get("key_responsibilities", []),
    )
    document = model_to_dict(job)
    await db.jobs.insert_one(document)
    logger.info(
        "[SUCCESS] JD parsed | title=%s | required_skills=%s | preferred_skills=%s",
        job.title,
        len(job.required_skills),
        len(job.preferred_skills),
    )
    logger.debug(
        "[DEBUG] tech_ratio=%.2f | min_experience=%s years",
        job.tech_vs_nontechnical_ratio,
        job.experience_years_min,
    )
    logger.info("[INFO] JD stored | job_id=%s", job.job_id)
    return document
