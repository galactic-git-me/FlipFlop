"""
Priority proxy so production Ollama requests (Andromeda, via the SSH tunnel
straight to :11434) never wait behind local development requests on the same
GPU (a single RTX 3070 shared by both).

Ollama itself has no request-priority/QoS concept -- it's first-come,
first-served across a shared queue (OLLAMA_MAX_QUEUE) and a small number of
parallel slots (OLLAMA_NUM_PARALLEL). Production talks to Ollama directly on
:11434 (unchanged -- the tunnel and Andromeda's config need zero changes).
This proxy sits on a SEPARATE port (:11436) that only the local DEV backend
is configured to use (flipflop-api/.env.development.local's OLLAMA_BASE_URL).

Behavior: before forwarding a dev request, the proxy polls Ollama's own
/api/ps (currently-loaded/running models) and waits (with a bounded timeout)
while something is already running that this proxy didn't itself just start
-- in practice, that's almost always production's scan, since dev's own
requests all funnel through this same single-flight gate. This is an
approximation, not true queue-jumping (Ollama has no API to preempt an
in-flight generation), but it prevents dev from ever piling NEW work in front
of an active production request, which is the actual risk: an idle GPU with
one dev request queued, then a production burst arrives and has to wait
behind it.

Run as a Windows Service (NSSM) alongside OllamaService -- see
scripts/install-ollama-dev-proxy-service.ps1.
"""
import http.server
import json
import socketserver
import threading
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11434"
PROXY_PORT = 11436
# How long the proxy will hold a dev request back while production appears
# to be actively using the GPU, before forwarding anyway (never fully starve
# dev -- a stuck production job must not permanently block local work).
MAX_WAIT_SECONDS = 45
POLL_INTERVAL_SECONDS = 0.5

# Set while THIS proxy has a request in flight, so it can tell "something
# else (production) is running" apart from "my own forwarded request is
# running" when polling /api/ps.
_inflight_lock = threading.Lock()
_inflight_count = 0


def _ollama_has_external_activity() -> bool:
    """True if Ollama reports a running model this proxy didn't itself start."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=3) as resp:
            data = json.loads(resp.read())
    except Exception:
        # If Ollama is unreachable, don't block dev on that -- let the real
        # forward attempt fail/succeed on its own below.
        return False
    running = data.get("models", [])
    with _inflight_lock:
        mine = _inflight_count
    # Ollama's /api/ps doesn't attribute a running model to a caller, so this
    # is a coarse signal: any running model while we have zero in-flight
    # requests of our own is treated as external (production) activity.
    return bool(running) and mine == 0


def _wait_for_clear_gpu() -> None:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not _ollama_has_external_activity():
            return
        time.sleep(POLL_INTERVAL_SECONDS)


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self, method: str) -> None:
        global _inflight_count
        _wait_for_clear_gpu()

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else None

        target = f"{OLLAMA_URL}{self.path}"
        req = urllib.request.Request(target, data=body, method=method)
        for header, value in self.headers.items():
            if header.lower() in ("host", "content-length"):
                continue
            req.add_header(header, value)

        with _inflight_lock:
            _inflight_count += 1
        try:
            with urllib.request.urlopen(req, timeout=300) as upstream:
                self.send_response(upstream.status)
                for header, value in upstream.headers.items():
                    if header.lower() in ("transfer-encoding", "connection"):
                        continue
                    self.send_header(header, value)
                self.end_headers()
                while True:
                    chunk = upstream.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.end_headers()
            self.wfile.write(exc.read())
        except Exception as exc:  # noqa: BLE001 - report upstream failure to caller
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"ollama-dev-proxy: {exc}"}).encode())
        finally:
            with _inflight_lock:
                _inflight_count -= 1

    def do_GET(self) -> None:
        self._proxy("GET")

    def do_POST(self) -> None:
        self._proxy("POST")

    def do_DELETE(self) -> None:
        self._proxy("DELETE")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # NSSM captures stdout/stderr separately; keep this quiet.


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"ollama-dev-proxy listening on 127.0.0.1:{PROXY_PORT} -> {OLLAMA_URL}")
    server.serve_forever()
