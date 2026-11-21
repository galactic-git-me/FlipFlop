"""Load the repository-owned operating procedures used by autonomous agents."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

AgentName = Literal["demand", "pricing", "playbook"]
_SKILL_DIR = Path(__file__).resolve().parents[1] / "agent_skills"


@lru_cache(maxsize=3)
def load_agent_skill(agent: AgentName) -> str:
    path = _SKILL_DIR / agent / "SKILL.md"
    return path.read_text(encoding="utf-8")
