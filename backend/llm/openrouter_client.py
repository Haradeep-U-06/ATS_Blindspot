from typing import Optional

import httpx

from config import settings
from logger import get_logger

logger = get_logger(__name__)


class OpenRouterClient:
    async def generate(
        self,
        prompt: str,
        *,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: Optional[float] = None,
    ) -> str:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        chosen_model = model_name or settings.openrouter_model
        logger.info("[INFO] Calling OpenRouter primary LLM | model=%s", chosen_model)
        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": "Respond only with valid JSON. No markdown. No explanation."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "AI ATS Backend",
        }
        async with httpx.AsyncClient(timeout=timeout or settings.api_timeout_seconds) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
