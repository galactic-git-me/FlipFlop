"""Link genuine Amazon UK Top 100 cases to the customer case catalogue.

ASIN is the primary identity. When the ASIN has no catalogue/listing match,
the existing case product key (CPK) is used to locate the same exact case
family among captured listings and CaseCatalogue rows. Unmatched cases receive
their own catalogue entry; no other product is attached based on a fuzzy name.

Run from flipflop-api:
    python -m scripts.reconcile_amazon_top100_case_catalogue
    python -m scripts.reconcile_amazon_top100_case_catalogue --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from app.database import AsyncSessionLocal, engine
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.case import Case
from app.models.catalogue import CaseCatalogue
from app.models.listing import Listing, ListingStatus
from app.services.case_product_key import case_product_key

# Independent UK price checks for captures that were missing or malformed.
# Values are exact product-model matches; keep the source URLs in the audit.
VERIFIED_PRICE_OVERRIDES = {
    "B0FK5GHQ2N": (94.99, "https://www.cclonline.com/o11dmiv2fx-lian-li-o11-dynamic-mini-v2-flow-mid-tower-gaming-case-black/"),
    "B0FKBN6BQ8": (45.70, "https://pricespy.co.uk/product.php?p=15479987"),
}


def asin_from_case(case: Case) -> str | None:
    match = re.search(r"/dp/([A-Z0-9]{10})(?:/|\?|$)", case.source_url or "", re.I)
    return match.group(1).upper() if match else None


def normalise(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def plausible_price(value) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if 5 <= price <= 2500 else None


def form_factor(case: Case) -> str:
    values = [str(value).lower() for value in (case.form_factors or [])]
    joined = " ".join(values + [case.name.lower()])
    for token in ("matx", "micro atx", "micro-atx"):
        if token in joined:
            return "matx"
    for token in ("mini-itx", "mini itx", "itx"):
        if token in joined:
            return "itx"
    return "atx"


def exact_asin_listing(listings: list[Listing], asin: str) -> Listing | None:
    matches = [row for row in listings if
        row.external_id in {asin, f"amazon-bestseller:{asin}"}
        or f"/dp/{asin}" in (row.url or "").upper()]
    if not matches:
        return None
    return sorted(matches, key=lambda row: (
        row.case_catalogue_id is not None,
        row.source_confidence == "bestseller_capture",
        row.last_seen_at or datetime.min,
        row.id,
    ), reverse=True)[0]


def cpk_catalogue_match(catalogues: list[CaseCatalogue], key: str,
                       case_name: str, asin: str) -> CaseCatalogue | None:
    matches = [row for row in catalogues
               if case_product_key(row.name, row.brand, None) == key]
    if not matches:
        return None
    # Prefer the exact captured product title. If titles differ but CPK is
    # unique, CPK is the intended cross-source fallback. Ambiguous CPK matches
    # are left unresolved rather than attaching the listing to the wrong SKU.
    title_match = [row for row in matches if normalise(row.name) == normalise(case_name)]
    if len(title_match) == 1:
        return title_match[0]
    if len(matches) == 1:
        return matches[0]
    asin_hint = [row for row in matches if asin.casefold() in (row.notes or "").casefold()]
    return asin_hint[0] if len(asin_hint) == 1 else None


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        cases = (await db.execute(select(Case).where(
            Case.source_site == "Amazon",
            Case.bestseller_rank.is_not(None),
            Case.bestseller_rank <= 100,
        ).order_by(Case.bestseller_rank, Case.id))).scalars().all()
        observations = (await db.execute(select(AmazonBestsellerObservation).where(
            AmazonBestsellerObservation.category == "case",
            AmazonBestsellerObservation.rank <= 100,
        ).order_by(AmazonBestsellerObservation.captured_at.desc(),
                   AmazonBestsellerObservation.id.desc()))).scalars().all()
        latest_obs: dict[str, AmazonBestsellerObservation] = {}
        for row in observations:
            latest_obs.setdefault(row.asin.upper(), row)
        listings = (await db.execute(select(Listing))).scalars().all()
        catalogues = (await db.execute(select(CaseCatalogue))).scalars().all()
        source_listing_count = len(listings)
        source_catalogue_count = len(catalogues)
        actions: list[dict] = []
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for case in cases:
            asin = asin_from_case(case)
            if not asin:
                actions.append({"rank": case.bestseller_rank, "action": "skip", "reason": "Case row has no Amazon ASIN URL"})
                continue
            observation = latest_obs.get(asin)
            if not observation or not observation.image_url:
                actions.append({"rank": case.bestseller_rank, "asin": asin, "action": "skip", "reason": "No captured Top 100 observation or image"})
                continue

            key = case_product_key(observation.title or case.name)
            listing = exact_asin_listing(listings, asin)
            catalogue = next((row for row in catalogues if listing and row.id == listing.case_catalogue_id), None)
            match_method = "asin" if catalogue else None
            if catalogue is None:
                catalogue = cpk_catalogue_match(catalogues, key, observation.title or case.name, asin)
                if catalogue:
                    match_method = "cpk"

            case_price = plausible_price(case.price_new) or plausible_price(case.price) or plausible_price(case.rrp)
            observation_price = plausible_price(observation.price)
            listing_price = plausible_price(listing.price) if listing else None
            override = VERIFIED_PRICE_OVERRIDES.get(asin)
            selected_price = observation_price or listing_price or case_price or (override[0] if override else None)
            price_evidence = "amazon_top100_observation" if observation_price else (
                "existing_exact_asin_listing" if listing_price else
                "existing_case_capture" if case_price else "verified_uk_price_comparison")
            if not selected_price:
                # Do not invent a price. The public customer chooser and build
                # price cannot safely use a CaseCatalogue row without one.
                actions.append({"rank": case.bestseller_rank, "asin": asin, "cpk": key,
                                "action": "skip", "reason": "No plausible sourced GBP price"})
                continue

            if catalogue is None:
                brand = (case.brand or (observation.title or case.name).split()[0] or "Unknown")[:100]
                catalogue = CaseCatalogue(
                    name=(observation.title or case.name)[:200], brand=brand,
                    form_factor=form_factor(case), images=[observation.image_url],
                    rrp_gbp=selected_price, status="active",
                    is_transparent_panel=True,
                    notes=json.dumps({"amazon_top100_case": {
                        "asin": asin, "rank": case.bestseller_rank, "cpk": key,
                        "price_gbp": selected_price, "price_evidence": price_evidence,
                        "captured_at": observation.captured_at.isoformat(),
                        "price_source_url": override[1] if override and not (observation_price or listing_price or case_price) else None,
                    }}, ensure_ascii=False),
                )
                db.add(catalogue)
                await db.flush()
                catalogues.append(catalogue)
                match_method = "created"
                catalogue_created = True
            else:
                catalogue_created = False

            # Make the source image available in the customer chooser while
            # preserving any existing gallery images.
            images = list(catalogue.images or [])
            if observation.image_url not in images:
                catalogue.images = [observation.image_url, *images]
            if not catalogue.form_factor or catalogue.form_factor == "unknown":
                catalogue.form_factor = form_factor(case)
            catalogue.status = "active"
            if not plausible_price(catalogue.rrp_gbp):
                catalogue.rrp_gbp = selected_price

            if listing is None:
                listing = Listing(
                    external_id=f"amazon-bestseller:{asin}", source_id=0,
                    source_name="amazon", source_confidence="bestseller_capture",
                    title=observation.title or case.name,
                    price=observation_price, url=f"https://www.amazon.co.uk/dp/{asin}",
                    image_urls=[observation.image_url], condition="new",
                    case_brand=case.brand, case_model=case.model or case.name,
                    case_form_factor=form_factor(case).upper(),
                    raw_specs={"amazon_top100_case": {
                        "asin": asin, "rank": case.bestseller_rank, "cpk": key,
                        "observed_at": observation.captured_at.isoformat(),
                        "price_gbp": observation_price,
                        "source_url": observation.url,
                        "catalogue_reference_price_gbp": selected_price,
                        "price_evidence": price_evidence,
                        "price_source_url": override[1] if override and not (observation_price or listing_price or case_price) else None,
                    }},
                    status=ListingStatus.active, first_seen_at=now, last_seen_at=now,
                )
                db.add(listing)
                await db.flush()
                listings.append(listing)
                listing_created = True
            else:
                listing_created = False
                if not listing.case_catalogue_id:
                    listing.case_catalogue_id = catalogue.id
                if not listing.image_urls:
                    listing.image_urls = [observation.image_url]
                listing.raw_specs = {
                    **(listing.raw_specs or {}),
                    "amazon_top100_case": {
                        "asin": asin, "rank": case.bestseller_rank, "cpk": key,
                        "observed_at": observation.captured_at.isoformat(),
                        "image_url": observation.image_url,
                    },
                }
            listing.case_catalogue_id = catalogue.id

            # Keep the operational Case row, Amazon Listing, and public
            # CaseCatalogue image aligned with the user-approved main photo.
            case.image_url = observation.image_url
            evidence = dict(case.sourcing_3d_evidence or {})
            evidence["amazon_top100_identity"] = {
                "asin": asin, "cpk": key, "catalogue_id": catalogue.id,
                "listing_id": listing.id, "matched_by": match_method,
                "photo_url": observation.image_url,
                "approved_photo_and_3d_reference": True,
            }
            case.sourcing_3d_evidence = evidence
            actions.append({"rank": case.bestseller_rank, "asin": asin, "cpk": key,
                            "listing_id": listing.id, "catalogue_id": catalogue.id,
                            "matched_by": match_method, "price_gbp": selected_price,
                            "price_evidence": price_evidence,
                            "listing_created": listing_created,
                            "catalogue_created": catalogue_created})

        if apply:
            await db.commit()
        else:
            await db.rollback()

        linked = [row for row in actions if row.get("catalogue_id")]
        print(json.dumps({
            "mode": "apply" if apply else "dry_run",
            "eligible_case_rows": len(cases),
            "matched_or_created": len(linked),
            "skipped": len(actions) - len(linked),
            "new_listings": sum(1 for row in linked if row.get("listing_created")),
            "new_case_catalogue_entries": sum(1 for row in linked if row.get("catalogue_created")),
            "actions": actions,
            "source_counts": {"listings": source_listing_count, "case_catalogue": source_catalogue_count},
        }, ensure_ascii=False, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the reconciliation")
    asyncio.run(run(parser.parse_args().apply))
