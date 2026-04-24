import base64

import httpx
import pytest

respx = pytest.importorskip("respx")

from enrichment.codechef_scraper import fetch_codechef_profile
from enrichment.codeforces_fetcher import fetch_codeforces_profile
from enrichment.github_fetcher import fetch_github_profile
from enrichment.leetcode_fetcher import fetch_leetcode_profile


@pytest.mark.asyncio
@respx.mock
async def test_github_fetcher_success():
    username = "jane_test"
    respx.get(f"https://api.github.com/users/{username}").mock(
        return_value=httpx.Response(200, json={"public_repos": 1, "followers": 5})
    )
    respx.get(f"https://api.github.com/users/{username}/repos?sort=stars&per_page=10").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "api",
                    "description": "FastAPI service",
                    "stargazers_count": 12,
                    "forks_count": 2,
                    "language": "Python",
                    "owner": {"login": username},
                }
            ],
        )
    )
    readme = base64.b64encode(b"# API\nFastAPI MongoDB").decode()
    respx.get(f"https://api.github.com/repos/{username}/api/readme").mock(
        return_value=httpx.Response(200, json={"content": readme})
    )

    result = await fetch_github_profile(username)

    assert result["public_repos"] == 1
    assert result["languages"] == ["Python"]
    assert result["top_repositories"][0]["stars"] == 12


@pytest.mark.asyncio
@respx.mock
async def test_github_fetcher_404_returns_empty():
    username = "missing_test"
    respx.get(f"https://api.github.com/users/{username}").mock(return_value=httpx.Response(404))

    assert await fetch_github_profile(username) == {}


@pytest.mark.asyncio
@respx.mock
async def test_leetcode_fetcher_success():
    username = "lc_test"
    respx.post("https://leetcode.com/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "matchedUser": {
                        "username": username,
                        "profile": {},
                        "submitStats": {
                            "acSubmissionNum": [
                                {"difficulty": "All", "count": 312, "submissions": 500},
                                {"difficulty": "Easy", "count": 120, "submissions": 150},
                                {"difficulty": "Medium", "count": 158, "submissions": 250},
                                {"difficulty": "Hard", "count": 34, "submissions": 100},
                            ]
                        },
                        "badges": [{"displayName": "Knight"}],
                    },
                    "userContestRanking": {"rating": 1845},
                }
            },
        )
    )

    result = await fetch_leetcode_profile(username)

    assert result["total_solved"] == 312
    assert result["contest_rating"] == 1845


@pytest.mark.asyncio
@respx.mock
async def test_codeforces_fetcher_success():
    username = "cf_test"
    respx.get(f"https://codeforces.com/api/user.info?handles={username}").mock(
        return_value=httpx.Response(200, json={"status": "OK", "result": [{"rating": 1724, "maxRating": 1890, "rank": "expert"}]})
    )
    respx.get(f"https://codeforces.com/api/user.rating?handle={username}").mock(
        return_value=httpx.Response(200, json={"status": "OK", "result": [{"newRating": 1724}]})
    )

    result = await fetch_codeforces_profile(username)

    assert result["rating"] == 1724
    assert result["rank"] == "expert"


@pytest.mark.asyncio
@respx.mock
async def test_codechef_scraper_success():
    username = "chef_test"
    html = """
    <html>
      <div class="rating-number">1643</div>
      <span class="rating-star">3★</span>
      <section>Highest Rating 1701</section>
      <section>Total Problems Solved 289</section>
    </html>
    """
    respx.get(f"https://www.codechef.com/users/{username}").mock(return_value=httpx.Response(200, text=html))

    result = await fetch_codechef_profile(username)

    assert result["rating"] == 1643
    assert result["stars"] == "3★"
