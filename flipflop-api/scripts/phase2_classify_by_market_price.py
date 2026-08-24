"""CLI wrapper for manual/offline re-runs of Phase 2 classification.

In normal operation, phase 2 runs automatically once the FlipFlopXtension
signals a scan sweep is complete and the submission queue has drained — see
app/workers/queue_processor.py's _phase2_trigger_loop and
app/gem_radar/phase2_runner.run_phase2_classification (the shared logic both
this script and that live trigger call).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.gem_radar.phase2_runner import run_phase2_classification


async def main():
    try:
        async with AsyncSessionLocal() as db:
            # A retrospective policy rescore must be deterministic and local;
            # retain stored review enrichment without making one eBay request
            # per newly promoted GEM. Live sweep-triggered runs still enrich.
            result = await run_phase2_classification(db, enrich_product_reviews=False)
    except Exception as exc:
        print(f"Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=" * 80)
    print("Phase 2 Complete!")
    print("=" * 80)
    print(f"  Total latest listings processed: {result.total_cpk_tagged}")
    total = result.total_cpk_tagged or 1
    print(f"  Classified: {result.classified_count} ({100 * result.classified_count // total}%)")
    print(f"  Unsettled (CPK has < 2 contributing listings): {result.unsettled_count}")
    for label, count in sorted(result.classification_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {label}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
