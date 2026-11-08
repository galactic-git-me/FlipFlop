"""End-to-end tests for the Windows watchdog using fake HTTP and restart endpoints."""
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
SCRIPT = Path(__file__).with_name("ollama-recovery-watchdog.ps1")


class Handler(BaseHTTPRequestHandler):
    queue_depth = 0
    active = 0
    fail_generation = False
    post_count = 0
    admission_paused = False
    busy_after_pause = False

    def log_message(self, *_args):
        pass

    def do_GET(self):
        body = json.dumps({"status": "ok", "queue_depth": self.queue_depth,
            "active_generations": self.active, "admission_paused": self.admission_paused}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/_maintenance/") and self.headers.get("X-Ollama-Maintenance-Token") != "test-token":
            self.send_error(403)
            return
        if self.path == "/_maintenance/pause":
            type(self).admission_paused = True
            if self.busy_after_pause:
                type(self).active = 1
            body = json.dumps({"admission_paused": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/_maintenance/resume":
            type(self).admission_paused = False
            type(self).active = 0
            body = json.dumps({"admission_paused": False}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        type(self).post_count += 1
        if self.fail_generation:
            self.send_error(503)
            return
        body = json.dumps({"message": {"content": "OK"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(POWERSHELL, "PowerShell is required to execute the Windows watchdog")
class OllamaRecoveryWatchdog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.health_url = f"http://127.0.0.1:{cls.httpd.server_port}/health"
        cls.generation_url = f"http://127.0.0.1:{cls.httpd.server_port}/api/chat"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)

    def setUp(self):
        Handler.queue_depth = 0
        Handler.active = 0
        Handler.fail_generation = False
        Handler.post_count = 0
        Handler.admission_paused = False
        Handler.busy_after_pause = False
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state.json"
        self.token = self.root / "maintenance-token.txt"
        self.token.write_text("test-token")
        self.launcher = self.root / "services" / "ollama-priority-gateway" / "start-prometheus-services.ps1"
        self.launcher.parent.mkdir(parents=True)
        self.marker = self.root / "restart.marker"
        self.launcher.write_text(f"Set-Content -LiteralPath '{self.marker}' -Value restarted\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_watchdog(self, *extra):
        command = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(SCRIPT), "-ProjectRoot", str(self.root), "-StatePath", str(self.state),
            "-GatewayHealthUrl", self.health_url, "-GatewayGenerationUrl", self.generation_url,
            "-GatewayHealthUrls", self.health_url, "-GatewayMaintenanceUrl",
            self.health_url.rsplit("/", 1)[0] + "/_maintenance", "-MaintenanceTokenPath", str(self.token),
            "-FailureThreshold", "1", *extra]
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=45)
        if result.returncode:
            self.fail(f"PowerShell watchdog failed: {result.stdout}\n{result.stderr}")
        return result

    def test_successful_probe_clears_failure_streak(self):
        self.state.write_text(json.dumps({"consecutive_failures": 2, "last_restart_epoch": None}))
        self.run_watchdog()
        self.assertEqual(json.loads(self.state.read_text())["consecutive_failures"], 0)
        watchdog_log = self.root / "logs" / "ollama-recovery-watchdog.log"
        self.assertEqual(Handler.post_count, 1, watchdog_log.read_text() if watchdog_log.exists() else "no watchdog log")
        self.assertFalse(self.marker.exists())

    def test_active_queue_skips_generation_probe_and_restart(self):
        Handler.queue_depth = 3
        self.state.write_text(json.dumps({"consecutive_failures": 2, "last_restart_epoch": None}))
        self.run_watchdog()
        self.assertEqual(json.loads(self.state.read_text())["consecutive_failures"], 0)
        self.assertEqual(Handler.post_count, 0)
        self.assertFalse(self.marker.exists())

    def test_repeated_generation_failure_calls_restart_with_cooldown_state(self):
        Handler.fail_generation = True
        self.run_watchdog()
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["consecutive_failures"], 0)
        self.assertIsNotNone(saved["last_restart_epoch"], f"{saved}; {list(self.root.rglob('*.log'))}")
        self.assertTrue(self.marker.exists())

    def test_recent_restart_is_suppressed_by_cooldown(self):
        Handler.fail_generation = True
        recent_restart = int(time.time()) - 120
        self.state.write_text(json.dumps({"consecutive_failures": 0,
            "last_restart_epoch": recent_restart}))
        self.run_watchdog()
        saved = json.loads(self.state.read_text())
        watchdog_log = self.root / "logs" / "ollama-recovery-watchdog.log"
        self.assertEqual(saved["consecutive_failures"], 1,
            f"{saved}; {watchdog_log.read_text() if watchdog_log.exists() else 'no log'}")
        self.assertEqual(saved["last_restart_epoch"], recent_restart)
        self.assertFalse(self.marker.exists())

    def test_restart_is_deferred_when_work_arrives_before_maintenance_check(self):
        Handler.fail_generation = True
        Handler.busy_after_pause = True
        self.run_watchdog()
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["consecutive_failures"], 1)
        self.assertFalse(saved.get("last_restart_epoch"))
        self.assertFalse(self.marker.exists())
        self.assertFalse(Handler.admission_paused)


if __name__ == "__main__":
    unittest.main()
