"""Central provider/model routing for every backend LLM request.

The ordered tiers are runtime-configurable through LLM_PRIMARY_*,
LLM_SECONDARY_*, and LLM_TERTIARY_* settings. The default is local Qwen,
OpenRouter free, then the cheapest paid OpenRouter model. Ollama's URL stays
environment-specific (dev gateway / production tunnel) in OLLAMA_BASE_URL.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.config import Settings, get_settings

log = structlog.get_logger(__name__)
_MODEL_CACHE: tuple[float, list[dict[str, Any]]] | None = None


@dataclass(frozen=True)
class ModelTier:
    provider: str
    model: str
    name: str


@dataclass
class ModelResult:
    text: str = ""
    model: str = ""
    provider: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    assistant_message: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)


class ModelSelectionError(RuntimeError):
    pass


class ModelSelectionService:
    """Selects the first configured compatible model that completes a request."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def tiers(self) -> list[ModelTier]:
        s = self.settings
        return [
            ModelTier(s.llm_primary_provider.strip().lower(), s.llm_primary_model.strip(), "primary"),
            ModelTier(s.llm_secondary_provider.strip().lower(), s.llm_secondary_model.strip(), "secondary"),
            ModelTier(s.llm_tertiary_provider.strip().lower(), s.llm_tertiary_model.strip(), "tertiary"),
        ]

    async def complete(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        timeout: float = 120,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        images: list[tuple[bytes, str]] | None = None,
        require_vision: bool = False,
        require_tools: bool = False,
    ) -> ModelResult:
        errors: list[str] = []
        for tier in self.tiers():
            if not tier.provider or not tier.model:
                continue
            if require_vision and tier.provider in {"ollama", "local"} and not _vision_capable(tier.model):
                errors.append(f"{tier.name}: configured Ollama model is not vision-capable")
                continue
            if tier.provider in {"openrouter", "openrouter-free"} and not self.settings.openrouter_api_key:
                errors.append(f"{tier.name}: OpenRouter API key is not configured")
                continue
            try:
                model = tier.model
                provider = "openrouter" if tier.provider == "openrouter-free" else tier.provider
                if provider == "openrouter" and model.lower() in {"auto:cheapest", "cheapest"}:
                    model = await _cheapest_openrouter_model(self.settings, require_vision, require_tools)
                if tier.provider == "openrouter-free" and not model.endswith(":free"):
                    model = f"{model}:free"
                result = await self._request(
                    provider=provider,
                    model=model,
                    task=task,
                    messages=messages,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    tools=tools,
                    json_mode=json_mode,
                    images=images or [],
                )
                if result.text.strip() or result.tool_calls:
                    log.info(
                        "llm.request.succeeded", task=task, tier=tier.name,
                        provider=result.provider, model=result.model,
                        prompt_tokens=result.usage.get("prompt_tokens"),
                        completion_tokens=result.usage.get("completion_tokens"),
                    )
                    return result
                errors.append(f"{tier.name}: empty response from {provider}/{model}")
            except Exception as exc:
                errors.append(f"{tier.name}: {type(exc).__name__}: {exc}")
                log.warning("llm.request.failed", task=task, tier=tier.name, provider=tier.provider, error=str(exc))
        raise ModelSelectionError(f"All configured model tiers failed for {task}: {'; '.join(errors)}")

    async def _request(self, *, provider: str, model: str, task: str,
                       messages: list[dict[str, Any]], system_prompt: str | None,
                       max_tokens: int, timeout: float,
                       tools: list[dict[str, Any]] | None, json_mode: bool,
                       images: list[tuple[bytes, str]]) -> ModelResult:
        if provider in {"ollama", "local"}:
            if not self.settings.ollama_base_url:
                raise ModelSelectionError("OLLAMA_BASE_URL is empty for this runtime")
            api_messages = _ollama_messages(messages, system_prompt, images)
            payload: dict[str, Any] = {"model": model, "messages": api_messages, "stream": False}
            if json_mode:
                payload["format"] = "json"
            if tools:
                payload["tools"] = [_to_ollama_tool(t) for t in tools]
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            message = data.get("message") or {}
            return ModelResult(
                text=message.get("content") or "", model=model, provider="ollama",
                tool_calls=message.get("tool_calls") or [], assistant_message=message, raw=data,
                usage={"prompt_tokens": int(data.get("prompt_eval_count") or 0),
                       "completion_tokens": int(data.get("eval_count") or 0)},
            )

        if provider != "openrouter":
            raise ModelSelectionError(f"Unsupported LLM provider: {provider}")
        if not self.settings.openrouter_api_key:
            raise ModelSelectionError("OPENROUTER_API_KEY is not configured")
        api_messages = _openrouter_messages(messages, system_prompt, images)
        payload = {"model": model, "messages": api_messages, "max_tokens": max_tokens}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = [_to_openai_tool(t) for t in tools]
            payload["tool_choice"] = "auto"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openrouter_api_key}",
                         "HTTP-Referer": self.settings.frontend_url, "X-Title": f"FlipFlop {task}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []
        usage = data.get("usage") or {}
        return ModelResult(
            text=message.get("content") or "", model=data.get("model") or model,
            provider="openrouter", tool_calls=calls, assistant_message=message, raw=data,
            usage={"prompt_tokens": int(usage.get("prompt_tokens") or 0),
                   "completion_tokens": int(usage.get("completion_tokens") or 0)},
        )


