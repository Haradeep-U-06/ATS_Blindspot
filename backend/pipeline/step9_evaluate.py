import json
import re
from typing import Any, Dict, List

from llm.exceptions import JSONRepairError, LLMUnavailableError
from llm.json_validator import parse_json_response
from llm.prompts import EVALUATION_PROMPT
from llm.router import LLMRouter
from logger import get_logger
from pipeline.step8_rag import jd_tech_skills

logger = get_logger(__name__)


def _source_quality(source: str) -> float:
    if source == "work_experience":
        return 0.95
    if source == "projects":
        return 0.9
    if source in {"github", "leetcode", "codeforces", "codechef"}:
        return 0.85
    if source in {"resume_raw", "resume_skills", "resume_summary"}:
        return 0.65
    return 0.5


def _skill_pattern(skill: str) -> re.Pattern[str]:
    escaped = re.escape(skill.lower()).replace("\\ ", r"\s+")
    return re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)


SKILL_ALIASES = {
    "restapis": {"restapi", "restfulapi", "restfulapis"},
    "nodejs": {"node"},
    "postgresql": {"postgres"},
    "mongodb": {"mongo"},
    "cicd": {"continuousintegration", "continuousdeployment", "continuousdelivery"},
    "aws": {"amazonwebservices"},
}


def _skill_key(skill: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (skill or "").lower())


def _skill_keys(skill: str) -> set[str]:
    key = _skill_key(skill)
    aliases = SKILL_ALIASES.get(key, set())
    reverse_aliases = {canonical for canonical, values in SKILL_ALIASES.items() if key in values}
    return {item for item in {key, *aliases, *reverse_aliases} if item}


def _candidate_skill_confidence(candidate_profile: Dict[str, Any]) -> Dict[str, float]:
    skills: Dict[str, float] = {}
    for item in candidate_profile.get("skills", []) or []:
        if isinstance(item, dict):
            skill = str(item.get("skill", "")).strip()
            confidence = float(item.get("confidence", 1.0) or 1.0)
        else:
            skill = str(item).strip()
            confidence = 1.0
        if not skill:
            continue
        for key in _skill_keys(skill):
            skills[key] = max(skills.get(key, 0.0), min(1.0, confidence))
    return skills


def _candidate_skill_evidence(skill: str, candidate_skills: Dict[str, float]) -> Dict[str, Any] | None:
    confidence = max((candidate_skills.get(key, 0.0) for key in _skill_keys(skill)), default=0.0)
    if confidence <= 0:
        confidence = None
    if confidence is None:
        return None
    return {
        "chunk_id": None,
        "source": "resume_skills",
        "text": f"Candidate profile explicitly lists skill: {skill}",
        "similarity": 1.0,
        "confidence": confidence,
    }


