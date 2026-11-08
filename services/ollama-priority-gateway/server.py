"""Priority-aware streaming gateway for the shared Ollama GPU service."""

from __future__ import annotations

import asyncio
import hmac
import itertools
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


UPSTREAM = os.getenv("OLLAMA_UPSTREAM_URL", "http://127.0.0.1:11433").rstrip("/")
MAX_QUEUE = int(os.getenv("OLLAMA_GATEWAY_MAX_QUEUE", "100"))
GENERATION_CONCURRENCY = max(1, int(os.getenv("OLLAMA_GATEWAY_CONCURRENCY", "4")))
OLLAMA_NUM_PARALLEL = max(1, int(os.getenv("OLLAMA_NUM_PARALLEL", "4")))
QUEUE_WAIT_SECONDS = max(1, float(os.getenv("OLLAMA_GATEWAY_QUEUE_WAIT_SECONDS", "300")))
UPSTREAM_READ_SECONDS = max(1, float(os.getenv("OLLAMA_GATEWAY_READ_TIMEOUT_SECONDS", "300")))
GENERATION_PATHS = {"/api/chat", "/api/generate", "/api/embed", "/api/embeddings"}
READ_ONLY_PATHS = {"/api/tags", "/api/version", "/api/ps"}
FULL_QUEUE_STALL_SECONDS = max(60, float(os.getenv("OLLAMA_GATEWAY_FULL_QUEUE_STALL_SECONDS", "600")))
UPSTREAM_CLOSE_SECONDS = max(1, float(os.getenv("OLLAMA_GATEWAY_UPSTREAM_CLOSE_SECONDS", "5")))
MAINTENANCE_TOKEN = os.getenv("OLLAMA_GATEWAY_MAINTENANCE_TOKEN", "")

logger = logging.getLogger("ollama_priority_gateway")


def _observe_close_task(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error("gateway.upstream_close_failed error=%s", error)


async def _close_with_timeout(response: httpx.Response) -> None:
    """Bound capacity release even if an upstream close ignores cancellation."""
    close_task = asyncio.create_task(response.aclose())
    done, _ = await asyncio.wait({close_task}, timeout=UPSTREAM_CLOSE_SECONDS)
    if close_task not in done:
        close_task.cancel()
        close_task.add_done_callback(_observe_close_task)
        logger.error("gateway.upstream_close_timed_out seconds=%s", UPSTREAM_CLOSE_SECONDS)
        return
    _observe_close_task(close_task)


class ManagedBody:
    """Own the upstream and capacity even before streaming has started."""

    def __init__(self, response: httpx.Response, release: Callable[[], None], on_progress: Callable[[], None] | None = None) -> None:
        self.response = response
        self.release = release
        self.on_progress = on_progress
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self.response.aiter_raw():
                if self.on_progress is not None:
                    self.on_progress()
                yield chunk
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            await _close_with_timeout(self.response)
        except asyncio.CancelledError:
            raise
        finally:
            self.release()


class ManagedStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # An async generator's finally block never runs if it was closed
            # before its first iteration. Close the owner explicitly instead.
            await self.body_iterator.aclose()


@dataclass
class QueuedRequest:
    priority: int
    sequence: int
    method: str
    path: str
    query: str
    body: bytes
    headers: dict[str, str]
    result: asyncio.Future[tuple[int, dict[str, str], ManagedBody]]
    deadline_seconds: float | None = None
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)


