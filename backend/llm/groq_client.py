from typing import Optional

import httpx

from config import settings
from logger import get_logger

logger = get_logger(__name__)


class GroqClient:
    async def generate(
        self,
        prompt: str,
        *,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: Optional[float] = None,
    ) -> str:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        chosen_model = model_name or settings.groq_model
        logger.info("[INFO] Calling Groq secondary LLM | model=%s", chosen_model)
        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": "Respond only with valid JSON. No markdown. No explanation."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        async with httpx.AsyncClient(timeout=timeout or settings.api_timeout_seconds) as client:
            response = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
