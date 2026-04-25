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


def _normalize_weights(skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Force skill weights to sum to 1.0 so scores are stable across LLM runs."""
    total = sum(float(s.get("weight", 0.0) or 0.0) for s in skills)
    if total <= 0:
        n = max(1, len(skills))
        return [{**s, "weight": round(1.0 / n, 6)} for s in skills]
    return [{**s, "weight": round(float(s.get("weight", 0.0) or 0.0) / total, 6)} for s in skills]


class ScoreEngine:
    # ── Score ceiling constants ──────────────────────────────────────
    REQUIRED_MAX   = 70.0   # points available from required skills
    PREFERRED_MAX  = 15.0   # points available from preferred skills
    EVIDENCE_MAX   = 10.0   # evidence quality bonus
    CONFIDENCE_MAX = 5.0    # LLM confidence bonus
    # Capped, proportional penalties (prevents wild score swings)
    PENALTY_PER_MISSING    = 6.0   # reduced from 8.0
    PENALTY_PER_HEAVY_MISS = 3.0   # reduced from 5.0
    MAX_PENALTY_FRACTION   = 0.40  # never subtract > 40% of raw score

    def compute(
        self,
        candidate_profile: Dict[str, Any],
        jd_structured: Dict[str, Any],
        evaluation_result: Dict[str, Any],
    ) -> ScoreResult:
        logger.info("[STEP 10] Scoring candidate (stable, normalized formula)")

        # Normalize weights so score is stable regardless of LLM weight variance
        required_skills  = _normalize_weights(_weighted_skills(jd_structured.get("required_skills", [])))
        preferred_skills = _normalize_weights(_weighted_skills(jd_structured.get("preferred_skills", [])))

        skill_map = self._skill_map(evaluation_result)

        required_weighted  = self._weighted_skill_score(required_skills, skill_map)
        preferred_weighted = self._weighted_skill_score(preferred_skills, skill_map)

        base_score       = required_weighted  * self.REQUIRED_MAX
        preferred_bonus  = preferred_weighted * self.PREFERRED_MAX
        evidence_score   = self._evidence_quality_score(required_skills + preferred_skills, skill_map) * self.EVIDENCE_MAX
        confidence_score = float(evaluation_result.get("confidence", 0.0) or 0.0) * self.CONFIDENCE_MAX

        raw_before_penalty = base_score + preferred_bonus + evidence_score + confidence_score

        # Proportional penalty capped at MAX_PENALTY_FRACTION of raw score
        penalties, penalty_detail = self._penalties(required_skills, skill_map, raw_before_penalty)

        raw_score   = raw_before_penalty + penalties  # penalties are negative
        final_score = round(min(100.0, max(0.0, raw_score)), 2)

        skill_scores = self._skill_scores(required_skills, preferred_skills, skill_map)

        logger.info(
            "[SUCCESS] Score=%.1f | base=%.1f | pref=%.1f | evidence=%.1f | confidence=%.1f | penalty=%.1f | rec=%s",
            final_score, base_score, preferred_bonus, evidence_score, confidence_score,
            penalties, evaluation_result.get("recommendation", "unknown"),
        )

        return ScoreResult(
            final_score=final_score,
            base_score=round(base_score, 2),
            preferred_bonus=round(preferred_bonus, 2),
            experience_score=round(evidence_score, 2),
            enrichment_score=round(confidence_score, 2),
            penalties=round(penalties, 2),
            subscores_detail={
                "required_weighted_match":  round(required_weighted, 4),
                "preferred_weighted_match": round(preferred_weighted, 4),
                "evidence_quality":         round(evidence_score / self.EVIDENCE_MAX, 4),
                "confidence_score":         round(confidence_score, 2),
                "penalty_detail":           penalty_detail,
                "skill_scores":             skill_scores,
                "formula": {
                    "required_skills_max":  self.REQUIRED_MAX,
                    "preferred_skills_max": self.PREFERRED_MAX,
                    "evidence_quality_max": self.EVIDENCE_MAX,
                    "confidence_max":       self.CONFIDENCE_MAX,
                    "penalties":            "Proportional penalty, capped at 40% of raw score.",
                    "weights_normalized":   True,
                },
            },
        )

    # ── Private helpers ─────────────────────────────────────────────

    def _skill_map(self, evaluation_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for item in evaluation_result.get("skill_matches", []) or []:
            skill = str(item.get("skill", "")).strip().lower()
            if not skill:
                continue
            candidate_has = bool(item.get("candidate_has"))
            confidence    = float(item.get("confidence", 0.0) or 0.0) if candidate_has else 0.0
            result[skill] = {
                "candidate_has":    candidate_has,
                "confidence":       min(1.0, confidence),
                "source_score":     _source_score(item.get("evidence_sources", []) or []),
                "evidence_sources": item.get("evidence_sources", []) or [],
                "notes":            item.get("notes", ""),
            }
        return result

    def _weighted_skill_score(self, skills: List[Dict[str, Any]], skill_map: Dict[str, Dict[str, Any]]) -> float:
        """Weighted average of confidence values. Returns 0–1."""
        score = 0.0
        for item in skills:
            skill  = str(item.get("skill", "")).strip().lower()
            weight = float(item.get("weight", 0.0) or 0.0)
            score += skill_map.get(skill, {}).get("confidence", 0.0) * weight
        return min(1.0, score)

    def _evidence_quality_score(self, skills: List[Dict[str, Any]], skill_map: Dict[str, Dict[str, Any]]) -> float:
        if not skills:
            return 0.0
        total_weight = sum(float(item.get("weight", 0.0) or 0.0) for item in skills) or 1.0
        score = 0.0
        for item in skills:
            skill  = str(item.get("skill", "")).strip().lower()
            weight = float(item.get("weight", 0.0) or 0.0)
            match  = skill_map.get(skill, {})
            score += match.get("source_score", 0.0) * weight
        return min(1.0, score / total_weight)

    def _skill_scores(
        self,
        required_skills:  List[Dict[str, Any]],
        preferred_skills: List[Dict[str, Any]],
        skill_map:        Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for requirement_type, skills, max_points in (
            ("required",  required_skills,  self.REQUIRED_MAX),
            ("preferred", preferred_skills, self.PREFERRED_MAX),
        ):
            for item in skills:
                skill_name = str(item.get("skill", "")).strip()
                skill_key  = skill_name.lower()
                weight     = float(item.get("weight", 0.0) or 0.0)
                match      = skill_map.get(skill_key, {})
                confidence = float(match.get("confidence", 0.0) or 0.0)
                max_pts    = max_points * weight
                rows.append({
                    "skill":            skill_name,
                    "requirement_type": requirement_type,
                    "weight":           round(weight, 4),
                    "max_points":       round(max_pts, 2),
                    "score":            round(confidence * max_pts, 2),
                    "match_percentage": round(confidence * 100.0, 1),
                    "candidate_has":    bool(match.get("candidate_has", False)),
                    "confidence":       round(confidence, 4),
                    "evidence_quality": round(float(match.get("source_score", 0.0) or 0.0), 4),
                    "evidence_sources": match.get("evidence_sources", []),
                    "notes":            match.get("notes", ""),
                })
        return rows

    def _penalties(
        self,
        required_skills: List[Dict[str, Any]],
        skill_map:       Dict[str, Dict[str, Any]],
        raw_score:       float,
    ) -> tuple[float, str]:
        missing = [
            item for item in required_skills
            if not skill_map.get(str(item.get("skill", "")).strip().lower(), {}).get("candidate_has")
        ]
        heavy_missing = [
            item for item in missing
            if float(item.get("weight", 0.0) or 0.0) >= 0.35
        ]

        penalty = 0.0
        details = []

        if missing:
            penalty -= self.PENALTY_PER_MISSING * len(missing)
            details.append(f"{len(missing)} missing required skill(s)")
        if heavy_missing:
            penalty -= self.PENALTY_PER_HEAVY_MISS * len(heavy_missing)
            details.append(f"{len(heavy_missing)} high-weight gap(s)")

        # Cap: never remove more than MAX_PENALTY_FRACTION of raw score
        max_deduction = -(raw_score * self.MAX_PENALTY_FRACTION)
        penalty = max(penalty, max_deduction)

        return round(penalty, 2), (", ".join(details) if details else "none")
