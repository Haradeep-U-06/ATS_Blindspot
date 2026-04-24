import asyncio
from typing import Optional

from config import settings
from logger import get_logger

logger = get_logger(__name__)


class GeminiClient:
    def __init__(self) -> None:
        self._configured = False

    def _configure(self) -> None:
        if self._configured:
            return
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._configured = True

    async def generate(
        self,
        prompt: str,
        *,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: Optional[float] = None,
    ) -> str:
        self._configure()
        import google.generativeai as genai

        chosen_model = model_name or settings.gemini_structuring_model
        logger.info("[INFO] Calling Gemini API | model=%s", chosen_model)
        generation_config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
        }
        model = genai.GenerativeModel(
            chosen_model,
            system_instruction="Respond only with valid JSON. No markdown. No explanation.",
            generation_config=generation_config,
        )

        def _call() -> str:
            response = model.generate_content(
                prompt,
                request_options={"timeout": timeout or settings.api_timeout_seconds},
            )
            return getattr(response, "text", "") or ""

        return await asyncio.to_thread(_call)
