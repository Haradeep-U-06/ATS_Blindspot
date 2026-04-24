import json

import httpx
import pytest
import respx

from config import settings
from llm.groq_client import GroqClient
from llm.ollama_client import OllamaClient
from llm.openrouter_client import OpenRouterClient


JSON_SYSTEM_PROMPT = "Respond only with valid JSON. No markdown. No explanation."


@pytest.mark.asyncio
async def test_openrouter_client_sends_json_system_prompt_and_user_prompt(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://openrouter.test/api/v1")

    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://openrouter.test/api/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})
        )

        response = await OpenRouterClient().generate("Prompt body", model_name="model/test", temperature=0.1)

    payload = json.loads(route.calls.last.request.content)
    assert response == '{"ok": true}'
    assert payload["model"] == "model/test"
    assert payload["temperature"] == 0.1
    assert payload["messages"] == [
        {"role": "system", "content": JSON_SYSTEM_PROMPT},
        {"role": "user", "content": "Prompt body"},
    ]
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-openrouter-key"


@pytest.mark.asyncio
async def test_groq_client_sends_json_system_prompt_and_user_prompt(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(settings, "groq_base_url", "https://groq.test/openai/v1")

    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://groq.test/openai/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})
        )

        response = await GroqClient().generate("Prompt body", model_name="llama-test", temperature=0.3)

    payload = json.loads(route.calls.last.request.content)
    assert response == '{"ok": true}'
    assert payload["model"] == "llama-test"
    assert payload["temperature"] == 0.3
    assert payload["messages"] == [
        {"role": "system", "content": JSON_SYSTEM_PROMPT},
        {"role": "user", "content": "Prompt body"},
    ]
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-groq-key"


@pytest.mark.asyncio
async def test_ollama_client_prefixes_prompt_with_json_instruction(monkeypatch):
    monkeypatch.setattr(settings, "ollama_base_url", "http://ollama.test")

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://ollama.test/api/generate").mock(
            return_value=httpx.Response(200, json={"response": '{"ok": true}'})
        )

        response = await OllamaClient().generate("Prompt body", model_name="llama-local", temperature=0.4)

    payload = json.loads(route.calls.last.request.content)
    assert response == '{"ok": true}'
    assert payload["model"] == "llama-local"
    assert payload["stream"] is False
    assert payload["options"] == {"temperature": 0.4}
    assert payload["prompt"] == f"{JSON_SYSTEM_PROMPT}\n\nPrompt body"
