from typing import Any, Dict, Iterable, List

from db.models import ScoreResult
from logger import get_logger

logger = get_logger(__name__)


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _weighted_skills(items: Iterable[Any]) -> List[Dict[str, Any]]:
    return [_as_dict(item) for item in items or []]


def _source_score(sources: List[str]) -> float:
    score = 0.0
    source_set = set(sources or [])
    if "work_experience" in source_set:
        score += 0.4
    if "projects" in source_set:
        score += 0.3
    if source_set.intersection({"github", "leetcode", "codeforces", "codechef"}):
        score += 0.2
    if source_set.intersection({"resume_raw", "resume_skills", "resume_summary"}):
        score += 0.1
    return min(1.0, score)


class ScoreEngine:
    def compute(
        self,
        candidate_profile: Dict[str, Any],
        jd_structured: Dict[str, Any],
        evaluation_result: Dict[str, Any],
    ) -> ScoreResult:
        logger.info("[STEP 10] Scoring candidate from JD tech-stack evidence only")
        skill_map = self._skill_map(evaluation_result)
        required_skills = _weighted_skills(jd_structured.get("required_skills", []))
        preferred_skills = _weighted_skills(jd_structured.get("preferred_skills", []))

        required_weighted = self._weighted_skill_score(required_skills, skill_map)
        preferred_weighted = self._weighted_skill_score(preferred_skills, skill_map)
        base_score = required_weighted * 70.0
        preferred_bonus = preferred_weighted * 15.0
        evidence_score = self._evidence_quality_score(required_skills + preferred_skills, skill_map) * 10.0
        confidence_score = float(evaluation_result.get("confidence", 0.0) or 0.0) * 5.0
        penalties, penalty_detail = self._penalties(required_skills, skill_map)

        raw_score = base_score + preferred_bonus + evidence_score + confidence_score + penalties
        final_score = min(100.0, max(0.0, raw_score))
        skill_scores = self._skill_scores(required_skills, preferred_skills, skill_map)
        logger.info("[SUCCESS] Score=%s | recommendation=%s", round(final_score, 2), evaluation_result.get("recommendation", "unknown"))
        return ScoreResult(
            final_score=round(final_score, 2),
            base_score=round(base_score, 2),
            preferred_bonus=round(preferred_bonus, 2),
            experience_score=round(evidence_score, 2),
            enrichment_score=round(confidence_score, 2),
            penalties=round(penalties, 2),
            subscores_detail={
                "required_weighted_match": round(required_weighted, 4),
                "preferred_weighted_match": round(preferred_weighted, 4),
                "evidence_quality": round(evidence_score / 10.0, 4),
                "confidence_score": round(confidence_score, 2),
                "penalty_detail": penalty_detail,
                "skill_scores": skill_scores,
                "formula": {
                    "required_skills_max": 70.0,
                    "preferred_skills_max": 15.0,
                    "evidence_quality_max": 10.0,
                    "confidence_max": 5.0,
                    "penalties": "Missing required skills subtract from the total score.",
                },
            },
        )

    def _skill_map(self, evaluation_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for item in evaluation_result.get("skill_matches", []) or []:
            skill = str(item.get("skill", "")).strip().lower()
            if not skill:
                continue
            candidate_has = bool(item.get("candidate_has"))
            confidence = float(item.get("confidence", 0.0) or 0.0) if candidate_has else 0.0
            result[skill] = {
                "candidate_has": candidate_has,
                "confidence": confidence,
                "source_score": _source_score(item.get("evidence_sources", []) or []),
                "evidence_sources": item.get("evidence_sources", []) or [],
                "notes": item.get("notes", ""),
            }
        return result

    def _weighted_skill_score(self, skills: List[Dict[str, Any]], skill_map: Dict[str, Dict[str, Any]]) -> float:
        score = 0.0
        for item in skills:
            skill = str(item.get("skill", "")).strip().lower()
            weight = float(item.get("weight", 0.0) or 0.0)
            score += skill_map.get(skill, {}).get("confidence", 0.0) * weight
        return score

    def _evidence_quality_score(self, skills: List[Dict[str, Any]], skill_map: Dict[str, Dict[str, Any]]) -> float:
        if not skills:
            return 0.0
        total_weight = sum(float(item.get("weight", 0.0) or 0.0) for item in skills) or len(skills)
        score = 0.0
        for item in skills:
            skill = str(item.get("skill", "")).strip().lower()
            weight = float(item.get("weight", 0.0) or 0.0) or (1.0 / len(skills))
            match = skill_map.get(skill, {})
            score += match.get("source_score", 0.0) * weight
        return min(1.0, score / total_weight)

    def _skill_scores(
        self,
        required_skills: List[Dict[str, Any]],
        preferred_skills: List[Dict[str, Any]],
        skill_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for requirement_type, skills, max_points in (
            ("required", required_skills, 70.0),
            ("preferred", preferred_skills, 15.0),
        ):
            for item in skills:
                skill_name = str(item.get("skill", "")).strip()
                skill_key = skill_name.lower()
                weight = float(item.get("weight", 0.0) or 0.0)
                match = skill_map.get(skill_key, {})
                confidence = float(match.get("confidence", 0.0) or 0.0)
                max_skill_points = max_points * weight
                rows.append(
                    {
                        "skill": skill_name,
                        "requirement_type": requirement_type,
                        "weight": round(weight, 4),
                        "max_points": round(max_skill_points, 2),
                        "score": round(confidence * max_skill_points, 2),
                        "match_percentage": round(confidence * 100.0, 2),
                        "candidate_has": bool(match.get("candidate_has", False)),
                        "confidence": round(confidence, 4),
                        "evidence_quality": round(float(match.get("source_score", 0.0) or 0.0), 4),
                        "evidence_sources": match.get("evidence_sources", []),
                        "notes": match.get("notes", ""),
                    }
                )
        return rows

    def _penalties(self, required_skills: List[Dict[str, Any]], skill_map: Dict[str, Dict[str, Any]]) -> tuple[float, str]:
        missing = [
            item
            for item in required_skills
            if not skill_map.get(str(item.get("skill", "")).strip().lower(), {}).get("candidate_has")
        ]
        penalties = 0.0
        details = []
        if missing:
            penalties -= 8.0 * len(missing)
            details.append(f"{len(missing)} missing required skill")
        heavy_missing = [item for item in missing if float(item.get("weight", 0.0) or 0.0) >= 0.4]
        if heavy_missing:
            penalties -= 5.0 * len(heavy_missing)
            details.append(f"{len(heavy_missing)} missing high-weight required skill")
        return penalties, ", ".join(details) if details else "none"
