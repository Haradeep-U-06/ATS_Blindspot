from typing import Optional

import httpx

from config import settings
from logger import get_logger

logger = get_logger(__name__)


class OllamaClient:
    async def generate(
        self,
        prompt: str,
        *,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: Optional[float] = None,
    ) -> str:
        chosen_model = model_name or settings.ollama_model
        logger.info("[INFO] Calling Ollama fallback | model=%s", chosen_model)
        payload = {
            "model": chosen_model,
            "prompt": "Respond only with valid JSON. No markdown. No explanation.\n\n" + prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=timeout or settings.api_timeout_seconds) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
