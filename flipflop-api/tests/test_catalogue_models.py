import pytest
from sqlalchemy import inspect
from app.models.catalogue import PlaybookSlot, CatalogueVariant, CaseCatalogue
from app.database import Base

def test_playbook_slot_tablename():
    assert PlaybookSlot.__tablename__ == "playbook_slots"

def test_catalogue_variant_tablename():
    assert CatalogueVariant.__tablename__ == "catalogue_variants"

def test_case_catalogue_tablename():
    assert CaseCatalogue.__tablename__ == "case_catalogue"

def test_playbook_slot_required_columns():
    cols = {c.key for c in inspect(PlaybookSlot).mapper.column_attrs}
    assert {"playbook_id", "slot_type", "is_customer_visible", "tier_names",
            "score_band_budget", "score_band_mid", "score_band_high"} <= cols

def test_catalogue_variant_required_columns():
    cols = {c.key for c in inspect(CatalogueVariant).mapper.column_attrs}
    assert {"listing_id", "slot_id", "status", "display_price", "tier",
            "consecutive_misses", "last_seen_at", "auto_published_at"} <= cols

def test_case_catalogue_required_columns():
    cols = {c.key for c in inspect(CaseCatalogue).mapper.column_attrs}
    assert {"name", "brand", "form_factor", "images", "rrp_gbp",
            "is_transparent_panel", "status"} <= cols
