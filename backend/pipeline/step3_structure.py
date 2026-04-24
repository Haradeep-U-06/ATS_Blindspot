import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from logger import get_logger

logger = get_logger(__name__)


KNOWN_TECH_SKILLS = [
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
    "HTML",
    "CSS",
    "Tailwind",
    "Next.js",
    "Express",
]


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
        "external_links": {},
    }
    defaults.update(data or {})
    return defaults


def _username_from_link(link: Optional[str], service: str) -> Optional[str]:
    if not link:
        return None
    value = link.strip().rstrip("/")
    if not value:
        return None
    if "://" not in value and "." not in value:
        return value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return None
    if service == "leetcode" and path_parts[0] == "u" and len(path_parts) > 1:
        return path_parts[1]
    if service == "codeforces" and path_parts[0] == "profile" and len(path_parts) > 1:
        return path_parts[1]
    if service == "codechef" and path_parts[0] == "users" and len(path_parts) > 1:
        return path_parts[1]
    return path_parts[0]


def _extract_section(text: str, headings: list[str], max_chars: int = 900) -> str:
    heading_pattern = "|".join(re.escape(heading) for heading in headings)
    match = re.search(
        rf"(?is)(?:^|\n)\s*(?:{heading_pattern})\s*:?\s*\n?(.*?)(?=\n\s*[A-Z][A-Za-z /&-]{{2,}}\s*:?\s*\n|\Z)",
        text,
    )
    return (match.group(1).strip()[:max_chars] if match else "")


def _extract_explicit_skills(text: str) -> list[Dict[str, Any]]:
    lower = text.lower()
    skills = []
    for skill in KNOWN_TECH_SKILLS:
        pattern = re.escape(skill.lower()).replace("\\ ", r"\s+")
        if re.search(rf"\b{pattern}\b", lower):
            skills.append({"skill": skill, "source": "resume_explicit", "confidence": 1.0})
    return skills


async def structure_resume(
    *,
    resume_id: str,
    raw_text: str,
    external_links: Optional[Dict[str, Optional[str]]] = None,
    llm_router: Any | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 3] Structuring resume deterministically | resume_id=%s", resume_id)
    if llm_router is not None:
        logger.info("[INFO] Resume structuring ignores LLM router by design | resume_id=%s", resume_id)

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

    external_links = external_links or {}
    summary = " ".join(lines[:5])[:700] if lines else text[:700]
    experience_text = _extract_section(text, ["experience", "work experience", "employment"])
    projects_text = _extract_section(text, ["projects", "project experience"])
    education_text = _extract_section(text, ["education", "academics"])

    profile = _with_defaults(
        {
            "name": name,
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0).strip() if phone_match else "",
            "summary": summary,
            "skills": _extract_explicit_skills(text),
            "experience": [
                {"company": "", "role": "", "duration": "", "description": experience_text}
            ]
            if experience_text
            else [],
            "education": [
                {"institution": "", "degree": education_text[:300], "year": ""}
            ]
            if education_text
            else [],
            "projects": [
                {"name": "Resume Project Evidence", "description": projects_text, "tech_stack": [], "url": None}
            ]
            if projects_text
            else [],
            "certifications": [],
            "github_username": _username_from_link(external_links.get("github"), "github"),
            "leetcode_username": _username_from_link(external_links.get("leetcode"), "leetcode"),
            "codeforces_username": _username_from_link(external_links.get("codeforces"), "codeforces"),
            "codechef_username": _username_from_link(external_links.get("codechef"), "codechef"),
            "external_links": external_links,
        }
    )
    logger.info(
        "[SUCCESS] Resume structured without LLM | resume_id=%s | explicit_skills=%s",
        resume_id,
        len(profile["skills"]),
    )
    return profile
