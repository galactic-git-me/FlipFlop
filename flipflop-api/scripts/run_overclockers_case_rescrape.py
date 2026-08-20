"""Run Overclockers catalogue scrape and upsert into cases + parts."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal
from app.swarms.cases import _scrape_overclockers, _upsert_case, _upsert_case_new


async def main() -> None:
    cases = await _scrape_overclockers("catalogue", "Catalogue")
    print(f"SCRAPED {len(cases)}")
    async with AsyncSessionLocal() as db:
        for case in cases:
            await _upsert_case(db, case)
            await _upsert_case_new(db, case)
        await db.commit()
    amazon = sum(1 for c in cases if c.source_site == "Overclockers")
    print(f"UPSERTED {len(cases)} overclockers={amazon}")


if __name__ == "__main__":
    asyncio.run(main())
