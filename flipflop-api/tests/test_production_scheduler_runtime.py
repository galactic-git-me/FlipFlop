import re
from pathlib import Path


def _service_block(compose: str, service_name: str) -> str:
    marker = f"  {service_name}:\n"
    start = compose.index(marker)
    rest = compose[start + len(marker):]
    next_service = re.search(r"\n  [a-zA-Z0-9_-]+:\n", rest)
    return rest[:next_service.start()] if next_service else rest


def test_production_api_starts_scheduler_without_duplicate_background_worker():
    repo_root = Path(__file__).resolve().parents[2]
    compose = (repo_root / "deploy" / "andromeda-api.compose.yml").read_text(encoding="utf-8")
    api = _service_block(compose, "api")
    gem_radar_endpoint = _service_block(compose, "gemradar-worker")
    main_source = (repo_root / "flipflop-api" / "app" / "main.py").read_text(encoding="utf-8")

    assert re.search(r'^      WEB_ONLY: "false"$', api, re.MULTILINE)
    assert re.search(r'^      WEB_ONLY: "true"$', gem_radar_endpoint, re.MULTILINE)
    assert re.search(
        r'^      EXTERNAL_GEM_RADAR_WORKER_ENABLED: "true"$',
        gem_radar_endpoint,
        re.MULTILINE,
    )
    assert "OLLAMA_BASE_URL: http://ollama-tunnel:11434" in api
    assert "app.gem_radar_standalone:app" in gem_radar_endpoint
    assert re.search(r"if not settings\.web_only:[\s\S]{0,1200}start_scheduler\(\)", main_source)
