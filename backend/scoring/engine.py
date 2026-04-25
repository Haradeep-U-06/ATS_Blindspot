from typing import Any, Dict, List, Tuple
import re

from db.models import ScoreResult
from logger import get_logger

logger = get_logger(__name__)


def _normalize_weights(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not items:
        return []
    total = sum(float(item.get("weight", 0.0) or 0.0) for item in items)
    if total <= 0:
        return [{"skill": item.get("skill"), "weight": 1.0 / len(items)} for item in items]
    return [{"skill": item.get("skill"), "weight": float(item.get("weight", 0.0) or 0.0) / total} for item in items]


def _weighted_skills(skills: Any) -> List[Dict[str, Any]]:
    if not skills:
        return []
    result = []
    for item in skills:
        if isinstance(item, dict):
            result.append(item)
        elif hasattr(item, "model_dump"):
            result.append(item.model_dump())
        elif hasattr(item, "dict"):
            result.append(item.dict())
    return result


class ScoreEngine:
    """
    Unified Deterministic Scoring Engine.
    Computes ATS Baseline Score mathematically, blends with RAG Score and Keyword Score.
    No LLM involved.
    """
    
    # ── Weights for ATS Baseline Score ──
    W_SKILL           = 0.40
    W_PROJECT         = 0.20
    W_PROBLEM_SOLVING = 0.20
    W_CONSISTENCY     = 0.10
    W_EXPERIENCE      = 0.10

    def compute(
        self,
        candidate_profile: Dict[str, Any],
        jd_structured: Dict[str, Any],
        evaluation_result: Dict[str, Any],  # Not used anymore
        all_chunks: List[Dict[str, Any]] | None = None,
    ) -> ScoreResult:
        logger.info("[STEP 10] Scoring candidate (Unified Deterministic Pipeline)")

        # 1. ATS Baseline Score Components
        required_skills = _normalize_weights(_weighted_skills(jd_structured.get("required_skills", [])))
        preferred_skills = _normalize_weights(_weighted_skills(jd_structured.get("preferred_skills", [])))
        all_jd_skills = required_skills + preferred_skills
        
        # Candidate's explicitly parsed skills
        cand_skills = set(
            str(s.get("skill", s)).strip().lower() 
            for s in (candidate_profile.get("skills", []) or [])
        )
        
        # Skill Match Component (0-100)
        skill_score = 0.0
        if all_jd_skills:
            score_sum = 0.0
            for req in all_jd_skills:
                sk_name = str(req.get("skill", "")).lower()
                weight = float(req.get("weight", 0.0) or 0.0)
                # Check exact match or substring
                if any(sk_name in c_sk or c_sk in sk_name for c_sk in cand_skills):
                    score_sum += weight
            skill_score = min(100.0, score_sum * 100.0)
            
        # Project Component (0-100)
        projects = candidate_profile.get("projects", []) or []
        valid_projects = [p for p in projects if p.get("description")]
        if len(valid_projects) >= 2:
            project_score = 100.0
        elif len(valid_projects) == 1:
            project_score = 50.0
        else:
            project_score = 0.0
            
        # Problem Solving Component (0-100)
        has_lc = bool(candidate_profile.get("leetcode_username"))
        has_cf = bool(candidate_profile.get("codeforces_username"))
        has_cc = bool(candidate_profile.get("codechef_username"))
        problem_solving_score = 100.0 if any([has_lc, has_cf, has_cc]) else 0.0
        
        # Consistency Component (0-100)
        consistency_score = 100.0 if bool(candidate_profile.get("github_username")) else 0.0
        
        # Experience Component (0-100)
        experience = candidate_profile.get("experience", []) or []
        valid_exp = [e for e in experience if e.get("description")]
        experience_score = 100.0 if valid_exp else 0.0
        
        # Calculate ATS Baseline Score
        ats_score = round(
            (skill_score * self.W_SKILL) +
            (project_score * self.W_PROJECT) +
            (problem_solving_score * self.W_PROBLEM_SOLVING) +
            (consistency_score * self.W_CONSISTENCY) +
            (experience_score * self.W_EXPERIENCE),
            2
        )

        # 2. RAG & Keyword Evidence Scoring
        # Build jd_skills dict for rag_scorer {skill_name: weight}
        # Core keywords (required) get 1.5, preferred get 1.0
        jd_skill_dict = {}
        for s in required_skills:
            jd_skill_dict[s.get("skill")] = 1.5
        for s in preferred_skills:
            jd_skill_dict[s.get("skill")] = 1.0
            
        rag_data = {
            "rag_score": 0.0, 
            "keyword_score": 0.0, 
            "matched_keywords": [], 
            "top_chunks": [], 
            "chunk_scores": [], 
            "avg_similarity": 0.0, 
            "strong_count": 0
        }
        
        final_score = ats_score
        confidence_score = 0.5
        
        if all_chunks is not None:
            from scoring.rag_scorer import compute_rag_score, blend_scores
            rag_data = compute_rag_score(all_chunks, jd_skill_dict)
            blend_result = blend_scores(
                ats_score=ats_score,
                rag_score=rag_data["rag_score"],
                keyword_score=rag_data["keyword_score"],
                avg_similarity=rag_data["avg_similarity"],
                strong_count=rag_data["strong_count"]
            )
            final_score = blend_result["final_score"]
            confidence_score = blend_result["confidence_score"]
            
            formula_update = {
                "ats_weight": blend_result["ats_weight"],
                "rag_weight": blend_result["rag_weight"],
                "keyword_weight": blend_result["keyword_weight"],
                "rag_score": rag_data["rag_score"],
                "keyword_score": rag_data["keyword_score"],
            }
        else:
            formula_update = {"note": "No RAG chunks provided"}

        recommendation = "strong_fit" if final_score >= 80 else "moderate_fit" if final_score >= 50 else "weak_fit"

        logger.info(
            "[SUCCESS] ATS=%.1f | RAG=%.1f | KEY=%.1f | Final=%.1f | conf=%.3f | rec=%s",
            ats_score, rag_data["rag_score"], rag_data["keyword_score"], final_score, confidence_score,
            recommendation,
        )

        return ScoreResult(
            final_score=final_score,
            ats_score=ats_score,
            rag_score=rag_data["rag_score"],
            keyword_score=rag_data["keyword_score"],
            confidence_score=confidence_score,
            base_score=round(skill_score, 2),
            preferred_bonus=0.0,
            experience_score=round(experience_score, 2),
            problem_solving_score=problem_solving_score,
            consistency_score=consistency_score,
            penalties=0.0,
            subscores_detail={
                "project_score": project_score,
                "skill_score": skill_score,
                "top_chunks": rag_data["top_chunks"],
                "chunk_scores": rag_data["chunk_scores"],
                "matched_keywords": rag_data["matched_keywords"],
                "recommendation": recommendation,
                "formula": {
                    "w_skill": self.W_SKILL,
                    "w_project": self.W_PROJECT,
                    "w_problem_solving": self.W_PROBLEM_SOLVING,
                    "w_consistency": self.W_CONSISTENCY,
                    "w_experience": self.W_EXPERIENCE,
                    **formula_update
                },
            },
        )