def _vision_capable(model: str) -> bool:
    return any(tag in model.lower() for tag in ("vl", "vision", "llava", "minicpm-v", "gemma3"))


def _ollama_messages(messages: list[dict[str, Any]], system_prompt: str | None,
                     images: list[tuple[bytes, str]]) -> list[dict[str, Any]]:
    result = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [dict(m) for m in messages]
    if images:
        target = next((m for m in reversed(result) if m.get("role") == "user"), None)
        if target is None:
            target = {"role": "user", "content": ""}
            result.append(target)
        target["images"] = [base64.b64encode(data).decode("ascii") for data, _ in images]
    return result


def _openrouter_messages(messages: list[dict[str, Any]], system_prompt: str | None,
                         images: list[tuple[bytes, str]]) -> list[dict[str, Any]]:
    result = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [dict(m) for m in messages]
    if images:
        target = next((m for m in reversed(result) if m.get("role") == "user"), None)
        if target is None:
            target = {"role": "user", "content": ""}
            result.append(target)
        text = target.get("content", "")
        content = [{"type": "text", "text": text}] if isinstance(text, str) else text
        content.extend({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"}}
                       for data, mime in images)
        target["content"] = content
    return result


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    if tool.get("type") == "function" and "function" in tool:
        return tool
    return {"type": "function", "function": {
        "name": tool["name"], "description": tool.get("description", ""),
        "parameters": tool.get("input_schema", tool.get("parameters", {"type": "object", "properties": {}})),
    }}


def _to_ollama_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return _to_openai_tool(tool)


async def _cheapest_openrouter_model(settings: Settings, vision: bool, tools: bool) -> str:
    global _MODEL_CACHE
    now = time.monotonic()
    if _MODEL_CACHE is None or now - _MODEL_CACHE[0] > 3600:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            _MODEL_CACHE = (now, resp.json().get("data", []))
    candidates: list[tuple[float, str]] = []
    for item in _MODEL_CACHE[1]:
        model_id = str(item.get("id") or "")
        pricing = item.get("pricing") or {}
        modalities = (item.get("architecture") or {}).get("input_modalities") or []
        params = item.get("supported_parameters") or []
        try:
            prompt_cost = float(pricing.get("prompt") or 0)
            output_cost = float(pricing.get("completion") or 0)
        except (ValueError, TypeError):
            continue
        if not model_id or model_id.endswith(":free") or prompt_cost <= 0 or output_cost <= 0:
            continue
        if vision and "image" not in modalities:
            continue
        if tools and "tools" not in params and "tool_choice" not in params:
            continue
        candidates.append((prompt_cost + output_cost, model_id))
    if not candidates:
        raise ModelSelectionError("OpenRouter model catalogue has no compatible paid model")
    return min(candidates)[1]


model_selection_service = ModelSelectionService()
