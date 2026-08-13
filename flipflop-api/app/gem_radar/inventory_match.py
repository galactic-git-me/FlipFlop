"""Inventory awareness (PRD §19). Purely informational — the caller
(scoring.py) never sees this data, by construction: nothing in this module
is imported by scoring.py, so inventory counts cannot leak into the
objective deal score even by accident.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.gem_radar.schemas import InventoryAwareness


def _apply_category_filter(query, category: str | None):
    return query.where(InventoryItem.component_type == category) if category else query


async def fetch_inventory_awareness(
    db: AsyncSession, category: str | None, model: str | None, brand: str | None
) -> InventoryAwareness:
    # Each count is its own independent query against InventoryItem directly
    # (never select_from a subquery while also referencing the original
    # table's columns — that produces an implicit cross join and silently
    # doubles every aggregate; a unit test caught exactly this).
    category_items_query = _apply_category_filter(select(InventoryItem), category)
    category_items_result = await db.execute(category_items_query)
    category_items = category_items_result.scalars().all()
    category_count = sum(item.quantity for item in category_items)
    item_ids = [item.id for item in category_items]

    exact_matches_owned = 0
    same_model_owned = 0
    if model:
        matched_items = [item for item in category_items if model.lower() in item.component_name.lower()]
        same_model_owned = sum(item.quantity for item in matched_items)
        if brand:
            exact_matches_owned = sum(
                item.quantity for item in matched_items if brand.lower() in item.component_name.lower()
            )
        else:
            exact_matches_owned = same_model_owned

    reserved_count = 0
    if item_ids:
        reserved_result = await db.execute(
            select(func.coalesce(func.sum(InventoryAllocation.quantity_allocated), 0)).where(
                InventoryAllocation.inventory_item_id.in_(item_ids)
            )
        )
        reserved_count = reserved_result.scalar_one()

    available_count = max(0, category_count - reserved_count)

    return InventoryAwareness(
        exact_matches_owned=exact_matches_owned,
        same_model_owned=same_model_owned,
        category_count=category_count,
        reserved_count=reserved_count,
        available_count=available_count,
    )
