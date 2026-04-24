import asyncio
import re
from typing import Any, Dict, Optional

import httpx

from config import settings
from logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://www.codechef.com/users"
USER_AGENT = "Mozilla/5.0 (compatible; ATSBot/1.0; +https://example.com/bot)"


def _parse_int(text: str) -> Optional[int]:
    match = re.search(r"[\d,]+", text or "")
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _parse_profile(html: str, username: str) -> Dict[str, Any]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        logger.warning("[WARN] BeautifulSoup unavailable — CodeChef enrichment skipped")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    rating_node = soup.select_one(".rating-number")
    stars_node = soup.select_one(".rating-star")
    highest_node = soup.find(string=re.compile(r"Highest Rating", re.IGNORECASE))
    solved_text = soup.get_text(" ", strip=True)

    highest_rating = None
    if highest_node:
        highest_rating = _parse_int(str(highest_node.parent.get_text(" ", strip=True)))

    solved_match = re.search(r"Total Problems Solved\s*[:\-]?\s*(\d+)", solved_text, re.IGNORECASE)
    if not solved_match:
        solved_match = re.search(r"Problems Solved\s*[:\-]?\s*(\d+)", solved_text, re.IGNORECASE)

    return {
        "username": username,
        "rating": _parse_int(rating_node.get_text(" ", strip=True)) if rating_node else None,
        "stars": stars_node.get_text(" ", strip=True) if stars_node else None,
        "highest_rating": highest_rating,
        "problems_solved": int(solved_match.group(1)) if solved_match else None,
    }


async def fetch_codechef_profile(username: Optional[str], client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    if not username:
        return {}
    logger.info("[STEP 4d] Scraping CodeChef profile | username=%s", username)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=settings.api_timeout_seconds)
    url = f"{BASE_URL}/{username}"
    try:
        for attempt in range(3):
            try:
                logger.info("[INFO] GET %s", url)
                response = await http_client.get(url, headers={"User-Agent": USER_AGENT})
                if response.status_code == 404:
                    logger.warning("[WARN] CodeChef user not found | username=%s", username)
                    return {}
                if response.status_code == 429:
                    logger.warning("[WARN] CodeChef rate limited | username=%s", username)
                    return {}
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=response.request, response=response)
                response.raise_for_status()
                data = _parse_profile(response.text, username)
                logger.info(
                    "[SUCCESS] rating=%s | stars=%s | problems_solved=%s",
                    data.get("rating"),
                    data.get("stars"),
                    data.get("problems_solved"),
                )
                return data
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    logger.warning("[WARN] CodeChef scrape failed after 3 retries — enrichment skipped")
                    return {}
                await asyncio.sleep(2**attempt)
                logger.warning("[WARN] CodeChef scrape retry | attempt=%s | error=%s", attempt + 2, exc)
        return {}
    finally:
        if owns_client:
            await http_client.aclose()
