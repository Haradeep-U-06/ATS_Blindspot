from typing import Any, Dict, Optional

import httpx

from config import settings
from enrichment.cache import get_cached, set_cached
from logger import get_logger

logger = get_logger(__name__)

LEETCODE_URL = "https://leetcode.com/graphql"

LEETCODE_QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking reputation starRating }
    submitStats {
      acSubmissionNum { difficulty count submissions }
    }
    badges { displayName }
  }
  userContestRanking(username: $username) {
    rating
    globalRanking
    attendedContestsCount
  }
}
"""


async def fetch_leetcode_profile(username: Optional[str], client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    if not username:
        return {}
    cached = get_cached(f"leetcode:{username}", ttl_seconds=24 * 3600)
    if cached is not None:
        logger.info("[INFO] LeetCode cache hit | username=%s", username)
        return cached

    logger.info("[STEP 4b] Fetching LeetCode stats | username=%s", username)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=settings.api_timeout_seconds)
    try:
        response = await http_client.post(
            LEETCODE_URL,
            json={"query": LEETCODE_QUERY, "variables": {"username": username}},
            headers={"Content-Type": "application/json"},
        )
        logger.info("[INFO] LeetCode GraphQL query sent")
        if response.status_code == 429:
            logger.warning("[WARN] LeetCode rate limited | username=%s", username)
            return {}
        if response.status_code >= 400:
            logger.warning("[WARN] LeetCode HTTP error | status=%s", response.status_code)
            return {}
        payload = response.json().get("data", {})
        matched = payload.get("matchedUser")
        if not matched:
            logger.warning("[WARN] LeetCode user not found | username=%s", username)
            return {}

        counts = {item["difficulty"].lower(): item["count"] for item in matched["submitStats"]["acSubmissionNum"]}
        contest = payload.get("userContestRanking") or {}
        data = {
            "username": username,
            "total_solved": counts.get("all", 0),
            "easy": counts.get("easy", 0),
            "medium": counts.get("medium", 0),
            "hard": counts.get("hard", 0),
            "contest_rating": contest.get("rating"),
            "badges": [badge.get("displayName") for badge in matched.get("badges", []) if badge.get("displayName")],
        }
        logger.info(
            "[SUCCESS] solved=%s | easy=%s | medium=%s | hard=%s | rating=%s",
            data["total_solved"],
            data["easy"],
            data["medium"],
            data["hard"],
            data["contest_rating"],
        )
        set_cached(f"leetcode:{username}", data)
        return data
    except httpx.TimeoutException as exc:
        logger.error("[ERROR] LeetCode timeout | username=%s | error=%s", username, exc)
        return {}
    except Exception as exc:
        logger.error("[ERROR] LeetCode enrichment failed | username=%s | error=%s", username, exc)
        return {}
    finally:
        if owns_client:
            await http_client.aclose()
