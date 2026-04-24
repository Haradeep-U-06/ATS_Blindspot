from scoring.engine import ScoreEngine


def test_scoring_formula_and_subscores():
    candidate = {
        "github_username": "jane",
        "github_data": {},
        "leetcode_data": {},
        "codeforces_data": {},
        "codechef_data": {},
    }
    job = {
        "required_skills": [
            {"skill": "Python", "weight": 0.5},
            {"skill": "FastAPI", "weight": 0.3},
            {"skill": "MongoDB", "weight": 0.2},
        ],
        "preferred_skills": [
            {"skill": "Docker", "weight": 0.5},
            {"skill": "CI/CD", "weight": 0.5},
        ],
        "tech_vs_nontechnical_ratio": 0.8,
    }
    evaluation = {
        "skill_matches": [
            {"skill": "Python", "candidate_has": True, "confidence": 1.0, "evidence_sources": ["work_experience", "projects"]},
            {"skill": "FastAPI", "candidate_has": True, "confidence": 0.8, "evidence_sources": ["projects"]},
            {"skill": "MongoDB", "candidate_has": False, "confidence": 0.0, "evidence_sources": []},
            {"skill": "Docker", "candidate_has": True, "confidence": 0.7, "evidence_sources": ["github"]},
            {"skill": "CI/CD", "candidate_has": False, "confidence": 0.0, "evidence_sources": []},
        ],
        "experience_match": {"match_score": 0.9},
        "recommendation": "moderate_fit",
        "confidence": 0.9,
    }

    result = ScoreEngine().compute(candidate, job, evaluation)

    assert result.base_score == 51.8
    assert result.preferred_bonus == 5.25
    assert result.experience_score == 2.7
    assert result.enrichment_score == 4.5
    assert result.penalties == -8.0
    assert result.final_score == 56.25


def test_penalties_for_missing_heavy_skill_no_github_and_low_confidence():
    candidate = {"github_data": {}, "leetcode_data": {}, "codeforces_data": {}, "codechef_data": {}}
    job = {
        "required_skills": [{"skill": "Python", "weight": 0.7}, {"skill": "SQL", "weight": 0.3}],
        "preferred_skills": [],
        "tech_vs_nontechnical_ratio": 0.9,
    }
    evaluation = {
        "skill_matches": [
            {"skill": "Python", "candidate_has": False, "confidence": 0.0},
            {"skill": "SQL", "candidate_has": True, "confidence": 0.8},
        ],
        "experience_match": {"match_score": 0.5},
        "confidence": 0.4,
    }

    result = ScoreEngine().compute(candidate, job, evaluation)

    assert result.penalties == -13.0
    assert result.subscores_detail["penalty_detail"] == "1 missing required skill, 1 missing high-weight required skill"
