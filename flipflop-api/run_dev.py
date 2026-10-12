"""Windows-friendly API launcher with source auto-reload.

Uvicorn's built-in ``--reload`` watcher forces WindowsSelectorEventLoopPolicy,
which breaks Playwright browser subprocess creation. This launcher keeps the
API child on WindowsProactorEventLoopPolicy and uses watchfiles in a separate
supervisor process to restart it when Python source changes.
"""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys
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
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=False)


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


def supervise(host: str, port: int) -> None:
    from watchfiles import PythonFilter, watch

    api_root = Path(__file__).resolve().parent
    watch_roots = (api_root / "app", Path(__file__).resolve())
    child_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--_serve",
        "--host",
        host,
        "--port",
        str(port),
    ]

    print(f"[*] API auto-reload watching Python files under {api_root / 'app'}", flush=True)
    child = None
    try:
        while True:
            child = subprocess.Popen(child_command, cwd=api_root, env=os.environ.copy())
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
                    print(f"[WARN] API process exited ({child.returncode}); restarting in 1 second.", flush=True)
                    time.sleep(1)
                    break
                if changes:
                    changed_paths = sorted({path for _, path in changes})
                    print(f"[*] Source changed; restarting API: {', '.join(changed_paths)}", flush=True)
                    restart_for_change = True
                    break

            stop_child(child)
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
