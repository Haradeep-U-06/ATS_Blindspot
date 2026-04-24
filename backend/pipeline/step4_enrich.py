import asyncio
from typing import Any, Dict

from enrichment.codechef_scraper import fetch_codechef_profile
from enrichment.codeforces_fetcher import fetch_codeforces_profile
from enrichment.github_fetcher import fetch_github_profile
from enrichment.leetcode_fetcher import fetch_leetcode_profile
from logger import get_logger

logger = get_logger(__name__)


async def enrich_profile(*, resume_id: str, structured_resume: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("[STEP 4] Running external profile enrichment | resume_id=%s", resume_id)
    results = await asyncio.gather(
        fetch_github_profile(structured_resume.get("github_username")),
        fetch_leetcode_profile(structured_resume.get("leetcode_username")),
        fetch_codeforces_profile(structured_resume.get("codeforces_username")),
        fetch_codechef_profile(structured_resume.get("codechef_username")),
        return_exceptions=True,
    )

    keys = ["github_data", "leetcode_data", "codeforces_data", "codechef_data"]
    enrichment: Dict[str, Any] = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            logger.warning("[WARN] %s enrichment skipped | resume_id=%s | error=%s", key, resume_id, result)
            enrichment[key] = {}
        else:
            enrichment[key] = result or {}
    logger.info("[SUCCESS] External enrichment complete | resume_id=%s", resume_id)
    return enrichment
