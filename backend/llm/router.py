from typing import Optional

from config import settings
from llm.exceptions import LLMUnavailableError
from llm.groq_client import GroqClient
from llm.ollama_client import OllamaClient
from llm.openrouter_client import OpenRouterClient
from logger import get_logger

logger = get_logger(__name__)


class LLMRouter:
    def __init__(
        self,
        openrouter_client: Optional[OpenRouterClient] = None,
        groq_client: Optional[GroqClient] = None,
        ollama_client: Optional[OllamaClient] = None,
    ) -> None:
        self.openrouter = openrouter_client or OpenRouterClient()
        self.groq = groq_client or GroqClient()
        self.ollama = ollama_client or OllamaClient()

    async def generate(
        self,
        prompt: str,
        *,
        task: str = "structuring",
        model_name: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        last_error: Exception | None = None
        providers = [
            ("OpenRouter", self.openrouter, model_name or settings.openrouter_model),
            ("Groq", self.groq, settings.groq_model),
            ("Ollama", self.ollama, settings.ollama_model),
        ]
        for provider_name, provider, chosen_model in providers:
            try:
                logger.info("[STEP] LLM request | provider=%s | task=%s", provider_name, task)
                response = await provider.generate(
                    prompt,
                    model_name=chosen_model,
                    temperature=temperature,
                )
                logger.info("[SUCCESS] LLM request complete | provider=%s | task=%s", provider_name, task)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[WARN] LLM provider failed | provider=%s | task=%s | error=%s",
                    provider_name,
                    task,
                    exc,
                )
        logger.error("[ERROR] All LLM providers failed | task=%s", task)
        raise LLMUnavailableError(str(last_error or "No LLM provider available"))
