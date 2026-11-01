"""Capture catalogue listing costs automatically, without inventing availability."""
from sqlalchemy import select
from app.models.commerce_evidence import SupplierOfferEvidence


async def import_current_catalogue_prices(db, parts, admin_id):
    from app.api.commercial_readiness import store_reviewed_sources
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from decimal import Decimal
    from urllib.parse import urlsplit
    from app.services.commercial_quote_evidence import supplier_identity
    from app.services.commercial_source_validation import delivery_estimate_source_label, bounded_evidence_reference
    pending, blocked = [], []
    for part in parts:
        source, key = part.get('source'), part.get('part_key')
        if not source or not key:
            blocked.append(f"{part['role']}: an exact linked supplier capture is needed; buying postage defaults to £0.00")
            continue
        if not source.get('fresh') or not source.get('commercial_capture_verified'):
            blocked.append(f"{part['role']}: refresh the listing to collect a current item price and stock; unknown buying postage defaults to £0.00")
            continue
        evidence_ref=bounded_evidence_reference(str(source.get('url') or ''))
        old = (await db.execute(select(SupplierOfferEvidence).where(
            SupplierOfferEvidence.part_key == key, SupplierOfferEvidence.evidence_ref == evidence_ref,
        ).order_by(SupplierOfferEvidence.id.desc()).limit(1))).scalar_one_or_none()
        marketplace = supplier_identity(source.get('source'), source['url']) in {'ebay', 'vinted'}
        if not old and (marketplace or source.get('condition') != 'new'):
            blocked.append(f"{part['role']}: marketplace fees, risk and condition need a supplier review")
            continue
        # New retail listings have no separate marketplace buyer-fee allowance.
        # Existing explicit procurement allowances always take precedence.
        confirmed = bool(source.get('active_listing') and source.get('stock_status') == 'available')
        if source.get('condition') not in {'new', 'used', 'refurbished'}:
            blocked.append(f"{part['role']}: collector condition needs review")
            continue
        url = urlsplit(str(source.get('url') or ''))
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            blocked.append(f"{part['role']}: exact HTTPS supplier listing URL is missing or invalid")
            continue
        try:
            observed = datetime.fromisoformat(source['observed_at'].replace('Z', '+00:00'))
            item = Decimal(str(source['item_gbp']))
            delivery_value = source.get('delivery_gbp') if source.get('postage_verified') is True else '0.00'
            delivery = Decimal(str(delivery_value))
        except (KeyError, ValueError, TypeError, ArithmeticError):
            blocked.append(f"{part['role']}: captured item price or observation timestamp is invalid; unknown buying postage defaults to £0.00")
            continue
        if (observed.tzinfo is None or observed > datetime.now(timezone.utc)
                or not item.is_finite() or item < 0 or not delivery.is_finite() or delivery < 0
                or item != item.quantize(Decimal('0.01')) or delivery != delivery.quantize(Decimal('0.01'))):
            blocked.append(f"{part['role']}: captured item price or observation timestamp is invalid; unknown buying postage defaults to £0.00")
            continue
        identity = supplier_identity(source.get('source'), source['url'])
        software = source.get('evidence_kind') == 'official_free_software'
        free_official_download = (
            software and identity == 'ubuntu'
            and source.get('identity_source') == 'official_free_software'
            and source.get('source') == 'Ubuntu'
            and source.get('stock_status') == 'available'
            and source.get('delivery_working_days') == 0
            and item == 0 and delivery == 0
        )
        if item == 0 and not free_official_download:
            blocked.append(f"{part['role']}: zero-cost items require verified official Ubuntu download evidence")
            continue
        if identity in {'royalcdkeys','gamers_outlet'} and source.get('licence_source_reviewed') is not True:
            vendor='Gamers Outlet' if identity=='gamers_outlet' else 'RoyalCDKeys'
            blocked.append(f"{part['role']}: exact {vendor} licence terms need review")
            continue
        supplier = 'Ubuntu' if software else identity
        entry = SimpleNamespace(part_key=key, fees_gbp=old.fees_gbp if old else Decimal('0.00'),
            risk_gbp=old.risk_gbp if old else Decimal('0.00'),
            supplier_confidence=old.supplier_confidence if old else Decimal('1.0000'),
            stock_confirmed=confirmed)
        if not entry.stock_confirmed and source.get('lifecycle_updated_at'):
            lifecycle_time = datetime.fromisoformat(source['lifecycle_updated_at'].replace('Z', '+00:00'))
            observed = max(observed, lifecycle_time)
        delivery_source=delivery_estimate_source_label(source.get('delivery_estimate_source'))
        pending.append({'part_key': key, 'supplier': supplier,
            'channel': 'software' if software or identity in {'royalcdkeys','gamers_outlet'} else 'marketplace' if identity in {'ebay', 'vinted'} else 'retail',
            'condition': source['condition'], 'item_gbp': item, 'delivery_gbp': delivery,
            'fees_gbp': entry.fees_gbp, 'risk_gbp': entry.risk_gbp,
            'supplier_confidence': entry.supplier_confidence, 'stock_confirmed': entry.stock_confirmed,
            'observed_at': observed, 'delivery_working_days': source.get('delivery_working_days'),
            'delivery_estimate_source': delivery_source,
            'prime_eligible': source.get('prime_eligible'), 'evidence_ref': evidence_ref,
            'evidence_source': f"catalogue_import:{source['observation_id']}:{source['fingerprint'][:16]}"})
        if not confirmed:
            blocked.append(f"{part['role']}: the current listing does not confirm available stock")
    imported, reused = await store_reviewed_sources(db, pending, admin_id)
    return {'imported': len(imported), 'reused': len(reused), 'blocked': blocked}
