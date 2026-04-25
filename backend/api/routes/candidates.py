from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_db, serialize_mongo
from pipeline.step12_rank import _score_breakdown, _structured_resume_summary

router = APIRouter(tags=["candidates"])


def _format_score(score: dict) -> dict:
    details = score.get("subscores_detail", {}) or {}
    return {
        **score,
        "pros": score.get("strengths", []),
        "cons": score.get("gaps", []),
        "skill_scores": details.get("skill_scores", []),
        "score_breakdown": _score_breakdown(score),
    }


def _build_external_profiles_summary(candidate: dict) -> dict:
    """Build structured, frontend-ready external profile data from raw fetched data."""
    github_raw = candidate.get("github_data") or {}
    leetcode_raw = candidate.get("leetcode_data") or {}
    codeforces_raw = candidate.get("codeforces_data") or {}
    codechef_raw = candidate.get("codechef_data") or {}

    # ── GitHub ──────────────────────────────────────────────────────
    github = None
    if github_raw and github_raw.get("username"):
        top_repos = github_raw.get("top_repositories") or []
        structured_repos = []
        for repo in top_repos[:3]:
            structured_repos.append({
                "name": repo.get("repo") or repo.get("name"),
                "description": repo.get("description") or None,
                "tech_stack": [repo["language"]] if repo.get("language") else [],
                "stars": repo.get("stars", 0),
                "forks": repo.get("forks", 0),
                "readme_preview": (repo.get("readme_preview") or "")[:300] or None,
                "url": f"https://github.com/{github_raw['username']}/{repo.get('repo') or repo.get('name')}",
            })
        github = {
            "username": github_raw.get("username"),
            "repo_count": github_raw.get("public_repos", len(top_repos)),
            "followers": github_raw.get("followers"),
            "languages": github_raw.get("languages", []),
            "top_repositories": structured_repos,
            "commit_activity_level": (
                "high" if github_raw.get("public_repos", 0) >= 20
                else "medium" if github_raw.get("public_repos", 0) >= 8
                else "low"
            ),
        }

    # ── LeetCode ────────────────────────────────────────────────────
    leetcode = None
    if leetcode_raw and leetcode_raw.get("username"):
        total = leetcode_raw.get("total_solved", 0) or 0
        leetcode = {
            "username": leetcode_raw.get("username"),
            "total_solved": total,
            "easy_solved": leetcode_raw.get("easy", 0),
            "medium_solved": leetcode_raw.get("medium", 0),
            "hard_solved": leetcode_raw.get("hard", 0),
            "contest_rating": leetcode_raw.get("contest_rating"),
            "badges": leetcode_raw.get("badges", []),
            "active_recently": total > 0,
        }

    # ── Codeforces ──────────────────────────────────────────────────
    codeforces = None
    if codeforces_raw and codeforces_raw.get("username"):
        codeforces = {
            "username": codeforces_raw.get("username"),
            "rating": codeforces_raw.get("rating"),
            "max_rating": codeforces_raw.get("max_rating"),
            "rank": codeforces_raw.get("rank"),
            "max_rank": codeforces_raw.get("max_rank"),
            "contest_count": codeforces_raw.get("rating_history_count", 0),
        }

    # ── CodeChef ────────────────────────────────────────────────────
    codechef = None
    if codechef_raw and codechef_raw.get("username"):
        codechef = {
            "username": codechef_raw.get("username"),
            "rating": codechef_raw.get("rating"),
            "highest_rating": codechef_raw.get("highest_rating"),
            "stars": codechef_raw.get("stars"),
            "problems_solved": codechef_raw.get("problems_solved"),
        }

    # ── Summary text ────────────────────────────────────────────────
    parts = []
    if github:
        lang_str = ", ".join(github["languages"][:4]) if github["languages"] else "various languages"
        parts.append(
            f"Active on GitHub ({github['repo_count']} public repos) with projects in {lang_str}."
        )
    if leetcode and leetcode["total_solved"]:
        parts.append(
            f"Solved {leetcode['total_solved']} LeetCode problems "
            f"({leetcode['hard_solved']} hard), showing strong algorithmic skills."
        )
    if codeforces and codeforces["rating"]:
        parts.append(f"Codeforces rating: {codeforces['rating']} ({codeforces['rank']}).")
    if codechef and codechef["rating"]:
        parts.append(f"CodeChef rating: {codechef['rating']} ({codechef.get('stars', '')}).")

    return {
        "github": github,
        "leetcode": leetcode,
        "codeforces": codeforces,
        "codechef": codechef,
        "summary": " ".join(parts) if parts else None,
    }


async def _candidate_payload(candidate_id: str, db: Any) -> dict:
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate_id not found")
    scores = await db.scores.find({"candidate_id": candidate_id}).sort("created_at", -1).to_list(length=50)

    external_profiles = _build_external_profiles_summary(candidate)

    payload = {
        **candidate,
        "resume_summary": _structured_resume_summary(candidate),
        "scores": [_format_score(score) for score in scores],
        "external_profiles": external_profiles,
    }
    return serialize_mongo(payload)


@router.get("/candidate/{candidate_id}")
async def get_candidate_profile(candidate_id: str, db: Any = Depends(get_db)) -> dict:
    return await _candidate_payload(candidate_id, db)


@router.get("/candidates/{candidate_id}")
async def get_candidate_profile_hr(candidate_id: str, db: Any = Depends(get_db)) -> dict:
    return await _candidate_payload(candidate_id, db)
