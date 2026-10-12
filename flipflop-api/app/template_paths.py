"""Resolve reviewed repository templates or their API-image copies."""
from pathlib import Path


_REPOSITORY_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates" / "dispatch"
_PACKAGED_TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "dispatch"


def dispatch_template_path(*parts: str) -> Path:
    """Prefer canonical repo assets; use bundled copies in API-only images."""
    canonical = _REPOSITORY_TEMPLATE_ROOT.joinpath(*parts)
    if canonical.exists():
        return canonical
    packaged = _PACKAGED_TEMPLATE_ROOT.joinpath(*parts)
    return packaged if packaged.exists() else canonical
