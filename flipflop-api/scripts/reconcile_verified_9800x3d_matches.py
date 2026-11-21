"""Narrow, reviewed DEV repair for known Ryzen 7 9800X3D identities.

Dry-run by default. `--apply` is restricted to loopback Postgres and only
updates four independently verified standalone CPU listings plus removes
seven exact, already-reviewed complete-PC listings from the CPU cohort.
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.gem_radar.identity import is_full_system_listing
from app.gem_radar.opportunity_scoring import identity_gates
from app.gem_radar.product_identifiers import canonical_cpu_model
from app.gem_radar.search_identity import SEARCH_IDENTITY_VERSION

TARGET_CPK = "17f0f6a336174b115a2ff33e6048a844"
CPU_MODEL = "amd_ryzen_9800x3d"
TITLE_ALIAS = json.dumps(["amd", CPU_MODEL], separators=(",", ":"))

STANDALONE = {
    "278426270485": {
        "title": "AMD Ryzen 9800X3D CPU", "cpk": "26a000ca1bb4ca5b",
        "category": "cpu", "minimum_price": 300.0,
    },
    "237031989064": {
        "title": "New Ryzen 7 9800X3D (Tray Edition)", "cpk": "471e71e66040d95f",
        "category": "cpu", "minimum_price": 250.0,
    },
    "880103348379": {
        "title": "Ryzen 7 9800X3D Socket AM5 CPU", "cpk": "471e71e66040d95f",
        "category": "cpu", "minimum_price": 250.0,
    },
    "940094592324": {
        "title": "AMD Ryzen 7 9800X3D CPU 4.7GHz 8 Core AM5 Processor", "cpk": "471e71e66040d95f",
        "category": "cpu", "minimum_price": 250.0,
    },
}

COMPLETE_SYSTEMS = {
    "298719451280": "CyberPowerPC Lumina White AMD Ryzen 7 9800X3D 32GB RAM 2TB SSD RTX 5090  LD22246",
    "188620428800": "Ryzen 7 9800X3D | RX 7900 XTX 24GB | 64GB DDR5 | 4TB SSD",
    "newegg_uk:N82E16883230877": "CyberPowerPC Gamer Supreme Liquid Cool GML70850 - AMD Ryzen 7 9800X3D 4.7GHz CPU, 32GB DDR5, AMD Radeon RX 9060 XT 16GB, 2TB PCIe 4.0 NVMe SSD & Win 11 Home",
    "newegg_uk:N82E16883230807": "CyberPowerPC Gamer Supreme Liquid Cool GML70170 - AMD Ryzen 7 9800X3D 4.7GHz CPU, 32GB DDR5, NVIDIA GeForce RTX 5080 16GB, 2TB PCIe 4.0 NVMe SSD & Win 11 Home",
    "366731089346": "HIGH PERFORMANCE GAMING PC - AMD Ryzen 7 9800x3d - 1TB SSD - MORE SPECS IN DESC",
    "168799005539": "3XS Edge RTX, 12GB RTX 5070, AMD Ryzen 7 9800X3D, 32GB DDR5, 2TB M.2 SSD, SCAN G",
    "257813432332": "Acer NITRO 70 N70X3D-100 - AMD Ryzen 7 9800X3D CPU, RTX 5080 GPU, 32GB, 2TB SSD,",
}


async def _latest_title(db, listing_id: str, cpk_data: dict) -> str:
    title = (await db.execute(text("""
        SELECT title FROM gem_radar_listing_observations
        WHERE listing_id=:id ORDER BY observed_at DESC,id DESC LIMIT 1
    """), {"id": listing_id})).scalar_one_or_none()
    if not title:
        title = (await db.execute(text(
            "SELECT title FROM listings WHERE external_id=:id"
        ), {"id": listing_id})).scalar_one_or_none()
    return str(title or cpk_data.get("identity_source_title") or "")


async def reconcile(apply: bool) -> dict:
    async with engine.begin() as db:
        await db.execute(text("SET TRANSACTION READ WRITE" if apply else "SET TRANSACTION READ ONLY"))
        context = (await db.execute(text(
            "SELECT current_database() AS name,inet_server_addr()::text AS address"
        ))).mappings().one()
        address = (context["address"] or "").split("/", 1)[0]
        if apply and (not address or not ipaddress.ip_address(address).is_loopback):
            raise RuntimeError("--apply is restricted to loopback PostgreSQL instances")

        anchor = (await db.execute(text("""
            SELECT cpk_data FROM gem_radar_listing_cpk WHERE cpk=:cpk
            ORDER BY updated_at DESC LIMIT 1
        """), {"cpk": TARGET_CPK})).mappings().first()
        if not anchor or canonical_cpu_model(
            (anchor["cpk_data"] or {}).get("identity_source_title", ""), "amd"
        ) != CPU_MODEL:
            raise RuntimeError("Target CPK is not the verified Ryzen 7 9800X3D product")

        merges = []
        old_cpks = set()
        for listing_id, expected in STANDALONE.items():
            row = (await db.execute(text("""
                SELECT c.listing_id,c.cpk,c.cpk_data,c.cpk_confidence,
                       p.price AS ledger_price,p.cpk AS ledger_cpk,
                       l.price AS listing_price,l.status AS listing_status
                FROM gem_radar_listing_cpk c
                LEFT JOIN gem_radar_cpk_listing_price p ON p.listing_id=c.listing_id
                LEFT JOIN listings l ON l.external_id=c.listing_id
                WHERE c.listing_id=:id
            """), {"id": listing_id})).mappings().first()
            if not row or row["cpk"] != expected["cpk"]:
                raise RuntimeError(f"Unexpected current CPK for reviewed CPU listing {listing_id}")
            data = row["cpk_data"] or {}
            title = await _latest_title(db, listing_id, data)
            price = row["ledger_price"] or row["listing_price"]
            if (title != expected["title"] or data.get("category") != expected["category"]
                    or canonical_cpu_model(title, "amd") != CPU_MODEL
                    or is_full_system_listing(title)
                    or any(flag != "identity_incomplete" for flag in identity_gates(
                        title, {"category": "cpu", "brand": "amd", "model": CPU_MODEL}
                    ))
                    or not price or float(price) < expected["minimum_price"]):
                raise RuntimeError(f"CPU listing {listing_id} failed the exact standalone preflight")
            if row["ledger_cpk"] != expected["cpk"] or row["ledger_price"] is None:
                raise RuntimeError(f"CPU listing {listing_id} has no matching price ledger row")
            merges.append({"listing_id": listing_id, "title": title, "category": "cpu",
                           "price": float(price), "old_cpk": row["cpk"], "final_cpk": TARGET_CPK,
                           "identity": data})
            old_cpks.add(row["cpk"])

        removals = []
        for listing_id, expected_title in COMPLETE_SYSTEMS.items():
            row = (await db.execute(text("""
                SELECT c.listing_id,c.cpk,c.cpk_data,p.price AS ledger_price
                FROM gem_radar_listing_cpk c
                LEFT JOIN gem_radar_cpk_listing_price p ON p.listing_id=c.listing_id
                WHERE c.listing_id=:id AND c.cpk=:cpk
            """), {"id": listing_id, "cpk": TARGET_CPK})).mappings().first()
            if not row:
                raise RuntimeError(f"Reviewed PC listing {listing_id} is no longer assigned to the target CPK")
            title = await _latest_title(db, listing_id, row["cpk_data"] or {})
            if title != expected_title or not is_full_system_listing(title):
                raise RuntimeError(f"PC listing {listing_id} failed exact title/system preflight")
            removals.append({"listing_id": listing_id, "title": title, "category": "complete_pc",
                             "price": float(row["ledger_price"]) if row["ledger_price"] is not None else None,
                             "old_cpk": row["cpk"], "final_cpk": None})

        # No other currently assigned target record may be an unreviewed PC.
        target_rows = (await db.execute(text("""
            SELECT c.listing_id,c.cpk_data FROM gem_radar_listing_cpk c WHERE c.cpk=:cpk
        """), {"cpk": TARGET_CPK})).mappings().all()
        found_systems = set()
        for row in target_rows:
            title = await _latest_title(db, row["listing_id"], row["cpk_data"] or {})
            if title and is_full_system_listing(title):
                found_systems.add(row["listing_id"])
        if found_systems != set(COMPLETE_SYSTEMS):
            raise RuntimeError(f"Target CPK has unreviewed PC assignments: {sorted(found_systems ^ set(COMPLETE_SYSTEMS))}")

        before = (await db.execute(text("""
            SELECT listing_count,min_price,median_price,max_price
            FROM gem_radar_cpk_market_price WHERE cpk=:cpk
        """), {"cpk": TARGET_CPK})).mappings().first()
        report = {"database": context["name"], "host": address, "apply": apply,
                  "target_cpk": TARGET_CPK, "before_market": dict(before or {}),
                  "merge_standalone_cpus": [{k:v for k,v in x.items() if k != "identity"} for x in merges],
                  "remove_complete_systems": removals}
        if not apply:
            return report

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        ids = sorted({x["listing_id"] for x in [*merges, *removals]})
        for table, suffix in (("gem_radar_listing_cpk", "listing_cpk"),
                              ("gem_radar_scored_listings", "scored"),
                              ("gem_radar_cpk_listing_price", "price_ledger")):
            name = f"ff_verified_9800x3d_{suffix}_{stamp}"
            await db.execute(text(f"CREATE TABLE {name} AS SELECT * FROM {table} WHERE listing_id=ANY(:ids)"),
                             {"ids": ids})
            report.setdefault("backup_tables", []).append(name)
        alias_backup = f"ff_verified_9800x3d_identifier_{stamp}"
        await db.execute(text(f"""
            CREATE TABLE {alias_backup} AS SELECT * FROM canonical_component_identifiers
            WHERE kind='title_product' AND namespace='cpu' AND value=:value
        """), {"value": TITLE_ALIAS})
        report.setdefault("backup_tables", []).append(alias_backup)
        market_backup = f"ff_verified_9800x3d_market_{stamp}"
        await db.execute(text(f"""
            CREATE TABLE {market_backup} AS SELECT * FROM gem_radar_cpk_market_price
            WHERE cpk=ANY(:cpks)
        """), {"cpks": sorted(old_cpks | {TARGET_CPK})})
        report.setdefault("backup_tables", []).append(market_backup)

        for item in merges:
            old = item["identity"]
            data = {
                "cpk": TARGET_CPK, "category": "cpu", "brand": "amd", "model": CPU_MODEL,
                "specs": {}, "confidence": 0.95,
                "extraction_method": "verified_exact_title_model_reconciliation",
                "identity_match_rule": "normalized_cpu_model",
                "identity_source_title": item["title"],
                "identity_validation_version": SEARCH_IDENTITY_VERSION,
                "identity_claims": [{"kind": "title_product", "namespace": "cpu", "value": TITLE_ALIAS}],
                "identity_anchor_cpk": TARGET_CPK, "identity_reconciled_from": item["old_cpk"],
            }
            if old.get("category_provenance"):
                data["category_provenance"] = old["category_provenance"]
            await db.execute(text("""
                UPDATE gem_radar_listing_cpk SET cpk=:cpk,cpk_data=CAST(:data AS jsonb),
                    cpk_confidence=0.95,updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id
            """), {"cpk": TARGET_CPK, "data": json.dumps(data), "id": item["listing_id"]})
            await db.execute(text("""
                UPDATE gem_radar_cpk_listing_price SET cpk=:cpk WHERE listing_id=:id
            """), {"cpk": TARGET_CPK, "id": item["listing_id"]})
            await db.execute(text("""
                UPDATE gem_radar_scored_listings SET cpk=:cpk,category='cpu'
                WHERE listing_id=:id
            """), {"cpk": TARGET_CPK, "id": item["listing_id"]})

        for item in removals:
            await db.execute(text("DELETE FROM gem_radar_listing_cpk WHERE listing_id=:id"),
                             {"id": item["listing_id"]})
            await db.execute(text("DELETE FROM gem_radar_cpk_listing_price WHERE listing_id=:id"),
                             {"id": item["listing_id"]})
            await db.execute(text("""
                UPDATE gem_radar_scored_listings SET cpk=NULL,classification='INELIGIBLE',
                    deal_score=0,evidence_reason='complete_system_not_component',
                    reasoning_summary='Complete PC; excluded from standalone component pricing.'
                WHERE listing_id=:id
            """), {"id": item["listing_id"]})

        evidence = json.dumps({"source": "verified narrow 9800X3D reconciliation",
                               "at": datetime.now(timezone.utc).isoformat()})
        await db.execute(text("""
            INSERT INTO canonical_component_identifiers(kind,namespace,value,cpk,evidence)
            VALUES('title_product','cpu',:value,:cpk,CAST(:evidence AS jsonb))
            ON CONFLICT(kind,namespace,value) DO UPDATE SET cpk=EXCLUDED.cpk,evidence=EXCLUDED.evidence
        """), {"value": TITLE_ALIAS, "cpk": TARGET_CPK, "evidence": evidence})

        from app.gem_radar.cpk_market import recompute_market_price
        report["after_market_by_cpk"] = {}
        for cpk in old_cpks | {TARGET_CPK}:
            await recompute_market_price(db, cpk,
                category="cpu" if cpk == TARGET_CPK else None,
                brand="amd" if cpk == TARGET_CPK else None,
                model=CPU_MODEL if cpk == TARGET_CPK else None)
            market = (await db.execute(text("""
                SELECT listing_count,min_price,median_price,max_price
                FROM gem_radar_cpk_market_price WHERE cpk=:cpk
            """), {"cpk": cpk})).mappings().first()
            report["after_market_by_cpk"][cpk] = dict(market or {})
        after = (await db.execute(text("""
            SELECT listing_count,min_price,median_price,max_price
            FROM gem_radar_cpk_market_price WHERE cpk=:cpk
        """), {"cpk": TARGET_CPK})).mappings().first()
        report["after_market"] = dict(after or {})
        report["backup_stamp"] = stamp
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(reconcile(args.apply)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
