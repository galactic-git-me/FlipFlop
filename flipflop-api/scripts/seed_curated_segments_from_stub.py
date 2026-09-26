"""Create the 24 draft customer/budget segments without publishing or pricing them.

Run from flipflop-api: .venv/Scripts/python scripts/seed_curated_segments_from_stub.py
Existing segments and approved component assignments are left intact.
"""
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings


def main() -> None:
    source = Path(__file__).resolve().parents[2] / "tmp" / "curated-playbooks-v1-stub.json"
    playbooks = json.loads(source.read_text(encoding="utf-8"))["playbooks"]
    pairs = {(item["customer_type"], item["budget_tier"]) for item in playbooks}
    if len(playbooks) != 24 or len(pairs) != 24:
        raise ValueError("Expected 24 distinct customer type and budget segments")
    engine = create_engine(get_settings().sync_database_url)
    with engine.begin() as connection:
        for item in playbooks:
            connection.execute(text("""
                INSERT INTO curated_build_segments
                    (customer_type, budget_level, components, availability_status,
                     is_live, regeneration_status, updated_at)
                VALUES (:customer_type, :budget_level, '{}'::json, 'out_of_stock',
                        false, 'idle', now())
                ON CONFLICT (customer_type, budget_level) DO NOTHING
            """), {
                "customer_type": item["customer_type"],
                "budget_level": item["budget_tier"],
            })
    print(f"Ensured {len(pairs)} draft segments")


if __name__ == "__main__":
    main()
