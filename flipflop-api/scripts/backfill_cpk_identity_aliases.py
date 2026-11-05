"""Register safe aliases for existing CPKs without changing listing assignments.

Default mode is read-only and emits a review report. ``--apply`` only inserts
unambiguous aliases in the verified DEV database; conflicting aliases are
reported and left untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment

API_ROOT = Path(__file__).resolve().parents[1]
load_application_environment(API_ROOT)

_SOURCE_HOSTS = {
    "ebay":"ebay.co.uk", "amazon":"amazon.co.uk", "overclockers":"overclockers.co.uk",
    "scan":"scan.co.uk", "awd_it":"awd-it.co.uk", "computer_orbit":"computerorbit.com",
    "bargain_hardware":"bargainhardware.co.uk", "ebuyer":"ebuyer.com",
    "newegg_uk":"newegg.com", "aliexpress":"aliexpress.com", "cex":"uk.webuy.com",
}

from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.gem_radar.product_identifiers import extract_asin
from app.gem_radar.product_identity_registry import identifier_claims, resolve_identifiers
from app.services.amazon_bestsellers import bestseller_item_matches_category


async def run(*, apply: bool, report_path: Path) -> dict:
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        if not apply:
            await db.execute(text("SET TRANSACTION READ ONLY"))
        target = dict((await db.execute(text(
            "SELECT current_database() AS database,current_schema() AS schema"
        ))).mappings().one())
        if apply:
            if settings.app_env != "dev" or target != {"database": "pcflipper", "schema": "public"}:
                raise RuntimeError(f"Refusing alias backfill outside verified DEV: {settings.app_env}, {target}")

        present = await db.scalar(text(
            "SELECT to_regclass('canonical_component_identifiers') IS NOT NULL"
        ))
        if not present:
            raise RuntimeError("Identity registry migration must be applied before alias backfill")

        rows = (await db.execute(text("""
            WITH latest AS (
                SELECT DISTINCT ON(listing_id) listing_id,title,category,source,
                       gtin,mpn,model_number,epid,vendor_product_id
                FROM gem_radar_listing_observations
                ORDER BY listing_id,observed_at DESC,id DESC
            )
            SELECT l.*,c.cpk,c.cpk_data
            FROM latest l JOIN gem_radar_listing_cpk c USING(listing_id)
            WHERE c.cpk IS NOT NULL
        """))).mappings().all()

        alias_cpks: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        alias_listing_ids: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        cpk_identity: dict[str, dict] = {}
        for row in rows:
            cpk = str(row["cpk"])
            cpk_identity.setdefault(cpk, row["cpk_data"] or {"cpk": cpk})
            for claim in identifier_claims(
                title=row["title"], category=row["category"], gtin=row["gtin"],
                mpn=row["mpn"], model_number=row["model_number"], epid=row["epid"],
                vendor_product_id=row["vendor_product_id"],
                source_url=(f"https://{_SOURCE_HOSTS[row['source']]}/"
                            if row["vendor_product_id"] and row["source"] in _SOURCE_HOSTS else None),
            ):
                key = (claim["kind"], claim["namespace"], claim["value"])
                alias_cpks[key].add(cpk)
                alias_listing_ids[key].add(str(row["listing_id"]))
            if row["source"] == "amazon" and (asin := extract_asin(row["listing_id"])):
                key = ("asin", "amazon.co.uk", asin)
                alias_cpks[key].add(cpk)
                alias_listing_ids[key].add(str(row["listing_id"]))

        all_claims = [
            {"kind": key[0], "namespace": key[1], "value": key[2]}
            for key in alias_cpks
        ]
        existing = {}
        if all_claims:
            found = (await db.execute(text("""
                SELECT i.kind,i.namespace,i.value,i.cpk
                FROM canonical_component_identifiers i
                JOIN jsonb_to_recordset(CAST(:claims AS jsonb)) c(kind text,namespace text,value text)
                  USING(kind,namespace,value)
            """), {"claims": json.dumps(all_claims)})).mappings().all()
            existing = {(r["kind"],r["namespace"],r["value"]):str(r["cpk"]) for r in found}

        additions, conflicts = [], []
        for key, cpks in alias_cpks.items():
            record = {"kind":key[0],"namespace":key[1],"value":key[2],
                      "cpks":sorted(cpks),"listing_ids":sorted(alias_listing_ids[key])[:20]}
            registered = existing.get(key)
            if len(cpks) != 1 or (registered and registered not in cpks):
                record["registered_cpk"] = registered
                conflicts.append(record)
            elif not registered:
                record["cpk"] = next(iter(cpks))
                additions.append(record)

        report = {
            "created_at":datetime.now(timezone.utc).isoformat(),
            "database_target":target,
            "mode":"apply" if apply else "dry_run",
            "existing_cpk_listings":len(rows),
            "existing_cpks":len(cpk_identity),
            "distinct_aliases_seen":len(alias_cpks),
            "unambiguous_aliases_to_add":len(additions),
            "conflicting_aliases_skipped":len(conflicts),
            "aliases_to_add":additions,
            "conflicts":conflicts,
        }
        bestseller_rows = []
        bestseller_asins = bestseller_observation_rows_assigned = bestseller_unresolved = 0
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        if apply:
            for cpk, identity in cpk_identity.items():
                await db.execute(text("""
                    INSERT INTO canonical_component_products(cpk,identity)
                    VALUES(:cpk,CAST(:identity AS jsonb)) ON CONFLICT(cpk) DO NOTHING
                """), {"cpk":cpk,"identity":json.dumps(identity)})
            by_key = {(x["kind"],x["namespace"],x["value"]):x["cpk"] for x in additions}
            evidence = json.dumps({"source":"dev_alias_backfill","resolver_version":2,
                                   "observed_at":datetime.now(timezone.utc).isoformat()})
            for key, cpk in by_key.items():
                await db.execute(text("""
                    INSERT INTO canonical_component_identifiers(kind,namespace,value,cpk,evidence)
                    VALUES(:kind,:namespace,:value,:cpk,CAST(:evidence AS jsonb))
                    ON CONFLICT(kind,namespace,value) DO NOTHING
                """), {"kind":key[0],"namespace":key[1],"value":key[2],
                       "cpk":cpk,"evidence":evidence})
            await db.commit()
            report["inserted_aliases"] = len(by_key)
            report["listing_assignments_changed"] = 0

            # Amazon ASINs are exact product IDs. Seed CPKs for valid bestseller
            # products that have no marketplace listing match yet; this lets a
            # later retailer sighting resolve to the ASIN anchor or its title alias.
            bestseller_rows = (await db.execute(text("""
                SELECT DISTINCT ON(asin) asin,title,category,url,cpk
                FROM amazon_bestseller_observations
                ORDER BY asin,captured_at DESC,id DESC
            """))).mappings().all()
            bestseller_asins_processed = bestseller_rows_matched = 0
            for item in bestseller_rows:
                if item["cpk"]:
                    continue
                if not bestseller_item_matches_category(item["title"], item["category"]):
                    continue
                identity = await resolve_identifiers(
                    db,title=item["title"],category=item["category"],source_url=item["url"]
                )
                if identity and identity.get("status") == "conflict":
                    identity = await resolve_identifiers(
                        db,title=item["title"],category=item["category"],source_url=item["url"],
                        include_title_alias=False,include_manufacturer_part=False,
                        use_search_identity=False,
                    )
                bestseller_asins_processed += 1
                if identity and identity.get("status") in {"matched","new"}:
                    result = await db.execute(text("""
                        UPDATE amazon_bestseller_observations SET cpk=:cpk
                        WHERE asin=:asin AND cpk IS NULL
                    """),{"cpk":identity["cpk"],"asin":item["asin"]})
                    bestseller_rows_matched += result.rowcount or 0
                else:
                    bestseller_unresolved += 1
                if bestseller_asins_processed % 100 == 0:
                    await db.commit()
            await db.commit()
            bestseller_asins = bestseller_asins_processed
            bestseller_observation_rows_assigned = bestseller_rows_matched
            report["eligible_bestseller_asins_processed"] = bestseller_asins
            report["bestseller_observation_rows_newly_assigned_this_run"] = bestseller_observation_rows_assigned
            report["bestseller_asins_left_unresolved"] = bestseller_unresolved
            coverage=(await db.execute(text("""
                WITH latest AS (
                    SELECT DISTINCT ON(asin) asin,cpk
                    FROM amazon_bestseller_observations
                    ORDER BY asin,captured_at DESC,id DESC
                )
                SELECT count(*) AS unique_asins,
                       count(*) FILTER(WHERE cpk IS NOT NULL) AS latest_asins_with_cpk
                FROM latest
            """))).mappings().one()
            report["latest_bestseller_unique_asins"] = coverage["unique_asins"]
            report["latest_bestseller_asins_with_cpk"] = coverage["latest_asins_with_cpk"]
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k not in {"aliases_to_add","conflicts"}}, indent=2))
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Insert unambiguous aliases in DEV")
    parser.add_argument("--report", type=Path, required=True, help="JSON review report output path")
    args = parser.parse_args()
    async def execute() -> None:
        await run(apply=args.apply, report_path=args.report)
        await engine.dispose()
    asyncio.run(execute())


if __name__ == "__main__":
    main()
