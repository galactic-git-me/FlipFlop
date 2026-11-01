"""Local overrides beat base files; explicit process settings beat both."""
import os
from pathlib import Path
from dotenv import dotenv_values


def load_application_environment(directory: Path) -> None:
    # Tests must never inherit developer credentials or live feature flags
    # from repository dotenv files. Their configuration is injected by the
    # isolated runner instead.
    if os.getenv("APP_ENV", "").strip().casefold() in {"test", "testing"}:
        return
    values = {**dotenv_values(directory / '.env'), **dotenv_values(directory / '.env.local')}
    for name, value in values.items():
        if value is not None:
            os.environ.setdefault(name, value)
