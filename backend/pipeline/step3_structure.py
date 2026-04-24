import re
from typing import Any, Dict

from llm.exceptions import JSONRepairError, LLMUnavailableError
from llm.json_validator import parse_json_response
from llm.prompts import RESUME_STRUCTURE_PROMPT
from llm.router import LLMRouter
from logger import get_logger

logger = get_logger(__name__)


def _with_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    defaults = {
        "name": "",
        "email": "",
        "phone": "",
        "summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "github_username": None,
        "leetcode_username": None,
        "codeforces_username": None,
        "codechef_username": None,
    }
    defaults.update(data or {})
    return defaults


def _extract_username(text: str, service: str) -> str | None:
    patterns = {
        "github": [r"github\.com/([A-Za-z0-9-]+)", r"github[:\s]+([A-Za-z0-9-]+)"],
        "leetcode": [r"leetcode\.com/(?:u/)?([A-Za-z0-9_-]+)", r"leetcode[:\s]+([A-Za-z0-9_-]+)"],
        "codeforces": [r"codeforces\.com/profile/([A-Za-z0-9_-]+)", r"codeforces[:\s]+([A-Za-z0-9_-]+)"],
        "codechef": [r"codechef\.com/users/([A-Za-z0-9_-]+)", r"codechef[:\s]+([A-Za-z0-9_-]+)"],
    }
    for pattern in patterns.get(service, []):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip("/.")
    return None


def _fallback_structure_resume(raw_text: str) -> Dict[str, Any]:
    logger.warning("[WARN] LLM unavailable for resume structuring — using deterministic resume parser")
    text = raw_text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone_match = re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text)
    name = ""
    for line in lines[:8]:
        if "@" in line or re.search(r"\d{3,}", line):
            continue
        words = re.findall(r"[A-Za-z][A-Za-z.'-]*", line)
        if 1 <= len(words) <= 5:
            name = " ".join(words)
            break

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
        "Git",
        "GitHub",
    ]
    lower = text.lower()
    skills = []
    for skill in known_skills:
        pattern = re.escape(skill.lower()).replace("\\ ", r"\s+")
        if re.search(rf"\b{pattern}\b", lower):
            skills.append(skill)

    summary = " ".join(lines[:4])[:500] if lines else text[:500]
    projects = []
    if "project" in lower:
        projects.append(
            {
                "name": "Resume Project",
                "description": "Project details extracted from resume text.",
                "tech_stack": skills[:8],
                "url": None,
            }
        )

    return _with_defaults(
        {
            "name": name,
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0).strip() if phone_match else "",
            "summary": summary,
            "skills": skills,
            "experience": [
                {
                    "company": "",
                    "role": "",
                    "duration": "",
                    "description": summary,
                }
            ]
            if summary
            else [],
            "education": [],
            "projects": projects,
            "certifications": [],
            "github_username": _extract_username(text, "github"),
            "leetcode_username": _extract_username(text, "leetcode"),
            "codeforces_username": _extract_username(text, "codeforces"),
            "codechef_username": _extract_username(text, "codechef"),
        }
    )


async def structure_resume(
    *,
    resume_id: str,
    raw_text: str,
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 3] Structuring resume with LLM...")
    router = llm_router or LLMRouter()
    prompt = RESUME_STRUCTURE_PROMPT.format(resume_text=raw_text[:15000])
    logger.debug("[DEBUG] Prompt sent | tokens_estimate=%s", max(1, len(prompt) // 4))
    try:
        response = await router.generate(prompt, task="structuring")
        parsed = await parse_json_response(
            response,
            repair_callback=lambda repair_prompt: router.generate(repair_prompt, task="repair"),
            resume_id=resume_id,
        )
    except (LLMUnavailableError, JSONRepairError) as exc:
        logger.warning("[WARN] Resume LLM structuring failed — fallback active | resume_id=%s | error=%s", resume_id, exc)
        parsed = _fallback_structure_resume(raw_text)
    structured = _with_defaults(parsed)
    logger.info(
        "[SUCCESS] Valid JSON received | sections=%s | skills_count=%s",
        len(structured.keys()),
        len(structured.get("skills", [])),
    )
    logger.debug(
        "[DEBUG] github_username=%s | leetcode_username=%s",
        structured.get("github_username"),
        structured.get("leetcode_username"),
    )
    return structured
