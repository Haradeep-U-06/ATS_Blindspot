import re
from typing import Any, Dict, List

from db.models import JobDocument, WeightedSkill, model_to_dict, new_id
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


def _skills_in_text(text: str, known_skills: List[str]) -> List[str]:
    lower = (text or "").lower()
    found = []
    for skill in known_skills:
        pattern = re.escape(skill.lower()).replace("\\ ", r"\s+")
        if re.search(rf"\b{pattern}\b", lower):
            found.append(skill)
    return found


def _labeled_skill_sections(jd_text: str, known_skills: List[str]) -> tuple[List[str], List[str]]:
    required_match = re.search(
        r"(?is)(?:required(?:\s+skills)?(?:\s+include)?|must[-\s]?have)\s*:?\s*"
        r"(.*?)(?=(?:preferred|nice[-\s]?to[-\s]?have|bonus)\s*:|\Z)",
        jd_text,
    )
    preferred_match = re.search(
        r"(?is)(?:preferred(?:\s+skills)?|nice[-\s]?to[-\s]?have|bonus)\s*:?\s*(.*?)(?=\Z)",
        jd_text,
    )
    required = _skills_in_text(required_match.group(1), known_skills) if required_match else []
    preferred = _skills_in_text(preferred_match.group(1), known_skills) if preferred_match else []
    preferred = [skill for skill in preferred if skill not in required]
    return required, preferred


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
    found = _skills_in_text(text, known_skills)
    required_source, preferred_source = _labeled_skill_sections(text, known_skills)
    if not required_source and not preferred_source:
        required_count = min(max(1, len(found) - 2), len(found)) if found else 0
        required_source = found[:required_count] if required_count else []
        preferred_source = found[required_count:] if found else []
    elif not required_source:
        required_source = [skill for skill in found if skill not in preferred_source]
    elif not preferred_source:
        preferred_source = [skill for skill in found if skill not in required_source and skill not in preferred_source]

    required = [{"skill": skill, "weight": 1.0 / len(required_source)} for skill in required_source] if required_source else []
    preferred = [{"skill": skill, "weight": 1.0 / len(preferred_source)} for skill in preferred_source] if preferred_source else []

    exp_match = re.search(r"(\d+)\+?\s*(?:years|yrs)", lower)
    experience_years_min = int(exp_match.group(1)) if exp_match else 0

    title = "Backend Engineer" if "backend" in lower else "Software Engineer"
    if "frontend" in lower:
        title = "Frontend Engineer"
    if "full stack" in lower or "fullstack" in lower:
        title = "Full Stack Engineer"
    if "data" in lower:
        title = "Data Engineer"

    tech_ratio = 1.0 if found else 0.0

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


async def create_job_record(
    *,
    jd_text: str,
    db: Any,
    hr_user_id: str = "default_hr",
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    logger.info("[INFO] JD uploaded")
    logger.info("[STEP] Structuring JD tech stack before opening applications")
    job = await process_job_description(
        jd_text=jd_text,
        db=db,
        hr_user_id=hr_user_id,
        llm_router=llm_router,
        application_window_closed=False,
        evaluation_status="not_started",
    )
    logger.info("[SUCCESS] JD stored | job_id=%s | status=%s", job["job_id"], job["evaluation_status"])
    return job


async def process_job_description(
    *,
    jd_text: str,
    db: Any,
    hr_user_id: str = "default_hr",
    job_id: str | None = None,
    llm_router: LLMRouter | None = None,
    application_window_closed: bool | None = None,
    evaluation_status: str = "processing",
) -> Dict[str, Any]:
    logger.info("[STEP 6] Processing Job Description for evaluation...")
    logger.info("[INFO] JD text length: %s chars", len(jd_text or ""))
    router = llm_router or LLMRouter()
    logger.info("[INFO] Calling LLM router for JD tech-stack structuring...")
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
        job_id=job_id or new_id("job"),
        hr_user_id=hr_user_id,
        title=parsed.get("title", "Untitled Role"),
        raw_jd_text=jd_text,
        required_skills=[WeightedSkill(**item) for item in parsed.get("required_skills", [])],
        preferred_skills=[WeightedSkill(**item) for item in parsed.get("preferred_skills", [])],
        experience_years_min=int(parsed.get("experience_years_min", 0) or 0),
        domain=parsed.get("domain", ""),
        tech_vs_nontechnical_ratio=float(parsed.get("tech_vs_nontechnical_ratio", 1.0) or 1.0),
        key_responsibilities=parsed.get("key_responsibilities", []),
        application_window_closed=application_window_closed if application_window_closed is not None else bool(job_id),
        evaluation_status=evaluation_status,
    )
    document = model_to_dict(job)
    if job_id:
        await db.jobs.update_one({"job_id": job_id}, {"$set": document})
    else:
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
