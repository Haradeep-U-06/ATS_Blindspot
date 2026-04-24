class LLMUnavailableError(RuntimeError):
    """Raised when both primary and fallback LLM providers fail."""


class JSONRepairError(ValueError):
    """Raised when a model response cannot be parsed or repaired as JSON."""