def _fallback_evaluate_candidate(job: Dict[str, Any], rag_evidence: Dict[str, Any], candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
    logger.warning("[WARN] LLM unavailable for evaluation — using evidence-only deterministic evaluator")
    evidence_by_skill = rag_evidence.get("evidence_by_skill", {}) if rag_evidence else {}
    candidate_skills = _candidate_skill_confidence(candidate_profile)
    skill_matches = []
    matched_required = 0
    required_skills = {item["skill"].lower() for item in jd_tech_skills(job) if item["requirement_type"] == "required"}

    for item in jd_tech_skills(job):
        skill = item["skill"]
        pattern = _skill_pattern(skill)
        matching_chunks = []
        sources = []
        for chunk in evidence_by_skill.get(skill, []) or []:
            text = chunk.get("text", "")
            source = (chunk.get("metadata") or {}).get("source_type", "unknown")
            if pattern.search(text):
                matching_chunks.append(
                    {
                        "chunk_id": (chunk.get("metadata") or {}).get("chunk_id"),
                        "source": source,
                        "text": text[:500],
                        "similarity": chunk.get("similarity", 0),
                    }
                )
                sources.append(source)
        explicit_skill_evidence = _candidate_skill_evidence(skill, candidate_skills)
        if explicit_skill_evidence:
            matching_chunks.append(explicit_skill_evidence)
            sources.append("resume_skills")
        has_skill = bool(matching_chunks)
        if has_skill and skill.lower() in required_skills:
            matched_required += 1
        confidence = min(
            0.95,
            max(
                [
                    *(_source_quality(source) for source in sources),
                    *(min(0.9, float(evidence.get("confidence", 0.0) or 0.0)) for evidence in matching_chunks),
                ],
                default=0.0,
            ),
        )
        skill_matches.append(
            {
                "skill": skill,
                "candidate_has": has_skill,
                "confidence": confidence if has_skill else 0.0,
                "notes": "Explicit chunk evidence found" if has_skill else "No explicit evidence found in retrieved chunks",
                "evidence": matching_chunks[:3],
                "evidence_sources": sorted(set(sources)),
                "requirement_type": item["requirement_type"],
            }
        )

    required_count = max(1, len(required_skills))
    required_ratio = matched_required / required_count
    recommendation = "strong_fit" if required_ratio >= 0.8 else "moderate_fit" if required_ratio >= 0.5 else "weak_fit" if required_ratio > 0 else "no_fit"
    strengths = [item["skill"] for item in skill_matches if item["candidate_has"]][:5]
    gaps = [item["skill"] for item in skill_matches if not item["candidate_has"]][:5]
    return {
        "overall_match_summary": f"Evidence-only evaluation matched {matched_required}/{len(required_skills)} required technical skills.",
        "skill_matches": skill_matches,
        "experience_match": {
            "years_required": int(job.get("experience_years_min", 0) or 0),
            "years_candidate": 0,
            "match_score": required_ratio,
        },
        "strengths": strengths,
        "gaps": gaps,
        "recommendation": recommendation,
        "confidence": 0.75 if any(item["candidate_has"] for item in skill_matches) else 0.35,
    }


def _matches_by_skill(received: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_skill: Dict[str, Dict[str, Any]] = {}
    for item in received:
        skill = str(item.get("skill", "")).strip()
        if not skill:
            continue
        for key in _skill_keys(skill):
            by_skill.setdefault(key, item)
    return by_skill


def _recommendation_from_matches(matches: List[Dict[str, Any]]) -> str:
    required = [item for item in matches if item.get("requirement_type") == "required"]
    scored = required or matches
    if not scored:
        return "no_fit"
    matched_ratio = sum(1 for item in scored if item.get("candidate_has")) / len(scored)
    if matched_ratio >= 0.8:
        return "strong_fit"
    if matched_ratio >= 0.5:
        return "moderate_fit"
    if matched_ratio > 0:
        return "weak_fit"
    return "no_fit"


def _match_summary(matches: List[Dict[str, Any]]) -> str:
    required = [item for item in matches if item.get("requirement_type") == "required"]
    preferred = [item for item in matches if item.get("requirement_type") == "preferred"]
    required_hits = sum(1 for item in required if item.get("candidate_has"))
    preferred_hits = sum(1 for item in preferred if item.get("candidate_has"))
    return (
        f"Matched {required_hits}/{len(required)} required technical skills and "
        f"{preferred_hits}/{len(preferred)} preferred skills using resume, project, work, and profile evidence."
    )


def _normalize_evaluation(
    evaluation: Dict[str, Any],
    job: Dict[str, Any],
    rag_evidence: Dict[str, Any],
    candidate_profile: Dict[str, Any],
) -> Dict[str, Any]:
    evidence_by_skill = rag_evidence.get("evidence_by_skill", {}) if rag_evidence else {}
    candidate_skills = _candidate_skill_confidence(candidate_profile)
    normalized_matches = []
    received = evaluation.get("skill_matches", []) or []
    by_skill = _matches_by_skill(received)

    for jd_item in jd_tech_skills(job):
        item = dict(next((by_skill[key] for key in _skill_keys(jd_item["skill"]) if key in by_skill), {}))
        chunks = evidence_by_skill.get(jd_item["skill"], []) or []
        pattern = _skill_pattern(jd_item["skill"])
        supporting_chunks = [chunk for chunk in chunks if pattern.search(chunk.get("text", ""))]
        item["skill"] = jd_item["skill"]
        item["requirement_type"] = jd_item["requirement_type"]
        item["candidate_has"] = bool(item.get("candidate_has"))
        item["confidence"] = float(item.get("confidence", 0.0) or 0.0) if item["candidate_has"] else 0.0
        item["evidence"] = item.get("evidence") or []
        item["evidence_sources"] = item.get("evidence_sources") or []

        if not item["candidate_has"] and supporting_chunks:
            item["candidate_has"] = True
            item["confidence"] = min(
                0.9,
                max(
                    (
                        _source_quality((chunk.get("metadata") or {}).get("source_type", "unknown"))
                        for chunk in supporting_chunks
                    ),
                    default=0.0,
                ),
            )
            item["notes"] = "Explicit chunk evidence found after validation"
            item["evidence"] = [
                {
                    "chunk_id": (chunk.get("metadata") or {}).get("chunk_id"),
                    "source": (chunk.get("metadata") or {}).get("source_type", "unknown"),
                    "text": chunk.get("text", "")[:500],
                    "similarity": chunk.get("similarity", 0),
                }
                for chunk in supporting_chunks[:3]
            ]
            item["evidence_sources"] = sorted({evidence.get("source", "unknown") for evidence in item["evidence"]})
        if item["candidate_has"] and not item["evidence"] and supporting_chunks:
            item["evidence"] = [
                {
                    "chunk_id": (chunk.get("metadata") or {}).get("chunk_id"),
                    "source": (chunk.get("metadata") or {}).get("source_type", "unknown"),
                    "text": chunk.get("text", "")[:500],
                    "similarity": chunk.get("similarity", 0),
                }
                for chunk in supporting_chunks[:3]
            ]
            item["evidence_sources"] = sorted(
                {
                    evidence.get("source", "unknown")
                    for evidence in item["evidence"]
                }
            )
        explicit_skill_evidence = _candidate_skill_evidence(jd_item["skill"], candidate_skills)
        if explicit_skill_evidence and not item["candidate_has"]:
            item["candidate_has"] = True
            item["confidence"] = max(item.get("confidence", 0.0), min(0.9, explicit_skill_evidence["confidence"]))
            item["notes"] = item.get("notes") or "Explicit skill found in structured candidate profile"
        if explicit_skill_evidence and not item["evidence"]:
            item["evidence"] = [explicit_skill_evidence]
        if explicit_skill_evidence and "resume_skills" not in item["evidence_sources"]:
            item["evidence_sources"] = sorted({*item["evidence_sources"], "resume_skills"})
        if item["candidate_has"] and not item["evidence"]:
            item["candidate_has"] = False
            item["confidence"] = 0.0
            item["notes"] = "No explicit chunk evidence found after validation"
            item["evidence_sources"] = []
        normalized_matches.append(item)

    evaluation["skill_matches"] = normalized_matches
    evaluation["overall_match_summary"] = _match_summary(normalized_matches)
    evaluation["strengths"] = [item["skill"] for item in normalized_matches if item["candidate_has"]][:5]
    evaluation["gaps"] = [item["skill"] for item in normalized_matches if not item["candidate_has"]][:5]
    evaluation["recommendation"] = _recommendation_from_matches(normalized_matches)
    if normalized_matches:
        average_confidence = sum(float(item.get("confidence", 0.0) or 0.0) for item in normalized_matches) / len(normalized_matches)
        evaluation["confidence"] = max(float(evaluation.get("confidence", 0.0) or 0.0), min(0.95, average_confidence))
    else:
        evaluation.setdefault("confidence", 0.5)
    evaluation.setdefault(
        "experience_match",
        {"years_required": int(job.get("experience_years_min", 0) or 0), "years_candidate": 0, "match_score": 0.0},
    )
    return evaluation


async def evaluate_candidate(
    *,
    resume_id: str,
    candidate_profile: Dict[str, Any],
    job: Dict[str, Any],
    rag_context: str = "",
    rag_evidence: Dict[str, Any] | None = None,
    llm_router: LLMRouter | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 9] Evaluating candidate against JD tech stack | resume_id=%s", resume_id)
    logger.info("[INFO] Context chunks supplied to LLM: %s", rag_context.count("\n\n") + 1 if rag_context else 0)
    router = llm_router or LLMRouter()
    try:
        response = await router.generate(
            EVALUATION_PROMPT.format(
                candidate_profile=json.dumps(candidate_profile, default=str),
                job_description=json.dumps(
                    {
                        "job_id": job.get("job_id"),
                        "required_skills": job.get("required_skills", []),
                        "preferred_skills": job.get("preferred_skills", []),
                        "experience_years_min": job.get("experience_years_min", 0),
                    },
                    default=str,
                ),
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
        evaluation = _fallback_evaluate_candidate(job, rag_evidence or {}, candidate_profile)

    evaluation = _normalize_evaluation(evaluation, job, rag_evidence or {}, candidate_profile)
    logger.info("[SUCCESS] Evaluation complete | resume_id=%s | recommendation=%s", resume_id, evaluation.get("recommendation"))
    return evaluation
