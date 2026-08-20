import pytest
from sqlalchemy import inspect
from app.models.catalogue import PlaybookSlot, CatalogueVariant, CaseCatalogue
from app.database import Base
from app.workers.queue_processor import _case_form_factor, _case_brand, _is_case_search, _looks_like_pc_case

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


@pytest.mark.parametrize("search_id", ["pc-case-chassis", "overclockers-pc-cases", "lian-li-chassis"])
def test_case_search_ids_are_recognised(search_id):
    assert _is_case_search(search_id)


def test_non_case_search_id_is_ignored():
    assert not _is_case_search("overclockers-gpu")


def test_case_title_filter_rejects_complete_pcs():
    assert _looks_like_pc_case("Havn BF 360 premium mid tower case")
    assert not _looks_like_pc_case("Overclockers complete gaming PC with case")


def test_case_metadata_helpers():
    assert _case_brand("Lian Li O11 Vision Compact PC Case") == "Lian Li"
    assert _case_form_factor("Cooler Master micro ATX case") == "matx"
