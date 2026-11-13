"""Windows-friendly API launcher with source auto-reload.

Uvicorn's built-in ``--reload`` watcher forces WindowsSelectorEventLoopPolicy,
which breaks Playwright browser subprocess creation. This launcher keeps the
API child on WindowsProactorEventLoopPolicy and uses watchfiles in a separate
supervisor process to restart it when Python source changes.
"""
import argparse
import asyncio
import ctypes
import ctypes.wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def configure_windows_event_loop() -> None:
    if sys.platform != "win32":
        return

    # Keep console logs reliable for marketplace titles containing emoji.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Ignore harmless connection-reset errors raised during Proactor cleanup.
    import asyncio.proactor_events as proactor_events

    original_lost = proactor_events._ProactorBasePipeTransport._call_connection_lost

    def patched_lost(self, exc):
        try:
            original_lost(self, exc)
        except (ConnectionResetError, OSError):
            pass

    proactor_events._ProactorBasePipeTransport._call_connection_lost = patched_lost


def serve(host: str, port: int) -> None:
    if os.environ.get("FLIPFLOP_TRACE_MEMORY") == "1":
        start_memory_diagnostics()

    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=False)


def start_memory_diagnostics() -> None:
    """Opt-in DEV allocation sampler; emits Python allocation stacks near a memory threshold."""
    import tracemalloc

    tracemalloc.start(5)
    process_handle = ctypes.windll.kernel32.GetCurrentProcess()

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.wintypes.DWORD),
            ("PageFaultCount", ctypes.wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.DWORD]
    get_memory.restype = ctypes.wintypes.BOOL
    print("[memory-trace] started; Python allocation tracing depth=5", flush=True)

    def sample() -> None:
        previous_snapshot_at = 0.0
        while True:
            time.sleep(15)
            if not get_memory(process_handle, ctypes.byref(counters), counters.cb):
                continue
            current, peak = tracemalloc.get_traced_memory()
            private_bytes = counters.PrivateUsage
            now = time.monotonic()
            snapshot_due = private_bytes >= 3.5 * 1024**3 or current >= 512 * 1024**2
            event = {
                "private_bytes": private_bytes,
                "working_set_bytes": counters.WorkingSetSize,
                "python_current_bytes": current,
                "python_peak_bytes": peak,
            }
            if snapshot_due and now - previous_snapshot_at >= 60:
                snapshot = tracemalloc.take_snapshot()
                event["top_python_allocations"] = [
                    {"trace": str(stat.traceback), "bytes": stat.size, "blocks": stat.count}
                    for stat in snapshot.statistics("traceback")[:20]
                ]
                previous_snapshot_at = now
            print(f"[memory-trace] {json.dumps(event, separators=(',', ':'))}", flush=True)

    threading.Thread(target=sample, name="api-memory-diagnostics", daemon=True).start()


def stop_child(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return

    if os.name == "nt":
        # Include Playwright browser processes created by this API process.
        try:
            subprocess.run(
                ["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            child.terminate()
    else:
        child.terminate()
    try:
        child.wait(timeout=8)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def relay_output(stream, changed_paths: list[str], started_at: float) -> None:
    """Condense routine reload startup chatter while retaining failures verbatim."""
    restarting = bool(changed_paths)
    for line in stream:
        if restarting and "Uvicorn running on " in line:
            elapsed = time.monotonic() - started_at
            print(f"[*] File change {', '.join(changed_paths)} detected. Restarted API; ready in {elapsed:.1f}s.", flush=True)
            restarting = False
            continue
        if changed_paths and "worker_ready" in line and "[debug" in line:
            continue
        if restarting and (line.startswith("INFO:") or "[info " in line or "[debug " in line):
            continue
        print(line, end="", flush=True)


def supervise(host: str, port: int) -> None:
    from watchfiles import PythonFilter, watch

    api_root = Path(__file__).resolve().parent
    watch_roots = (api_root / "app", Path(__file__).resolve())
    child_command = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--_serve",
        "--host",
        host,
        "--port",
        str(port),
    ]

    print(f"[*] API auto-reload watching Python files under {api_root / 'app'}", flush=True)
    child = None
    changed_paths: list[str] = []
    try:
        while True:
            started_at = time.monotonic()
            child = subprocess.Popen(child_command, cwd=api_root, env=os.environ.copy(),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
            output = threading.Thread(target=relay_output,
                                      args=(child.stdout, changed_paths, started_at), daemon=True)
            output.start()
            if not changed_paths:
                print(f"[*] API process started (pid {child.pid})", flush=True)

            restart_for_change = False
            for changes in watch(
                *watch_roots,
                watch_filter=PythonFilter(),
                debounce=500,
                step=100,
                rust_timeout=500,
                yield_on_timeout=True,
            ):
                if child.poll() is not None:
                    output.join(timeout=2)
                    print(f"[WARN] API process exited ({child.returncode}); restarting in 1 second.", flush=True)
                    changed_paths = []
                    time.sleep(1)
                    break
                if changes:
                    changed_paths = sorted({path for _, path in changes})
                    restart_for_change = True
                    break

            stop_child(child)
            output.join(timeout=2)
            child.stdout.close()
            child = None
            if not restart_for_change:
                # The child exited unexpectedly; the watch generator ended only
                # if it raised, so this path is retained for clean shutdowns.
                time.sleep(1)
    except KeyboardInterrupt:
        print("[*] Stopping API auto-reload supervisor...", flush=True)
    finally:
        if child is not None:
            stop_child(child)


def main() -> None:
    configure_windows_event_loop()

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4311)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--_serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args._serve:
        serve(args.host, args.port)
    else:
        supervise(args.host, args.port)


if __name__ == "__main__":
    main()
