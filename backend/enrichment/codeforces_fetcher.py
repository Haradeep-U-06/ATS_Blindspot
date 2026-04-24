from typing import Any, Dict, Optional

import httpx

from config import settings
from logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://codeforces.com/api"


async def fetch_codeforces_profile(username: Optional[str], client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    if not username:
        return {}
    logger.info("[STEP 4c] Fetching Codeforces profile | username=%s", username)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=settings.api_timeout_seconds)
    try:
        logger.info("[INFO] API call: codeforces.com/api/user.info")
        info_response = await http_client.get(f"{BASE_URL}/user.info?handles={username}")
        if info_response.status_code == 429:
            logger.warning("[WARN] Codeforces API rate limited | username=%s", username)
            return {}
        if info_response.status_code >= 400:
            logger.warning("[WARN] Codeforces HTTP error | status=%s", info_response.status_code)
            return {}
        info_payload = info_response.json()
        if info_payload.get("status") != "OK" or not info_payload.get("result"):
            logger.warning("[WARN] Codeforces user not found | username=%s", username)
            return {}
        user = info_payload["result"][0]

        rating_history = []
        rating_response = await http_client.get(f"{BASE_URL}/user.rating?handle={username}")
        if rating_response.status_code < 400:
            rating_payload = rating_response.json()
            if rating_payload.get("status") == "OK":
                rating_history = rating_payload.get("result", [])

        data = {
            "username": username,
            "rating": user.get("rating"),
            "max_rating": user.get("maxRating"),
            "rank": user.get("rank"),
            "max_rank": user.get("maxRank"),
            "rating_history_count": len(rating_history),
        }
        logger.info(
            "[SUCCESS] rating=%s | max_rating=%s | rank=%s",
            data["rating"],
            data["max_rating"],
            data["rank"],
        )
        return data
    except httpx.TimeoutException as exc:
        logger.error("[ERROR] Codeforces timeout | username=%s | error=%s", username, exc)
        return {}
    except Exception as exc:
        logger.error("[ERROR] Codeforces enrichment failed | username=%s | error=%s", username, exc)
        return {}
    finally:
        if owns_client:
            await http_client.aclose()
