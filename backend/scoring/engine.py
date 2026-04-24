import math
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


class ScoreEngine:
    def compute(
        self,
        candidate_profile: Dict[str, Any],
        jd_structured: Dict[str, Any],
        evaluation_result: Dict[str, Any],
    ) -> ScoreResult:
        logger.info("[STEP 10] Computing candidate score...")
        skill_conf = self._skill_confidence_map(evaluation_result)
        required_skills = _weighted_skills(jd_structured.get("required_skills", []))
        preferred_skills = _weighted_skills(jd_structured.get("preferred_skills", []))
        tech_multiplier = float(jd_structured.get("tech_vs_nontechnical_ratio", 1.0) or 1.0)

        required_weighted = self._weighted_skill_score(required_skills, skill_conf)
        preferred_weighted = self._weighted_skill_score(preferred_skills, skill_conf)
        base_score = required_weighted * 50.0 * tech_multiplier
        preferred_bonus = preferred_weighted * 50.0 * 0.3
        experience_score = self._experience_score(evaluation_result)
        enrichment_score = self._enrichment_score(candidate_profile)
        penalties, penalty_detail = self._penalties(
            candidate_profile,
            jd_structured,
            evaluation_result,
            required_skills,
            skill_conf,
        )

        raw_score = base_score + preferred_bonus + experience_score + enrichment_score + penalties
        final_score = min(100.0, max(0.0, raw_score))

        logger.debug(
            "[DEBUG] base_score=%.2f | preferred_bonus=%.2f | experience_score=%.2f",
            base_score,
            preferred_bonus,
            experience_score,
        )
        logger.debug(
            "[DEBUG] enrichment_score=%.2f | tech_multiplier=%.2f",
            enrichment_score,
            tech_multiplier,
        )
        logger.debug("[DEBUG] penalties=%.2f (%s)", penalties, penalty_detail)
        logger.info(
            "[SUCCESS] Final score=%.1f / 100 | recommendation=%s",
            final_score,
            evaluation_result.get("recommendation", "unknown"),
        )

        return ScoreResult(
            final_score=round(final_score, 2),
            base_score=round(base_score, 2),
            preferred_bonus=round(preferred_bonus, 2),
            experience_score=round(experience_score, 2),
            enrichment_score=round(enrichment_score, 2),
            penalties=round(penalties, 2),
            subscores_detail={
                "required_weighted_match": round(required_weighted, 4),
                "preferred_weighted_match": round(preferred_weighted, 4),
                "tech_multiplier": tech_multiplier,
                "penalty_detail": penalty_detail,
            },
        )

    def _skill_confidence_map(self, evaluation_result: Dict[str, Any]) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for item in evaluation_result.get("skill_matches", []) or []:
            skill = str(item.get("skill", "")).strip().lower()
            if not skill:
                continue
            candidate_has = bool(item.get("candidate_has"))
            confidence = float(item.get("confidence", 0.0) or 0.0)
            result[skill] = confidence if candidate_has else 0.0
        return result

    def _weighted_skill_score(self, skills: List[Dict[str, Any]], skill_conf: Dict[str, float]) -> float:
        score = 0.0
        for item in skills:
            skill = str(item.get("skill", "")).strip().lower()
            weight = float(item.get("weight", 0.0) or 0.0)
            score += skill_conf.get(skill, 0.0) * weight
        return score

    def _experience_score(self, evaluation_result: Dict[str, Any]) -> float:
        match = evaluation_result.get("experience_match") or {}
        return float(match.get("match_score", 0.0) or 0.0) * 20.0

    def _enrichment_score(self, candidate_profile: Dict[str, Any]) -> float:
        github_score = self._github_score(candidate_profile.get("github_data") or {})
        leetcode_score = self._leetcode_score(candidate_profile.get("leetcode_data") or {})
        competitive_score = self._competitive_score(
            candidate_profile.get("codeforces_data") or {},
            candidate_profile.get("codechef_data") or {},
        )
        total = min(15.0, github_score + leetcode_score + competitive_score)
        logger.debug(
            "[DEBUG] enrichment_parts | github=%.2f | leetcode=%.2f | competitive=%.2f",
            github_score,
            leetcode_score,
            competitive_score,
        )
        return total

    def _github_score(self, github_data: Dict[str, Any]) -> float:
        if not github_data:
            return 0.0
        repos = github_data.get("top_repositories", []) or []
        total_stars = sum(float(repo.get("stars", 0) or 0) for repo in repos)
        languages = github_data.get("languages", []) or []
        repo_count = float(github_data.get("public_repos", len(repos)) or 0)
        stars_score = min(2.5, math.log10(total_stars + 1.0) * 1.25)
        language_score = min(1.5, len(set(languages)) * 0.3)
        repo_score = min(1.0, repo_count / 20.0)
        return min(5.0, stars_score + language_score + repo_score)

    def _leetcode_score(self, leetcode_data: Dict[str, Any]) -> float:
        solved = int(leetcode_data.get("total_solved", 0) or 0)
        rating = float(leetcode_data.get("contest_rating", 0) or 0)
        if solved > 200:
            score = 5.0
        elif solved > 100:
            score = 3.0
        elif solved > 50:
            score = 1.0
        else:
            score = 0.0
        if rating >= 1800:
            score += 0.75
        elif rating >= 1600:
            score += 0.4
        return min(5.0, score)

    def _competitive_score(self, codeforces_data: Dict[str, Any], codechef_data: Dict[str, Any]) -> float:
        cf_rating = float(codeforces_data.get("rating", 0) or 0)
        cc_rating = float(codechef_data.get("rating", 0) or 0)
        best = max(cf_rating, cc_rating)
        if best >= 2100:
            return 5.0
        if best >= 1800:
            return 4.0
        if best >= 1600:
            return 3.0
        if best >= 1400:
            return 2.0
        if best >= 1200:
            return 1.0
        return 0.0

    def _penalties(
        self,
        candidate_profile: Dict[str, Any],
        jd_structured: Dict[str, Any],
        evaluation_result: Dict[str, Any],
        required_skills: List[Dict[str, Any]],
        skill_conf: Dict[str, float],
    ) -> tuple[float, str]:
        penalties = 0.0
        details = []
        missing_heavy = [
            item.get("skill")
            for item in required_skills
            if float(item.get("weight", 0.0) or 0.0) > 0.2
            and skill_conf.get(str(item.get("skill", "")).lower(), 0.0) <= 0.0
        ]
        if missing_heavy:
            amount = -5.0 * len(missing_heavy)
            penalties += amount
            details.append(f"{len(missing_heavy)} missing required skill")

        is_technical = float(jd_structured.get("tech_vs_nontechnical_ratio", 1.0) or 1.0) >= 0.6
        has_github = bool(candidate_profile.get("github_username") or candidate_profile.get("github_data"))
        if is_technical and not has_github:
            penalties -= 3.0
            details.append("no GitHub profile")

        confidence = evaluation_result.get("confidence")
        if confidence is not None and float(confidence) < 0.5:
            logger.warning("[WARN] Low LLM confidence — penalty applied")
            penalties -= 5.0
            details.append("low LLM confidence")

        return penalties, ", ".join(details) if details else "none"
