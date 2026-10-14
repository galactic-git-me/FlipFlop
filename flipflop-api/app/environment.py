"""Local overrides beat base files; explicit process settings beat both."""
import os
from pathlib import Path
from dotenv import dotenv_values


def load_application_environment(directory: Path) -> None:
    values = {**dotenv_values(directory / '.env'), **dotenv_values(directory / '.env.local')}
    for name, value in values.items():
        if value is not None:
            os.environ.setdefault(name, value)
