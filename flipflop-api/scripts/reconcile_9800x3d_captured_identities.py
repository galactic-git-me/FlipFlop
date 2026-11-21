"""Repair exact Ryzen 7 9800X3D capture identities in the local Gem Radar DB.

Dry-run by default. With --apply, exact standalone CPU offers are moved to a
caller-selected verified anchor CPK; full systems and CPU-tagged bundles are
removed from component pricing while their source observations are retained.
The write is limited to a loopback PostgreSQL database and snapshots every
affected row before updating it.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.gem_radar.identity import is_full_system_listing, resolve_identity
from app.gem_radar.opportunity_scoring import identity_gates
from app.gem_radar.product_identifiers import canonical_cpu_model, title_part_numbers
from app.gem_radar.search_identity import SEARCH_IDENTITY_VERSION
from app.services.benchmark_normaliser import normalise_cpu


async def reconcile(target_cpk: str, apply: bool) -> dict:
    normalized_model = "amd_ryzen_7_9800x3d"
    async with engine.begin() as db:
        await db.execute(text("SET TRANSACTION READ ONLY" if not apply else "SET TRANSACTION READ WRITE"))
        context = (await db.execute(text(
            "SELECT current_database() AS name, inet_server_addr()::text AS address"
        ))).mappings().one()
        address = (context["address"] or "").split("/", 1)[0]
        if apply and (not address or not ipaddress.ip_address(address).is_loopback):
            raise RuntimeError("--apply is restricted to loopback PostgreSQL instances")

        target_row = (await db.execute(text("""
            SELECT cpk_data FROM gem_radar_listing_cpk
            WHERE cpk=:cpk AND cpk_data->>'category'='cpu'
            ORDER BY updated_at DESC LIMIT 1
        """), {"cpk": target_cpk})).mappings().first()
        if target_row is None:
            raise RuntimeError(f"Target CPK {target_cpk} is not an existing CPU identity")
        target_data = target_row["cpk_data"] or {}
        target_title = str(target_data.get("identity_source_title") or "")
        if normalise_cpu(target_title) != normalized_model:
            raise RuntimeError("Target CPK does not identify the exact Ryzen 7 9800X3D")
        model = canonical_cpu_model(target_title, "amd")
        if model != "amd_ryzen_9800x3d":
            raise RuntimeError("Target CPK does not have a canonical 9800X3D model key")

        rows = (await db.execute(text("""
            SELECT DISTINCT ON (o.listing_id)
                   o.listing_id,o.title,o.delivered_price,o.observed_at,
                   c.cpk,c.cpk_data,c.cpk_confidence
            FROM gem_radar_listing_observations o
            LEFT JOIN gem_radar_listing_cpk c USING (listing_id)
            WHERE o.title ILIKE '%9800X3D%'
            ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
        """))).mappings().all()

        observed_ids = {row["listing_id"] for row in rows}
        unobserved_listings = (await db.execute(text("""
            SELECT l.external_id AS listing_id,l.title,
                   p.price AS delivered_price,p.updated_at AS observed_at,
                   c.cpk,c.cpk_data,c.cpk_confidence
            FROM listings l
            JOIN gem_radar_listing_cpk c ON c.listing_id=l.external_id
            LEFT JOIN gem_radar_cpk_listing_price p ON p.listing_id=l.external_id
            WHERE l.title ILIKE '%9800X3D%' AND l.status='active'
              AND NOT EXISTS (SELECT 1 FROM gem_radar_listing_observations o
                              WHERE o.listing_id=l.external_id)
        """))).mappings().all()
        rows = [*rows, *(row for row in unobserved_listings if row["listing_id"] not in observed_ids)]

        exact_cpu = []
        full_systems = []
        cpu_bundles = []
        skipped = Counter()
        for row in rows:
            title = row["title"] or ""
            if is_full_system_listing(title):
                full_systems.append(row)
                continue
            flags = identity_gates(title, {"category": "cpu", "brand": "amd", "model": model})
            if "whole_system_misclassified_as_component" in flags:
                full_systems.append(row)
                continue
            if re.search(r"\b(?:bundle|combo)\b", title, re.I):
                if ((row["cpk_data"] or {}).get("category") == "cpu"):
                    cpu_bundles.append(row)
                else:
                    skipped["non_cpu_bundle"] += 1
                continue
            resolved = resolve_identity(title, row["delivered_price"])
            if canonical_cpu_model(title, "amd") != model:
                skipped["different_model"] += 1
                continue
            if resolved.category not in {None, "cpu"}:
                skipped["different_category"] += 1
                continue
            stored_category = (row["cpk_data"] or {}).get("category")
            if resolved.category is None and stored_category not in {None, "cpu"}:
                skipped["stored_identity_not_cpu"] += 1
                continue
            if resolved.category is None and not re.search(r"\b(?:cpu|processor)\b", title, re.I):
                skipped["category_not_resolved"] += 1
                continue
            hard_flags = [flag for flag in flags if flag != "identity_incomplete"]
            if hard_flags:
                skipped[hard_flags[0]] += 1
                continue
            if not re.search(r"\b(?:cpu|processor|ryzen)\b", title, re.I):
                skipped["no_cpu_title_signal"] += 1
                continue
            exact_cpu.append({**dict(row), "resolved_category": resolved.category or stored_category or "cpu",
                              "identity_flags": flags})

        old_cpk_counts = Counter(row["cpk"] or "missing" for row in exact_cpu)
        old_cpk_set = {row["cpk"] for row in exact_cpu if row["cpk"] and row["cpk"] != target_cpk}
        r5_rows = []
        if old_cpk_set:
            old_rows = (await db.execute(text("""
                SELECT DISTINCT ON (o.listing_id)
                       o.listing_id,o.title,o.delivered_price,o.observed_at,c.cpk
                FROM gem_radar_listing_observations o
                JOIN gem_radar_listing_cpk c USING (listing_id)
                WHERE c.cpk=ANY(:cpks)
                ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
            """), {"cpks": list(old_cpk_set)})).mappings().all()
            r5_rows = [row for row in old_rows
                       if normalise_cpu(row["title"] or "") == "amd_ryzen_5_3600"
                       and not is_full_system_listing(row["title"] or "")]
        cleanup_ids = {row["listing_id"] for row in [*full_systems, *cpu_bundles] if row["cpk"]}
        exact_ids = {row["listing_id"] for row in exact_cpu}
        affected_ids = sorted(cleanup_ids | exact_ids | {row["listing_id"] for row in r5_rows})
        summary = {
            "database": context["name"], "host": address,
            "apply": apply, "target_cpk": target_cpk,
            "matching_titles": len(rows), "exact_cpu_listings": len(exact_cpu),
            "full_systems_to_unprice": sum(bool(row["cpk"]) for row in full_systems),
            "cpu_bundles_to_unprice": sum(bool(row["cpk"]) for row in cpu_bundles),
            "ryzen_5_3600_rows_to_repair": len(r5_rows),
            "old_cpk_counts": dict(old_cpk_counts), "skipped": dict(skipped),
            "planned_changes": [
                {"listing_id": row["listing_id"], "title": row["title"],
                 "category": row.get("resolved_category", "cpu"),
                 "old_cpk": row["cpk"], "final_cpk": target_cpk,
                 "identity_flags": row.get("identity_flags", [])}
                for row in exact_cpu
            ] + [
                {"listing_id": row["listing_id"], "title": row["title"],
                 "category": (row.get("cpk_data") or {}).get("category"),
                 "old_cpk": row["cpk"], "final_cpk": None,
                 "action": "remove_non_component_price"}
                for row in [*full_systems, *cpu_bundles] if row["cpk"]
            ] + [
                {"listing_id": row["listing_id"], "title": row["title"],
                 "category": "cpu", "old_cpk": row["cpk"],
                 "final_cpk": row["cpk"], "action": "repair_ryzen_5_3600_metadata"}
                for row in r5_rows
            ],
        }
        if old_cpk_set:
            source_members = (await db.execute(text("""
                SELECT DISTINCT ON (o.listing_id)
                       o.listing_id,o.title,o.delivered_price,c.cpk,c.cpk_data
                FROM gem_radar_listing_observations o
                JOIN gem_radar_listing_cpk c USING (listing_id)
                WHERE c.cpk=ANY(:cpks)
                ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
            """), {"cpks": sorted(old_cpk_set)})).mappings().all()
            summary["source_cpk_members"] = [
                {"listing_id": row["listing_id"], "title": row["title"],
                 "category": (row["cpk_data"] or {}).get("category"),
                 "model": (row["cpk_data"] or {}).get("model"),
                 "cpk": row["cpk"], "delivered_price": row["delivered_price"],
                 "is_full_system": is_full_system_listing(row["title"] or ""),
                 "normalised_cpu": normalise_cpu(row["title"] or "")}
                for row in source_members
            ]
        target_members = (await db.execute(text("""
            SELECT DISTINCT ON (o.listing_id)
                   o.listing_id,o.title,o.delivered_price,c.cpk,c.cpk_data
            FROM gem_radar_listing_observations o
            JOIN gem_radar_listing_cpk c USING (listing_id)
            WHERE c.cpk=:cpk
            ORDER BY o.listing_id,o.observed_at DESC,o.id DESC
        """), {"cpk": target_cpk})).mappings().all()
        summary["target_cpk_members"] = [
            {"listing_id": row["listing_id"], "title": row["title"],
             "category": (row["cpk_data"] or {}).get("category"),
             "model": (row["cpk_data"] or {}).get("model"),
             "cpk": row["cpk"], "delivered_price": row["delivered_price"],
             "is_full_system": is_full_system_listing(row["title"] or ""),
             "normalised_cpu": normalise_cpu(row["title"] or "")}
            for row in target_members
        ]
        if not apply:
            return summary

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        for table in ("gem_radar_listing_cpk", "gem_radar_scored_listings", "gem_radar_cpk_listing_price"):
            backup = f"ff_9800x3d_{table.removeprefix('gem_radar_')}_{stamp}"
            await db.execute(text(f"CREATE TABLE {backup} AS SELECT * FROM {table} WHERE listing_id=ANY(:ids)"),
                             {"ids": affected_ids})
            summary.setdefault("backups", []).append(backup)
        identifier_values = [json.dumps(["amd", model], separators=(",", ":"))]
        if r5_rows:
            identifier_values.append(json.dumps(["amd", "amd_ryzen_3600"], separators=(",", ":")))
        await db.execute(text(f"""
            CREATE TABLE ff_9800x3d_identifiers_{stamp} AS
            SELECT * FROM canonical_component_identifiers
            WHERE namespace='cpu' AND kind='title_product' AND value=ANY(:values)
        """), {"values": identifier_values})
        if r5_rows:
            await db.execute(text(f"""
                CREATE TABLE ff_9800x3d_canonical_products_{stamp} AS
                SELECT * FROM canonical_component_products WHERE cpk=ANY(:cpks)
            """), {"cpks": sorted({row["cpk"] for row in r5_rows})})

        title_claims = {
            "9800": json.dumps(["amd", model], separators=(",", ":")),
            "3600": json.dumps(["amd", "amd_ryzen_3600"], separators=(",", ":")),
        }
        for row in exact_cpu:
            title = row["title"] or ""
            old_data = row["cpk_data"] or {}
            data = {
                "cpk": target_cpk,
                "category": "cpu",
                "brand": "amd",
                "model": model,
                "specs": {},
                "confidence": 0.95,
                "extraction_method": "exact_title_model_reconciliation",
                "identity_match_rule": "normalized_cpu_model",
                "identity_source_title": title,
                "identity_title_sha256": hashlib.sha256(
                    re.sub(r"\s+", " ", title.casefold()).strip().encode()
                ).hexdigest(),
                "identity_validation_version": SEARCH_IDENTITY_VERSION,
                "identity_claims": [
                    {"kind": "mpn", "namespace": "amd", "value": code}
                    for code in title_part_numbers(title)
                    if code.startswith("100-1000")
                ] + [{"kind": "title_product", "namespace": "cpu", "value": title_claims["9800"]}],
                "identity_anchor_cpk": target_cpk,
                "identity_reconciled_from": row["cpk"],
            }
            if old_data.get("category_provenance"):
                data["category_provenance"] = old_data["category_provenance"]
            await db.execute(text("""
                INSERT INTO gem_radar_listing_cpk(listing_id,cpk,cpk_data,cpk_confidence,updated_at)
                VALUES(:id,:cpk,CAST(:data AS jsonb),0.95,CURRENT_TIMESTAMP)
                ON CONFLICT(listing_id) DO UPDATE SET cpk=EXCLUDED.cpk,
                  cpk_data=EXCLUDED.cpk_data,cpk_confidence=EXCLUDED.cpk_confidence,
                  updated_at=CURRENT_TIMESTAMP
            """), {"id": row["listing_id"], "cpk": target_cpk, "data": json.dumps(data)})
            await db.execute(text("""
                UPDATE gem_radar_scored_listings SET cpk=:cpk,category='cpu'
                WHERE listing_id=:id
            """), {"id": row["listing_id"], "cpk": target_cpk})

        # The corrupt 650W group also contains two unambiguous Ryzen 5 3600
        # offers. Keep its CPK as the R5 anchor and repair its metadata instead
        # of carrying the bad shared model into the 9800X3D cohort.
        for row in r5_rows:
            title = row["title"] or ""
            data = {
                "cpk": row["cpk"], "category": "cpu", "brand": "amd",
                "model": "amd_ryzen_3600", "specs": {}, "confidence": 0.95,
                "extraction_method": "exact_title_model_reconciliation",
                "identity_match_rule": "normalized_cpu_model",
                "identity_source_title": title,
                "identity_title_sha256": hashlib.sha256(
                    re.sub(r"\s+", " ", title.casefold()).strip().encode()
                ).hexdigest(),
                "identity_validation_version": SEARCH_IDENTITY_VERSION,
                "identity_claims": [{"kind": "title_product", "namespace": "cpu", "value": title_claims["3600"]}],
            }
            await db.execute(text("""
                UPDATE gem_radar_listing_cpk SET cpk_data=CAST(:data AS jsonb),
                  cpk_confidence=0.95,updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id
            """), {"id": row["listing_id"], "data": json.dumps(data)})
            await db.execute(text("""
                UPDATE gem_radar_scored_listings SET category='cpu' WHERE listing_id=:id
            """), {"id": row["listing_id"]})

        # Remove the clearly wrong full-system and standalone-CPU-bundle CPK
        # assignments, preserving their source observations for audit.
        for row in [*full_systems, *cpu_bundles]:
            if not row["cpk"]:
                continue
            await db.execute(text("DELETE FROM gem_radar_listing_cpk WHERE listing_id=:id"), {"id": row["listing_id"]})
            await db.execute(text("DELETE FROM gem_radar_cpk_listing_price WHERE listing_id=:id"), {"id": row["listing_id"]})
            await db.execute(text("""
                UPDATE gem_radar_scored_listings SET cpk=NULL,classification='INELIGIBLE',deal_score=0,
                  evidence_reason='complete_system_not_component',
                  reasoning_summary='Complete computer or component bundle; excluded from standalone component pricing.'
                WHERE listing_id=:id
            """), {"id": row["listing_id"]})

        # Preserve existing price timestamps; seed missing rows with the actual
        # latest observation time so historical listings are not made fresh.
        for row in exact_cpu:
            price = (await db.execute(text(
                "SELECT price FROM gem_radar_cpk_listing_price WHERE listing_id=:id"
            ), {"id": row["listing_id"]})).scalar_one_or_none()
            if price is None and row["delivered_price"] and row["delivered_price"] > 0:
                await db.execute(text("""
                    INSERT INTO gem_radar_cpk_listing_price(listing_id,cpk,price,updated_at)
                    VALUES(:id,:cpk,:price,:observed_at)
                    ON CONFLICT(listing_id) DO UPDATE SET cpk=EXCLUDED.cpk,
                      price=EXCLUDED.price,updated_at=EXCLUDED.updated_at
                """), {"id": row["listing_id"], "cpk": target_cpk,
                       "price": row["delivered_price"], "observed_at": row["observed_at"]})
            else:
                await db.execute(text(
                    "UPDATE gem_radar_cpk_listing_price SET cpk=:cpk WHERE listing_id=:id"
                ), {"id": row["listing_id"], "cpk": target_cpk})

        alias_evidence = json.dumps({"source": "local exact-title CPK reconciliation", "at": datetime.now(timezone.utc).isoformat()})
        aliases_to_insert = [(title_claims["9800"], target_cpk)]
        if r5_rows:
            aliases_to_insert.append((title_claims["3600"], r5_rows[0]["cpk"]))
        for claim_value, cpk in aliases_to_insert:
            await db.execute(text("""
                INSERT INTO canonical_component_identifiers(kind,namespace,value,cpk,evidence)
                VALUES('title_product','cpu',:value,:cpk,CAST(:evidence AS jsonb))
                ON CONFLICT(kind,namespace,value) DO UPDATE SET cpk=EXCLUDED.cpk,evidence=EXCLUDED.evidence
            """), {"value": claim_value, "cpk": cpk, "evidence": alias_evidence})

        # Correct the old bad product metadata where it still backs the R5
        # listings; the exact Ryzen 7 title alias now resolves to the anchor.
        for old_cpk in old_cpk_set:
            if any(row["cpk"] == old_cpk for row in r5_rows):
                r5_title = next(row["title"] for row in r5_rows if row["cpk"] == old_cpk)
                r5_identity = {
                    "cpk": old_cpk, "category": "cpu", "brand": "amd",
                    "model": "amd_ryzen_5_3600", "specs": {}, "confidence": 0.95,
                    "identity_source_title": r5_title,
                    "identity_claims": [{"kind": "title_product", "namespace": "cpu", "value": title_claims["3600"]}],
                }
                await db.execute(text("""
                    UPDATE canonical_component_products SET identity=CAST(:identity AS jsonb)
                    WHERE cpk=:cpk
                """), {"cpk": old_cpk, "identity": json.dumps(r5_identity)})

        from app.gem_radar.cpk_market import recompute_market_price
        for cpk in old_cpk_set | {target_cpk}:
            await recompute_market_price(
                db, cpk,
                category="cpu" if cpk == target_cpk else None,
                brand="amd" if cpk == target_cpk else None,
                model=model if cpk == target_cpk else None,
            )
        summary["applied_exact_cpu"] = len(exact_cpu)
        summary["applied_r5_metadata_repairs"] = len(r5_rows)
        summary["applied_full_system_unpricing"] = sum(bool(row["cpk"]) for row in full_systems)
        summary["applied_bundle_unpricing"] = sum(bool(row["cpk"]) for row in cpu_bundles)
        summary["backup_stamp"] = stamp
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-cpk", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(reconcile(args.target_cpk, args.apply)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
