from types import SimpleNamespace

import pytest

from app.services import getting_started_service, model_selection_service
from app.services.getting_started_service import (
    GettingReadyPromptSizeError,
    generate_getting_ready_manifest,
)
from app.services.model_selection_service import ModelSelectionService


@pytest.mark.asyncio
async def test_ollama_request_uses_callers_max_tokens(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "{}"}}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(model_selection_service.httpx, "AsyncClient", FakeClient)
    service = ModelSelectionService(SimpleNamespace(ollama_base_url="http://127.0.0.1:11434"))

    await service._request(
        provider="ollama",
        model="qwen3.5:4b",
        task="Getting Ready",
        messages=[{"role": "user", "content": "{}"}],
        system_prompt="Return JSON",
        max_tokens=4321,
        timeout=5,
        tools=None,
        json_mode=True,
        images=[],
        tool_choice=None,
    )

    assert captured["payload"]["options"]["num_predict"] == 4321


@pytest.mark.asyncio
async def test_oversized_getting_ready_prompt_fails_before_model_call(monkeypatch):
    async def unexpected_model_call(**_kwargs):
        raise AssertionError("The model must not be called for an oversized prompt")

    monkeypatch.setattr(
        getting_started_service.model_selection_service,
        "complete",
        unexpected_model_call,
    )

    with pytest.raises(GettingReadyPromptSizeError, match="exceeds the configured input budget"):
        await generate_getting_ready_manifest({
            "build_name": "Budget guard test",
            "upgrade_policy": {
                "reviewed_material": "x" * (getting_started_service.GETTING_READY_PROMPT_MAX_BYTES + 1),
            },
        })
