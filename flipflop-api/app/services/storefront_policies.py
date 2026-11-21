"""Persisted customer policy copy shared by admin and the storefront."""
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from pydantic import BaseModel, ConfigDict, Field

POLICIES_PATH = Path(__file__).resolve().parents[2] / "data" / "storefront-policies.json"
DEFAULT_POLICIES_PATH = Path(__file__).resolve().parents[1] / "data" / "storefront-policies.default.json"
POLICY_TYPES = ("delivery", "returns", "warranty", "payments", "cancellations", "faults", "delivery-damage")
BASELINE = json.loads(DEFAULT_POLICIES_PATH.read_text(encoding="utf-8"))

class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=30000)

class PolicySet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policies: dict[str, Policy]

def read_policies() -> dict:
    if not POLICIES_PATH.exists():
        return BASELINE
    return json.loads(POLICIES_PATH.read_text(encoding="utf-8"))

def read_admin_policies() -> dict:
    """Show the documented, unpublished baseline in the editor until saved."""
    if not POLICIES_PATH.exists():
        return BASELINE
    return read_policies()

def save_policies(value: PolicySet) -> dict:
    unknown = set(value.policies) - set(POLICY_TYPES)
    if unknown:
        raise ValueError(f"Unknown policy types: {', '.join(sorted(unknown))}")
    POLICIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=POLICIES_PATH.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value.model_dump(), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(POLICIES_PATH)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return read_policies()
