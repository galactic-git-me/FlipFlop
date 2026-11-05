"""Deterministic GPU-only guard checks; no Ollama inference or restart."""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import httpx
from fastapi import HTTPException

path = Path(__file__).with_name("server.py")
spec = importlib.util.spec_from_file_location("gpu_gateway_contract", path)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


async def main():
    # An already resident model must not trigger any warm-up generation.
    calls = []

    def resident(request):
        calls.append(request)
        assert request.url.path == "/api/ps"
        return httpx.Response(200, json={"models": [
            {"name": "fixture:latest", "model": "fixture:latest", "size": 100, "size_vram": 100}
        ]})

    f = m.PriorityForwarder()
    async with httpx.AsyncClient(transport=httpx.MockTransport(resident)) as client:
        f._client = client
        body = await f.gpu_request_body(json.dumps({
            "model": "fixture",
            "messages": [{"role": "user", "content": "private prompt"}],
            "options": {"num_gpu": 0},
        }).encode())
    assert len(calls) == 1
    forwarded = json.loads(body)
    assert forwarded["options"]["num_gpu"] == 999
    assert forwarded["messages"][0]["content"] == "private prompt"

    # A missing model gets a bounded, generic warm-up and must be rechecked.
    calls = []
    ps_responses = iter([
        {"models": []},
        {"models": [{"name": "fixture:latest", "model": "fixture:latest", "size": 100, "size_vram": 100}]},
    ])

    def needs_load(request):
        calls.append(request)
        if request.url.path == "/api/ps":
            return httpx.Response(200, json=next(ps_responses))
        assert request.url.path == "/api/generate"
        warmup = json.loads(request.content)
        assert warmup["prompt"] == "."
        assert warmup["options"]["num_gpu"] == 999
        assert warmup["options"]["num_predict"] == 1
        assert "messages" not in warmup
        assert "private prompt" not in request.content.decode()
        return httpx.Response(200, json={"done": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(needs_load)) as client:
        f._client = client
        body = await f.gpu_request_body(json.dumps({
            "model": "fixture",
            "messages": [{"role": "user", "content": "private prompt"}],
            "options": {"num_gpu": 0, "num_predict": 256},
        }).encode())
    assert [request.url.path for request in calls] == ["/api/ps", "/api/generate", "/api/ps"]
    assert json.loads(body)["options"]["num_predict"] == 256

    # Concurrent cold requests for the same model must share one warm-up.
    loaded = False
    warmups = 0

    async def concurrent_cold(request):
        nonlocal loaded, warmups
        if request.url.path == "/api/ps":
            await asyncio.sleep(0.01)
            models = ([{"name": "fixture:latest", "model": "fixture:latest", "size": 100, "size_vram": 100}]
                      if loaded else [])
            return httpx.Response(200, json={"models": models})
        warmups += 1
        await asyncio.sleep(0.02)
        loaded = True
        return httpx.Response(200, json={"done": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(concurrent_cold)) as client:
        f._client = client
        request_body = json.dumps({"model": "fixture", "messages": []}).encode()
        await asyncio.gather(f.gpu_request_body(request_body), f.gpu_request_body(request_body))
    assert warmups == 1

    # Reject both CPU-only and partial GPU placement after the bounded warm-up.
    for vram in (0, 50):
        ps_responses = iter([
            {"models": []},
            {"models": [{"name": "fixture:latest", "model": "fixture:latest", "size": 100, "size_vram": vram}]},
        ])

        def remains_off_gpu(request):
            if request.url.path == "/api/ps":
                return httpx.Response(200, json=next(ps_responses))
            return httpx.Response(200, json={"done": True})

        async with httpx.AsyncClient(transport=httpx.MockTransport(remains_off_gpu)) as client:
            f._client = client
            try:
                await f.gpu_request_body(json.dumps({"model": "fixture", "messages": []}).encode())
            except HTTPException as exc:
                assert exc.status_code == 503
            else:
                raise AssertionError("CPU or partial GPU placement must be rejected")

    print("PASS: resident models skip warm-up; missing models use one bounded generic token; user prompts stay isolated; CPU/partial placement is rejected")


asyncio.run(main())
