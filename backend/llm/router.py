from typing import Optional

from config import settings
from llm.exceptions import LLMUnavailableError
from llm.gemini_client import GeminiClient
from llm.ollama_client import OllamaClient
from logger import get_logger

logger = get_logger(__name__)


class LLMRouter:
    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        ollama_client: Optional[OllamaClient] = None,
    ) -> None:
        self.gemini = gemini_client or GeminiClient()
        self.ollama = ollama_client or OllamaClient()

    async def generate(
        self,
        prompt: str,
        *,
        task: str = "structuring",
        model_name: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        chosen_model = model_name
        if chosen_model is None:
            chosen_model = (
                settings.gemini_evaluation_model
                if task == "evaluation"
                else settings.gemini_structuring_model
            )

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                return await self.gemini.generate(
                    prompt,
                    model_name=chosen_model,
                    temperature=temperature,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[WARN] Gemini failed | attempt=%s | task=%s | error=%s",
                    attempt + 1,
                    task,
                    exc,
                )

        logger.warning("[WARN] Gemini failed — activating Ollama fallback | task=%s", task)
        try:
            return await self.ollama.generate(
                prompt,
                model_name=settings.ollama_model,
                temperature=temperature,
            )
        except Exception as exc:
            logger.error("[ERROR] Both LLMs failed | task=%s | error=%s", task, exc)
            raise LLMUnavailableError(str(exc)) from last_error or exc
