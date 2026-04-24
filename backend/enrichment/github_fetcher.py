import asyncio
import base64
from typing import Any, Dict, Optional

import httpx

from config import settings
from enrichment.cache import get_cached, set_cached
from logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.github.com"


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def _request_json(client: httpx.AsyncClient, url: str) -> tuple[Optional[Dict[str, Any]], httpx.Response | None]:
    for attempt in range(2):
        try:
            response = await client.get(url, headers=_headers())
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                logger.debug("[DEBUG] GitHub rate limit remaining=%s", remaining)
            if response.status_code == 404:
                logger.warning("[WARN] GitHub resource not found | url=%s", url)
                return None, response
            if response.status_code == 429:
                logger.warning("[WARN] GitHub API rate limited — skipping enrichment")
                return None, response
            if response.status_code >= 500 and attempt == 0:
                logger.error("[ERROR] GitHub 5xx response | status=%s | retrying=true", response.status_code)
                await asyncio.sleep(2)
                continue
            response.raise_for_status()
            return response.json(), response
        except httpx.TimeoutException as exc:
            logger.error("[ERROR] GitHub timeout | attempt=%s | error=%s", attempt + 1, exc)
            if attempt == 0:
                continue
        except httpx.HTTPStatusError as exc:
            logger.warning("[WARN] GitHub HTTP error | status=%s", exc.response.status_code)
            return None, exc.response
        except Exception as exc:
            logger.error("[ERROR] GitHub enrichment error | error=%s", exc)
            return None, None
    return None, None


async def fetch_github_profile(username: Optional[str], client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    if not username:
        return {}
    cached = get_cached(f"github:{username}", ttl_seconds=3600)
    if cached is not None:
        logger.info("[INFO] GitHub cache hit | username=%s", username)
        return cached

    logger.info("[STEP 4a] Fetching GitHub profile | username=%s", username)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=settings.api_timeout_seconds)
    try:
        logger.info("[INFO] GitHub API call: GET /users/%s", username)
        user, _ = await _request_json(http_client, f"{BASE_URL}/users/{username}")
        if not user:
            return {}

        repos, _ = await _request_json(http_client, f"{BASE_URL}/users/{username}/repos?sort=stars&per_page=10")
        repos = repos or []
        logger.info("[SUCCESS] Retrieved %s public repos", len(repos))

        top_repos = sorted(repos, key=lambda repo: repo.get("stargazers_count", 0), reverse=True)[:10]
        top_preview = ", ".join(
            f"{repo.get('name')}({repo.get('stargazers_count', 0)}★)" for repo in top_repos[:2]
        )
        logger.debug("[DEBUG] Top repos by stars: %s", top_preview)

        readmes = []
        languages = set()
        logger.info("[INFO] Fetching READMEs for top 5 repos...")
        for repo in top_repos[:5]:
            repo_name = repo.get("name")
            owner = repo.get("owner", {}).get("login", username)
            language = repo.get("language")
            if language:
                languages.add(language)
            readme, _ = await _request_json(http_client, f"{BASE_URL}/repos/{owner}/{repo_name}/readme")
            content = ""
            if readme and readme.get("content"):
                try:
                    content = base64.b64decode(readme["content"]).decode("utf-8", errors="ignore")
                except Exception:
                    content = ""
            readmes.append(
                {
                    "repo": repo_name,
                    "description": repo.get("description") or "",
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": language,
                    "readme_preview": content[:1000],
                }
            )

        data = {
            "username": username,
            "public_repos": user.get("public_repos", len(repos)),
            "followers": user.get("followers", 0),
            "languages": sorted(languages),
            "top_repositories": readmes,
        }
        logger.info("[SUCCESS] GitHub enrichment complete | languages=%s", data["languages"])
        set_cached(f"github:{username}", data)
        return data
    finally:
        if owns_client:
            await http_client.aclose()
