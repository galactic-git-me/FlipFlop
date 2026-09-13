"""Build a conservative, reviewable queue for unmapped sold observations.

Usage (from ``flipflop-api``)::

    python scripts/propose_identity_reconciliation.py --limit 5000

The command only writes proposal rows. It never assigns ``sold.cpk`` and it
keeps ambiguous candidates together so a reviewer can resolve them safely.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


def normalise(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def tokens(value: str | None) -> set[str]:
    # Keep meaningful product tokens and discard common listing noise.
    stop = {"NEW", "USED", "BOXED", "OEM", "GAMING", "GRAPHICS", "CARD", "GPU", "CPU", "PC"}
    return {t for t in re.findall(r"[A-Z0-9]{3,}", (value or "").upper()) if t not in stop}


def build_proposal(sold: dict, cpks: list[dict]) -> dict:
    identifiers = {normalise(sold.get(k)) for k in ("gtin", "mpn", "model", "match_key") if normalise(sold.get(k))}
    title_tokens = tokens(sold.get("title")) | tokens(sold.get("model")) | tokens(sold.get("match_key"))
    exact: dict[str, set[str]] = defaultdict(set)
    scored: list[tuple[float, str, dict]] = []
    for product in cpks:
        data = product.get("cpk_data") or {}
        product_ids = {normalise(data.get(k)) for k in ("gtin", "mpn", "model") if normalise(data.get(k))}
        product_ids.update({normalise(f"{data.get('brand') or ''}{data.get('model') or ''}")})
        shared_ids = identifiers & product_ids
        product_tokens = tokens(" ".join(str(data.get(k) or "") for k in ("brand", "model", "mpn", "gtin")))
        overlap = len(title_tokens & product_tokens)
        score = overlap / max(1, len(product_tokens))
        if shared_ids:
            for identifier in shared_ids:
                exact[identifier].add(product["cpk"])
            scored.append((1.0, product["cpk"], {"shared_identifiers": sorted(shared_ids)}))
        elif overlap >= 1:
            scored.append((min(0.89, 0.55 + 0.1 * overlap), product["cpk"], {"title_token_overlap": overlap}))

    if exact:
        candidates = sorted({cp for values in exact.values() for cp in values})
        if len(candidates) == 1:
            return {"suggested_cpk": candidates[0], "candidate_cpks": candidates, "method": "exact_identifier", "confidence": 0.99,
                    "status": "pending", "evidence": {"identifiers": sorted(identifiers)}}
        return {"suggested_cpk": None, "candidate_cpks": candidates, "method": "conflicting_identifier", "confidence": 0.0,
                "status": "ambiguous", "evidence": {"identifiers": sorted(identifiers)}}

    scored.sort(reverse=True)
    if not scored:
        return {"suggested_cpk": None, "candidate_cpks": [], "method": "no_candidate", "confidence": 0.0,
                "status": "unresolved", "evidence": {"title": sold.get("title")}}
    best_score = scored[0][0]
    tied = [item for item in scored if item[0] == best_score]
    candidates = sorted({item[1] for item in tied})
    if len(candidates) != 1 or best_score < 0.75:
        return {"suggested_cpk": None, "candidate_cpks": candidates, "method": "title_candidate", "confidence": round(best_score, 3),
                "status": "ambiguous" if candidates else "unresolved", "evidence": {"best_score": best_score}}
    return {"suggested_cpk": candidates[0], "candidate_cpks": candidates, "method": "title_model_match", "confidence": round(best_score, 3),
            "status": "pending", "evidence": tied[0][2]}


def build_candidate_indexes(cpks: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    by_token: dict[str, list[dict]] = defaultdict(list)
    by_identifier: dict[str, list[dict]] = defaultdict(list)
    for product in cpks:
        data = product.get("cpk_data") or {}
        for token in tokens(" ".join(str(data.get(k) or "") for k in ("brand", "model", "mpn", "gtin"))):
            by_token[token].append(product)
        for key in ("gtin", "mpn", "model"):
            identifier = normalise(data.get(key))
            if identifier:
                by_identifier[identifier].append(product)
        # Sold match_keys commonly contain the concatenated brand+model.
        # Index both forms so clear deterministic products can be recovered
        # without scanning the full CPK catalog for every sold row.
        for identifier in (normalise(data.get("model")), normalise(f"{data.get('brand') or ''}{data.get('model') or ''}")):
            if identifier:
                by_identifier[identifier].append(product)
    return by_token, by_identifier


def candidate_subset(sold: dict, cpks: list[dict], indexes=None) -> list[dict]:
    """Cheap prefilter so a queue run does not compare every sale to every CPK."""
    wanted = tokens(sold.get("title")) | tokens(sold.get("model")) | tokens(sold.get("match_key"))
    identifiers = {normalise(sold.get(k)) for k in ("gtin", "mpn", "model", "match_key") if normalise(sold.get(k))}
    if indexes is None:
        indexes = build_candidate_indexes(cpks)
    by_token, by_identifier = indexes
    result = {id(product): product for token in wanted for product in by_token.get(token, [])}
    for identifier in identifiers:
        result.update({id(product): product for product in by_identifier.get(identifier, [])})
    return list(result.values())


async def run(limit: int, dry_run: bool) -> dict:
    engine = create_async_engine(get_settings().database_url, echo=False)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        sold_rows = (await db.execute(text("""
            SELECT id, title, model, mpn, gtin, condition, match_key
            FROM gem_radar_sold_observations
            WHERE cpk IS NULL
            ORDER BY observed_at DESC NULLS LAST, id DESC
            LIMIT :limit
        """), {"limit": limit})).mappings().all()
        cpk_rows = (await db.execute(text("""
            SELECT DISTINCT ON (cpk) cpk, cpk_data
            FROM gem_radar_listing_cpk
            WHERE cpk IS NOT NULL
            ORDER BY cpk, updated_at DESC NULLS LAST
        """))).mappings().all()
        cpks = [{"cpk": row["cpk"], "cpk_data": row["cpk_data"] or {}} for row in cpk_rows]
        indexes = build_candidate_indexes(cpks)
        counts = defaultdict(int)
        for sold in sold_rows:
            proposal = build_proposal(dict(sold), candidate_subset(dict(sold), cpks, indexes))
            counts[proposal["status"]] += 1
            if not dry_run:
                await db.execute(text("""
                    INSERT INTO gem_radar_identity_proposals
                        (sold_observation_id, suggested_cpk, candidate_cpks, method, confidence, evidence, status, created_at, updated_at)
                    VALUES (:sold_id, :suggested, :candidates, :method, :confidence, :evidence, :status, :now, :now)
                    ON CONFLICT (sold_observation_id) DO UPDATE SET
                        suggested_cpk = EXCLUDED.suggested_cpk,
                        candidate_cpks = EXCLUDED.candidate_cpks,
                        method = EXCLUDED.method,
                        confidence = EXCLUDED.confidence,
                        evidence = EXCLUDED.evidence,
                        status = CASE WHEN gem_radar_identity_proposals.status IN ('approved', 'rejected')
                                      THEN gem_radar_identity_proposals.status ELSE EXCLUDED.status END,
                        updated_at = EXCLUDED.updated_at
                """), {"sold_id": sold["id"], "suggested": proposal["suggested_cpk"],
                       "candidates": json.dumps(proposal["candidate_cpks"]), "method": proposal["method"],
                       "confidence": proposal["confidence"], "evidence": json.dumps(proposal["evidence"]),
                       "status": proposal["status"], "now": datetime.utcnow()})
        if not dry_run:
            await db.commit()
    await engine.dispose()
    return {"scanned": len(sold_rows), "cpks": len(cpks), "counts": dict(counts), "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(max(1, args.limit), args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