class PriorityForwarder:
    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, QueuedRequest]] = asyncio.PriorityQueue()
        self._sequence = itertools.count()
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._client: httpx.AsyncClient | None = None
        self._generation_slots = asyncio.Semaphore(GENERATION_CONCURRENCY)
        self._model_load_locks: dict[str, asyncio.Lock] = {}
        self._last_completed_at = time.monotonic()
        self._last_progress_at = self._last_completed_at
        self._completed_requests = 0
        self._full_queue_since: float | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self._admission_lock = asyncio.Lock()
        self._admissions_paused = False

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(
            connect=10, read=UPSTREAM_READ_SECONDS, write=30, pool=10))
        self._worker_tasks = [
            asyncio.create_task(self._worker(), name=f"ollama-priority-worker-{index + 1}")
            for index in range(GENERATION_CONCURRENCY)
        ]
        self._watchdog_task = asyncio.create_task(self._watch_full_stalled_queue(), name="ollama-priority-watchdog")

    async def stop(self) -> None:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            await asyncio.gather(self._watchdog_task, return_exceptions=True)
            self._watchdog_task = None
        for task in self._worker_tasks:
            task.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        if self._client:
            await self._client.aclose()

    async def pause_admission(self) -> None:
        async with self._admission_lock:
            self._admissions_paused = True

    async def resume_admission(self) -> None:
        async with self._admission_lock:
            self._admissions_paused = False

    def record_completion(self) -> None:
        self._completed_requests += 1
        self._last_completed_at = time.monotonic()
        self.record_progress()

    def record_progress(self) -> None:
        self._last_progress_at = time.monotonic()

    def should_restart_stalled_queue(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if self._queue.qsize() < MAX_QUEUE:
            self._full_queue_since = None
            return False
        if self._full_queue_since is None:
            self._full_queue_since = now
            return False
        return now - self._full_queue_since >= FULL_QUEUE_STALL_SECONDS and now - self._last_progress_at >= FULL_QUEUE_STALL_SECONDS

    def queue_state(self) -> dict[str, object]:
        now = time.monotonic()
        depth = self._queue.qsize()
        if depth >= MAX_QUEUE:
            if self._full_queue_since is None:
                self._full_queue_since = now
        else:
            self._full_queue_since = None
        return {
            "queue_depth": depth,
            "queue_limit": MAX_QUEUE,
            "active_generations": GENERATION_CONCURRENCY - self._generation_slots._value,
            "workers": [
                {"name": task.get_name(), "state": "running" if not task.done() else "stopped"}
                for task in self._worker_tasks
            ],
            "completed_requests": self._completed_requests,
            "seconds_since_completion": round(now - self._last_completed_at, 1),
            "seconds_since_progress": round(now - self._last_progress_at, 1),
            "full_queue_seconds": round(now - self._full_queue_since, 1) if self._full_queue_since is not None else 0,
            "admission_paused": self._admissions_paused,
        }

    async def _close_upstream(self, upstream: httpx.Response | None) -> None:
        if upstream is None:
            return
        try:
            await _close_with_timeout(upstream)
        except asyncio.CancelledError:
            raise

    async def _watch_full_stalled_queue(self) -> None:
        """Restart only this gateway after a continuously full, non-progressing queue."""
        while True:
            await asyncio.sleep(5)
            depth = self._queue.qsize()
            now = time.monotonic()
            if self.should_restart_stalled_queue(now):
                logger.critical(
                    "gateway.full_queue_stalled_restart queue_depth=%s queue_limit=%s active_generations=%s completed_requests=%s seconds_since_progress=%.1f stall_seconds=%s",
                    depth,
                    MAX_QUEUE,
                    GENERATION_CONCURRENCY - self._generation_slots._value,
                    self._completed_requests,
                    now - self._last_progress_at,
                    FULL_QUEUE_STALL_SECONDS,
                )
                # The parent supervisor restarts only this gateway, leaving Ollama alive.
                os._exit(75)

    async def gpu_request_body(self, body: bytes) -> bytes:
        """Ensure the requested model is fully GPU resident before forwarding user input."""
        payload = json.loads(body)
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            raise HTTPException(422, "A local model name is required")
        options = {**(payload.get("options") or {}), "num_gpu": 999}
        assert self._client is not None
        names = {model, model if ":" in model else f"{model}:latest"}

        async def get_resident_model() -> dict | None:
            state = await self._client.get(f"{UPSTREAM}/api/ps", timeout=10)
            state.raise_for_status()
            return next((m for m in state.json().get("models", [])
                if m.get("name") in names or m.get("model") in names), None)

        model_lock = self._model_load_locks.setdefault(model, asyncio.Lock())
        async with model_lock:
            resident = await get_resident_model()
            if not resident or not resident.get("size") or resident.get("size_vram", 0) < resident["size"]:
                # Ollama's empty-prompt generate call can keep generating forever.
                # Use one harmless token only when the model is absent or not fully
                # resident, then verify actual VRAM placement before passing user input.
                warmup_options = {**options, "num_predict": 1}
                loaded = await self._client.post(f"{UPSTREAM}/api/generate", json={
                    "model": model,
                    "prompt": ".",
                    "stream": False,
                    "keep_alive": -1,
                    "options": warmup_options,
                }, timeout=120)
                loaded.raise_for_status()
                resident = await get_resident_model()
        if not resident or not resident.get("size") or resident.get("size_vram", 0) < resident["size"]:
            raise HTTPException(503, "GPU-only inference required: model is not fully resident on the GPU. CPU fallback is blocked; check Ollama GPU discovery and available VRAM.")
        payload["options"] = options
        payload["keep_alive"] = -1
        return json.dumps(payload).encode()

    async def submit(
        self,
        *,
        priority: int,
        method: str,
        path: str,
        query: str,
        body: bytes,
        headers: dict[str, str],
        deadline_seconds: float | None = None,
    ) -> tuple[int, dict[str, str], ManagedBody]:
        self.prune_cancelled()
        loop = asyncio.get_running_loop()
        result: asyncio.Future[tuple[int, dict[str, str], ManagedBody]] = loop.create_future()
        async with self._admission_lock:
            if self._admissions_paused:
                raise HTTPException(status_code=503, detail="Ollama gateway is pausing for recovery")
            if self._queue.qsize() >= MAX_QUEUE:
                raise HTTPException(status_code=503, detail="Ollama priority queue is full")
            request = QueuedRequest(
                priority=priority,
                sequence=next(self._sequence),
                method=method,
                path=path,
                query=query,
                body=body,
                headers=headers,
                result=result,
                deadline_seconds=deadline_seconds,
            )
            self._queue.put_nowait((priority, request.sequence, request))
        try:
            return await asyncio.wait_for(result, timeout=deadline_seconds or QUEUE_WAIT_SECONDS)
        except TimeoutError as exc:
            request.cancelled.set()
            result.cancel()
            detail = "Ollama request exceeded its watchdog deadline" if deadline_seconds else "Ollama request exceeded its waiting deadline"
            raise HTTPException(504, detail) from exc
        except asyncio.CancelledError:
            # The worker skips cancelled futures when it reaches them.
            request.cancelled.set()
            result.cancel()
            raise

    @staticmethod
    async def _await_or_cancel(awaitable, cancelled: asyncio.Event):
        """Cancel an in-flight upstream operation when its bounded caller expires."""
        operation = asyncio.create_task(awaitable)
        cancel_wait = asyncio.create_task(cancelled.wait())
        try:
            done, _ = await asyncio.wait(
                {operation, cancel_wait}, return_when=asyncio.FIRST_COMPLETED
            )
            if cancel_wait in done:
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
                return None
            return operation.result()
        except BaseException:
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            raise
        finally:
            if not cancel_wait.done():
                cancel_wait.cancel()
            await asyncio.gather(cancel_wait, return_exceptions=True)

    def prune_cancelled(self) -> None:
        """Expired/disconnected callers must not occupy admission capacity."""
        live = []
        while not self._queue.empty():
            item = self._queue.get_nowait()
            if item[2].result.done():
                self._queue.task_done()
            else:
                live.append(item)
        for item in live:
            self._queue.put_nowait(item)
            self._queue.task_done()

    async def _worker(self) -> None:
        while True:
            _, _, request = await self._queue.get()
            slot_acquired = False
            slot_transferred_to_stream = False
            upstream = None
            try:
                await self._generation_slots.acquire()
                slot_acquired = True
                if request.result.cancelled():
                    continue

                assert self._client is not None
                if request.deadline_seconds is None:
                    request.body = await self.gpu_request_body(request.body)
                else:
                    prepared_body = await self._await_or_cancel(
                        self.gpu_request_body(request.body), request.cancelled
                    )
                    if prepared_body is None:
                        continue
                    request.body = prepared_body
                if request.result.done():
                    continue
                upstream_request = self._client.build_request(
                    request.method,
                    f"{UPSTREAM}{request.path}{request.query}",
                    content=request.body,
                    headers=request.headers,
                )
                if request.deadline_seconds is None:
                    upstream = await self._client.send(upstream_request, stream=True)
                else:
                    upstream = await self._await_or_cancel(
                        self._client.send(upstream_request, stream=True), request.cancelled
                    )
                    if upstream is None:
                        continue

                if request.result.done():
                    continue

                def release() -> None:
                    self.record_completion()
                    self._generation_slots.release()
                    self._queue.task_done()

                response_headers = {
                    key: value
                    for key, value in upstream.headers.items()
                    if key.lower() in {"content-type", "content-encoding", "cache-control"}
                }
                request.result.set_result((upstream.status_code, response_headers, ManagedBody(upstream, release, self.record_progress)))
                slot_transferred_to_stream = True
            except Exception as exc:  # noqa: BLE001 - forwarded to the caller
                if not request.result.done():
                    request.result.set_exception(
                        exc if isinstance(exc, HTTPException) else HTTPException(status_code=502, detail=f"Ollama upstream unavailable: {exc}")
                    )
            finally:
                if not slot_transferred_to_stream:
                    try:
                        await self._close_upstream(upstream)
                    finally:
                        if slot_acquired:
                            self._generation_slots.release()
                        if not request.result.done():
                            request.result.set_exception(HTTPException(502, "Ollama request failed before streaming began"))
                        self._queue.task_done()


forwarder = PriorityForwarder()
_forwarder_start_lock = asyncio.Lock()


def create_app(priority: int, name: str) -> FastAPI:
    app = FastAPI(title=f"Ollama priority gateway ({name})")

    @app.on_event("startup")
    async def startup() -> None:
        async with _forwarder_start_lock:
            if not forwarder._worker_tasks:
                await forwarder.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        # Both listeners share the process. Uvicorn's first shutdown must not
        # close the shared forwarder while the other listener is still live.
        return None

    @app.get("/health")
    async def health() -> JSONResponse:
        forwarder.prune_cancelled()
        return JSONResponse({
            "status": "ok",
            **forwarder.queue_state(),
            "priority": name,
            "generation_concurrency": GENERATION_CONCURRENCY,
            "queue_wait_seconds": QUEUE_WAIT_SECONDS,
            "upstream_read_timeout_seconds": UPSTREAM_READ_SECONDS,
            "ollama_num_parallel": OLLAMA_NUM_PARALLEL,
            "gpu_only": True,
        })

    @app.post("/_maintenance/{action}")
    async def maintenance(action: str, request: Request) -> JSONResponse:
        supplied = request.headers.get("x-ollama-maintenance-token", "")
        if not MAINTENANCE_TOKEN or not hmac.compare_digest(supplied, MAINTENANCE_TOKEN):
            raise HTTPException(status_code=403, detail="Maintenance authorization failed")
        if action == "pause":
            await forwarder.pause_admission()
        elif action == "resume":
            await forwarder.resume_admission()
        else:
            raise HTTPException(status_code=404, detail="Unknown maintenance action")
        return JSONResponse({"admission_paused": forwarder._admissions_paused})

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy(request: Request, path: str):
        route = f"/{path}"
        body = await request.body()
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }

        probe_timeout = headers.pop("x-ollama-watchdog-timeout-seconds", None)
        maintenance_token = headers.pop("x-ollama-maintenance-token", "")
        deadline_seconds = None
        if probe_timeout is not None:
            if not MAINTENANCE_TOKEN or not hmac.compare_digest(maintenance_token, MAINTENANCE_TOKEN):
                raise HTTPException(403, "Watchdog probe authorization failed")
            try:
                deadline_seconds = float(probe_timeout)
            except ValueError as exc:
                raise HTTPException(422, "Watchdog timeout must be a positive number of seconds") from exc
            if deadline_seconds <= 0 or deadline_seconds > min(QUEUE_WAIT_SECONDS, UPSTREAM_READ_SECONDS):
                raise HTTPException(422, "Watchdog timeout is outside the allowed gateway deadline")

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
            deadline_seconds=deadline_seconds,
        )
        return ManagedStreamingResponse(stream, status_code=status, headers=response_headers)

    return app


