"""Resolve approved case geometry by the exact catalogue case identity.

Catalogue variants can be retained as hidden media owners. That does not
hide an independently published case, nor make their IDs operational Case IDs.
"""
from sqlalchemy import select, text
from app.models.component_3d_asset import Component3DAsset


async def approved_case_assets(db, case_ids):
    if not case_ids:
        return {}
    rows = (await db.execute(text("""
        SELECT DISTINCT ON (c.id) c.id AS case_id, a.id AS asset_id
        FROM case_catalogue c
        JOIN listings l ON l.case_catalogue_id = c.id
        JOIN catalogue_variants v ON v.listing_id = l.id
        JOIN component_3d_assets a ON a.subject_id = v.id
        WHERE c.id = ANY(:case_ids) AND c.status = 'active'
          AND a.subject_type::text = 'VARIANT' AND a.category = 'case'
          AND a.status::text = 'FINAL' AND a.is_active IS TRUE
          AND a.review_decision = 'approved' AND a.glb_ref IS NOT NULL
          AND COALESCE(l.raw_specs::jsonb->>'catalogue_deleted', 'false') <> 'true'
          AND to_jsonb(v)->'asset_media_review'->>'status' IN ('approved', 'auto_included')
          AND jsonb_array_length(a.source_image_refs::jsonb) > 0
          AND a.source_image_refs::jsonb = COALESCE(
              NULLIF(to_jsonb(v)->'asset_media_review'->'model_image_urls', '[]'::jsonb),
              CASE WHEN jsonb_array_length(to_jsonb(v)->'asset_media_review'->'image_urls') <= 4
                   THEN to_jsonb(v)->'asset_media_review'->'image_urls' ELSE '[]'::jsonb END
          )
        ORDER BY c.id, a.version DESC, a.id DESC
    """), {"case_ids": list(set(case_ids))})).mappings().all()
    assets = {asset.id: asset for asset in (await db.execute(select(Component3DAsset).where(
        Component3DAsset.id.in_([row["asset_id"] for row in rows])
    ))).scalars()} if rows else {}
    return {row["case_id"]: assets[row["asset_id"]] for row in rows}
