"""Priority-aware streaming gateway for the shared Ollama GPU service."""

from __future__ import annotations

import asyncio
import itertools
import os
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


UPSTREAM = os.getenv("OLLAMA_UPSTREAM_URL", "http://127.0.0.1:11433").rstrip("/")
MAX_QUEUE = int(os.getenv("OLLAMA_GATEWAY_MAX_QUEUE", "100"))
GENERATION_PATHS = {"/api/chat", "/api/generate", "/api/embed", "/api/embeddings"}
READ_ONLY_PATHS = {"/api/tags", "/api/version", "/api/ps"}


@dataclass
class QueuedRequest:
    priority: int
    sequence: int
    method: str
    path: str
    query: str
    body: bytes
    headers: dict[str, str]
    result: asyncio.Future[tuple[int, dict[str, str], AsyncIterator[bytes]]]


class PriorityForwarder:
    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, QueuedRequest]] = asyncio.PriorityQueue()
        self._sequence = itertools.count()
        self._worker_task: asyncio.Task[None] | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=None)
        self._worker_task = asyncio.create_task(self._worker(), name="ollama-priority-worker")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
        if self._client:
            await self._client.aclose()

    async def submit(
        self,
        *,
        priority: int,
        method: str,
        path: str,
        query: str,
        body: bytes,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
        if self._queue.qsize() >= MAX_QUEUE:
            raise HTTPException(status_code=503, detail="Ollama priority queue is full")

        loop = asyncio.get_running_loop()
        result: asyncio.Future[tuple[int, dict[str, str], AsyncIterator[bytes]]] = loop.create_future()
        request = QueuedRequest(
            priority=priority,
            sequence=next(self._sequence),
            method=method,
            path=path,
            query=query,
            body=body,
            headers=headers,
            result=result,
        )
        await self._queue.put((priority, request.sequence, request))
        try:
            return await result
        except asyncio.CancelledError:
            # The worker skips cancelled futures when it reaches them.
            raise

    async def _worker(self) -> None:
        while True:
            _, _, request = await self._queue.get()
            if request.result.cancelled():
                self._queue.task_done()
                continue

            try:
                assert self._client is not None
                upstream = await self._client.stream(
                    request.method,
                    f"{UPSTREAM}{request.path}{request.query}",
                    content=request.body,
                    headers=request.headers,
                ).__aenter__()

                async def body_stream() -> AsyncIterator[bytes]:
                    try:
                        async for chunk in upstream.aiter_raw():
                            yield chunk
                    finally:
                        await upstream.aclose()
                        self._queue.task_done()

                response_headers = {
                    key: value
                    for key, value in upstream.headers.items()
                    if key.lower() in {"content-type", "content-encoding", "cache-control"}
                }
                request.result.set_result((upstream.status_code, response_headers, body_stream()))
            except Exception as exc:  # noqa: BLE001 - forwarded to the caller
                if not request.result.done():
                    request.result.set_exception(
                        HTTPException(status_code=502, detail=f"Ollama upstream unavailable: {exc}")
                    )
                self._queue.task_done()


forwarder = PriorityForwarder()
_forwarder_start_lock = asyncio.Lock()


def create_app(priority: int, name: str) -> FastAPI:
    app = FastAPI(title=f"Ollama priority gateway ({name})")

    @app.on_event("startup")
    async def startup() -> None:
        async with _forwarder_start_lock:
            if forwarder._worker_task is None:
                await forwarder.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        # Both listeners share the process. Uvicorn's first shutdown must not
        # close the shared forwarder while the other listener is still live.
        return None

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "queue_depth": forwarder._queue.qsize(), "priority": name})

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy(request: Request, path: str):
        route = f"/{path}"
        body = await request.body()
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }

        if route in READ_ONLY_PATHS or route not in GENERATION_PATHS:
            assert forwarder._client is not None
            response = await forwarder._client.request(
                request.method,
                f"{UPSTREAM}{route}",
                params=request.query_params,
                content=body,
                headers=headers,
            )
            return JSONResponse(
                content=response.json() if response.content else None,
                status_code=response.status_code,
                headers={"content-type": response.headers.get("content-type", "application/json")},
            )

        status, response_headers, stream = await forwarder.submit(
            priority=priority,
            method=request.method,
            path=route,
            query=(f"?{request.url.query}" if request.url.query else ""),
            body=body,
            headers=headers,
        )
        return StreamingResponse(stream, status_code=status, headers=response_headers)

    return app


async def serve() -> None:
    other = uvicorn.Server(
        uvicorn.Config(create_app(2, "other"), host=os.getenv("OTHER_LISTEN_HOST", "127.0.0.1"), port=int(os.getenv("OTHER_LISTEN_PORT", "11434")), log_level="info")
    )
    dev = uvicorn.Server(
        uvicorn.Config(create_app(1, "dev"), host=os.getenv("DEV_LISTEN_HOST", "127.0.0.1"), port=int(os.getenv("DEV_LISTEN_PORT", "11435")), log_level="info")
    )
    prod = uvicorn.Server(
        uvicorn.Config(create_app(0, "production"), host=os.getenv("PROD_LISTEN_HOST", "0.0.0.0"), port=int(os.getenv("PROD_LISTEN_PORT", "11436")), log_level="info")
    )
    await asyncio.gather(other.serve(), dev.serve(), prod.serve())


if __name__ == "__main__":
    asyncio.run(serve())