async def serve() -> None:
    other = uvicorn.Server(
        uvicorn.Config(create_app(2, "other"), host=os.getenv("OTHER_LISTEN_HOST", "127.0.0.1"), port=int(os.getenv("OTHER_LISTEN_PORT", "11434")), log_level="info")
    )
    dev = uvicorn.Server(
        uvicorn.Config(create_app(1, "dev"), host=os.getenv("DEV_LISTEN_HOST", "127.0.0.1"), port=int(os.getenv("DEV_LISTEN_PORT", "11435")), log_level="info")
    )
    prod = uvicorn.Server(
        uvicorn.Config(create_app(0, "production"), host=os.getenv("PROD_LISTEN_HOST", "127.0.0.1"), port=int(os.getenv("PROD_LISTEN_PORT", "11436")), log_level="info")
    )
    await asyncio.gather(other.serve(), dev.serve(), prod.serve())


def supervise_gateway() -> None:
    gateway_script = Path(__file__).resolve()
    repo_root = gateway_script.parents[2]
    child = None
    while True:
        try:
            child = subprocess.Popen(
                [sys.executable, str(gateway_script), "--gateway-child"],
                cwd=repo_root,
            )
            exit_code = child.wait()
        except KeyboardInterrupt:
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
            raise
        if exit_code == 0:
            return
        logger.error("gateway.child_exited_restarting exit_code=%s", exit_code)
        time.sleep(min(30, max(5, abs(exit_code))))


if __name__ == "__main__":
    if "--gateway-child" in sys.argv:
        asyncio.run(serve())
    else:
        supervise_gateway()
