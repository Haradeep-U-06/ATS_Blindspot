import pytest

from llm.router import LLMRouter


class FailingClient:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    async def generate(self, *args, **kwargs):
        self.calls.append(self.name)
        raise RuntimeError(f"{self.name} failed")


class PassingClient:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    async def generate(self, *args, **kwargs):
        self.calls.append(self.name)
        return '{"ok": true}'


@pytest.mark.asyncio
async def test_llm_router_uses_openrouter_then_groq_then_ollama():
    calls = []
    router = LLMRouter(
        openrouter_client=FailingClient("openrouter", calls),
        groq_client=FailingClient("groq", calls),
        ollama_client=PassingClient("ollama", calls),
    )

    response = await router.generate("{}", task="evaluation")

    assert response == '{"ok": true}'
    assert calls == ["openrouter", "groq", "ollama"]
