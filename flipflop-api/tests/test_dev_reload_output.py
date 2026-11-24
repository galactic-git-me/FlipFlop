import importlib.util
import io
from pathlib import Path

spec = importlib.util.spec_from_file_location("dev_launcher", Path(__file__).resolve().parents[1] / "run_dev.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_reload_emits_one_notice_only_after_server_is_listening(capsys):
    launcher.relay_output(io.StringIO(
        "INFO:     Waiting for application startup.\n"
        "2026-10-15 [info     ] scheduler.started jobs=38\n"
        "INFO:     Application startup complete.\n"
        "INFO:     Uvicorn running on http://127.0.0.1:4311 (Press CTRL+C to quit)\n"
        "2026-10-15 [debug    ] claude_eval_queue.worker_ready worker=1\n"
        "INFO:     GET /api/health 200 OK\n"
    ), ["app/example.py"], launcher.time.monotonic())
    output = capsys.readouterr().out
    assert "File change app/example.py detected. Restarted API; ready in" in output
    assert "scheduler.started" not in output
    assert "worker_ready" not in output
    assert "GET /api/health 200 OK" in output
    assert output.count("Restarted API") == 1


def test_reload_retains_warnings_errors_and_tracebacks_without_claiming_success(capsys):
    failure = "2026-10-15 [warning  ] token invalid\nERROR: Startup failed\nTraceback (most recent call last):\nValueError: bad config\n"
    launcher.relay_output(io.StringIO(failure), ["app/example.py"], launcher.time.monotonic())
    assert capsys.readouterr().out == failure


def test_initial_startup_keeps_all_output(capsys):
    startup = "INFO: Application startup complete.\n2026-10-15 [info     ] scheduler.started\n"
    launcher.relay_output(io.StringIO(startup), [], launcher.time.monotonic())
    assert capsys.readouterr().out == startup
