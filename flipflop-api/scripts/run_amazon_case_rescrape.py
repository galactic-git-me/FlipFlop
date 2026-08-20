"""Run the cases swarm: Amazon listings, Overclockers catalogue, then Amazon bestseller ranks."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.pop("CASES_AMAZON_ONLY", None)
os.environ.setdefault("CASES_MAX_TERMS", "8")
os.environ.setdefault("CASES_TERM_CONCURRENCY", "1")

from app.swarms.cases import run_cases_swarm


async def main() -> None:
    stats = await run_cases_swarm("main")
    print("SWARM_STATS", stats)


if __name__ == "__main__":
    asyncio.run(main())
