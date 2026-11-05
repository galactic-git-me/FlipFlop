import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import sqlite


@pytest.mark.asyncio
async def test_purchase_plan_requires_same_cpk_and_includes_sold_postage():
    from app.api.manual_builds import get_build_purchase_plan

    component = {"slot": "gpu", "name": "MSI NVIDIA GeForce RTX 4070 Ti 12GB Gaming GPU", "gem_radar_listing_id": 1}
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(is_archived=False, creation_method="gem_spotlight", components=[component])
    end = datetime.utcnow() + timedelta(hours=1)
    wrong = SimpleNamespace(title="MSI NVIDIA GeForce GTX 1050 Ti 4GB GPU", url="https://www.ebay.co.uk/itm/1", price=50, listing_ends_at=end)
    correct = SimpleNamespace(title=component["name"], url="https://www.ebay.co.uk/itm/2", price=300, listing_ends_at=end)
    calls = 0
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE gem_radar_sold_observations (cpk TEXT, price REAL, postage REAL, observed_at TEXT)")
    connection.executemany("INSERT INTO gem_radar_sold_observations VALUES (?, ?, ?, ?)", [
        ("gpu4070", 100, 20, "2026-11-01"), ("gpu4070", 100, None, "2026-11-02"),
    ])

    async def execute(statement):
        nonlocal calls
        calls += 1
        if calls == 1:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(id=1, cpk="gpu4070")]))
        if calls == 2:
            # Execute the actual sold-cohort SQL so postage arithmetic is tested.
            sql = str(statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
            rows = connection.execute(sql).fetchall()
            return SimpleNamespace(all=lambda: rows)
        return SimpleNamespace(all=lambda: [(wrong, "gpu1050"), (correct, "gpu4070")])

    db.execute.side_effect = execute
    try:
        plan = await get_build_purchase_plan(1, db)
    finally:
        connection.close()
    result = plan["components"][0]
    assert [row["url"] for row in result["auctions"]] == [correct.url]
    assert result["sold_median"] == 110
    assert result["sold_sample_size"] == 2
