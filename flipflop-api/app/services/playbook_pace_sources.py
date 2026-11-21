"""Per-component exact supplier choices for the customer's delivery pace."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from app.services.commerce_pricing import FulfilmentMode


_FALLBACK_ARRIVAL_ESTIMATES = {
    'vendor_default', 'general_supplier_default', 'prime_default',
    'saved_vendor_default', 'configured_vendor_default', 'owner_fallback',
}


def _arrival_precedence(source):
    """Prefer a captured ETA over a synthesized default for the same listing.

    Ties use observation recency. Keep one complete source record rather than
    merging price and delivery facts from separate captures.
    """
    days=source.get('delivery_working_days')
    explicit=(isinstance(days,int) and not isinstance(days,bool) and days>=0
        and source.get('delivery_estimate_source') not in _FALLBACK_ARRIVAL_ESTIMATES)
    try:
        observed=datetime.fromisoformat(str(source.get('observed_at') or '').replace('Z','+00:00'))
        if observed.tzinfo is None:
            observed=observed.replace(tzinfo=timezone.utc)
        observed_at=observed.astimezone(timezone.utc).timestamp()
    except (TypeError,ValueError,OverflowError):
        observed_at=float('-inf')
    return explicit,observed_at


def _record_choice(choices,source):
    url=source.get('url')
    if not url:
        return
    previous=choices.get(url)
    if previous is None or _arrival_precedence(source)>_arrival_precedence(previous):
        choices[url]=source


async def component_pace_sources(parts,policy,db):
    from app.services.playbook_service import (_current_suggested_supplier_source,
        _supplier_arrival_estimate,_supplier_fact_is_approvable)
    from app.services.playbook_commercial_quote import supplier_meets_delivery_commitment
    from app.services.commercial_quote_evidence import supplier_identity
    from app.services.commerce_pricing import SupplierOffer,Condition,FulfilmentMode,supplier_allowed
    from app.models.commerce_evidence import SupplierOfferEvidence
    from app.models.commerce_evidence import PriceQuoteSnapshot
    from app.services.commercial_quote_evidence import supplier_capture_product_key
    from app.services.commercial_quote_evidence import latest_listing_observations
    evidence_keys={}
    for part in parts.values():
        key=(f"case:{part['case_catalogue_id']}" if part.get('role')=='case' and part.get('case_catalogue_id')
             else f"variant:{part['variant_id']}")
        evidence_keys.setdefault(key,[]).append(part)
    rows=[]
    if evidence_keys:
        stored=(await db.execute(select(SupplierOfferEvidence).where(
            SupplierOfferEvidence.part_key.in_(list(evidence_keys))
        ))).scalars().all()
        cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
        rows=[row for row in latest_listing_observations(stored)
              if row.observed_at.replace(tzinfo=row.observed_at.tzinfo or timezone.utc)>=cutoff
              and row.stock_confirmed and row.condition=='new'
              and Decimal(row.supplier_confidence)>=Decimal('0.8')]
    capture_keys={supplier_capture_product_key(row.part_key,row.evidence_ref,row.observed_at.isoformat())
        for row in rows}
    capture_metadata={}
    if capture_keys:
        snapshots=(await db.execute(select(PriceQuoteSnapshot).where(
            PriceQuoteSnapshot.product_key.in_(list(capture_keys)),
            PriceQuoteSnapshot.status=='supplier_offer_capture'))).scalars().all()
        capture_metadata={snapshot.product_key:snapshot.evidence_json for snapshot in snapshots
            if isinstance(snapshot.evidence_json,dict)
            and (snapshot.decision_json or {}).get('capture_verified') is True}
    result={mode:[] for mode in ('fast_track','standard','flexible')}
    for part in parts.values():
        choices={}
        current=part.get('source_observation') or {}
        options=[current]
        for captured in part.get('supplier_offers') or []:
            source=_current_suggested_supplier_source({**part,'suggested_supplier_offer':captured})
            if source:options.append(source)
        for source in options:
            if not _supplier_fact_is_approvable({**part,'source_url':source.get('url')},source):continue
            days,estimate_source=_supplier_arrival_estimate(part,source)
            entry={**source,'delivery_working_days':days,'delivery_estimate_source':estimate_source}
            _record_choice(choices,entry)
        key=(f"case:{part['case_catalogue_id']}" if part.get('role')=='case' and part.get('case_catalogue_id')
             else f"variant:{part['variant_id']}")
        for row in rows:
            if row.part_key!=key:continue
            metadata=capture_metadata.get(supplier_capture_product_key(
                row.part_key,row.evidence_ref,row.observed_at.isoformat()))
            if metadata is None:
                continue
            source={'url':row.evidence_ref,'source':row.supplier,'item_gbp':str(row.item_gbp),
                'delivery_gbp':str(row.delivery_gbp),'postage_verified':True,
                'observed_at':row.observed_at.isoformat(),'observation_id':f"supplier-evidence:{row.id}",
                'fingerprint':f"supplier-evidence:{row.id}",'condition':row.condition,
                'channel':row.channel,'stock_confirmed':row.stock_confirmed,
                'title':metadata.get('title'),'mpn':metadata.get('mpn'),
                'cpk':metadata.get('cpk'),'cpk_data':metadata.get('cpk_data'),
                'listing_type':metadata.get('listing_type') or ('buy_it_now' if row.channel=='retail' else None),
                'listing_ends_at':metadata.get('listing_ends_at'),
                'stock_status':'available' if row.stock_confirmed else 'unavailable',
                'stock_evidence':metadata.get('stock_evidence') or f"Reviewed supplier stock capture #{row.id}",
                'fresh':True,'commercial_capture_verified':True,'active_listing':row.stock_confirmed,
                'postage_verified':metadata.get('postage_verified') is True,
                'postage_assumption':('owner-approved-zero-fallback'
                    if metadata.get('postage_verified') is not True and Decimal(row.delivery_gbp)==0 else None),
                'supplier_confidence':str(row.supplier_confidence),
                'delivery_working_days':row.delivery_working_days,
                'delivery_estimate_source':row.delivery_estimate_source}
            if source['delivery_working_days'] is None:
                days,estimate_source=_supplier_arrival_estimate(part,source)
                source['delivery_working_days']=days
                source['delivery_estimate_source']=estimate_source
            # The reviewed evidence row is the same source the quote engine
            # consumes, so it supersedes a duplicate Gem Radar card for this URL.
            _record_choice(choices,source)
        auction_urls=[url for url,source in choices.items()
            if str(source.get('listing_type') or '').casefold()=='auction']
        if auction_urls:
            # Auction evidence needs a current active listing and a real end
            # time inside the allowed seven-day attempt window. Stored bid
            # snapshots alone do not prove that the lot is still available.
            from app.models.listing import Listing
            now_utc=datetime.now(timezone.utc)
            live_rows=(await db.execute(select(Listing.url,Listing.listing_ends_at).where(
                Listing.url.in_(auction_urls),Listing.status=='active',
                Listing.listing_type=='auction',Listing.listing_ends_at>datetime.utcnow()
            ))).all()
            active_ends={}
            for url,ends_at in live_rows:
                if ends_at is None:
                    continue
                if ends_at.tzinfo is None:
                    ends_at=ends_at.replace(tzinfo=timezone.utc)
                ends_at=ends_at.astimezone(timezone.utc)
                if now_utc<ends_at<=now_utc+timedelta(days=7):
                    active_ends[url]=ends_at.isoformat()
            for url in auction_urls:
                if url not in active_ends:
                    choices.pop(url,None)
                else:
                    choices[url]['listing_ends_at']=active_ends[url]
        for mode,fulfilment in (('fast_track',FulfilmentMode.PRIORITY),('standard',FulfilmentMode.STANDARD),('flexible',FulfilmentMode.FLEXIBLE)):
            eligible=[]
            for source in choices.values():
                vendor=supplier_identity(source.get('source'),source['url'])
                software=part['role'].startswith('os')
                condition=Condition(source.get('condition') or 'new')
                offer=SupplierOffer(vendor,source.get('channel') or ('software' if software else 'retail'),condition,
                    Decimal(source['item_gbp']),Decimal(source.get('delivery_gbp') or 0),Decimal(0),Decimal(0),
                    source['observed_at'],bool(source.get('stock_confirmed',True)),True,source['delivery_working_days'],
                    Decimal(source.get('supplier_confidence') or '1'))
                if not supplier_allowed(fulfilment,offer):continue
                if policy is None:continue
                if (source['delivery_working_days'] is None
                        or source['delivery_working_days'] < 0):continue
                if mode!='flexible' and not supplier_meets_delivery_commitment(source['delivery_working_days'],policy.modes[mode]):continue
                eligible.append({k:source.get(k) for k in ('url','source','item_gbp','delivery_gbp','postage_verified',
                    'postage_assumption','delivery_working_days','delivery_estimate_source','observed_at','observation_id','fingerprint',
                    'listing_ends_at')})
                eligible[-1]['listing_type']=source.get('listing_type') or ('buy_it_now' if source.get('channel')=='retail' else None)
            eligible.sort(key=lambda s:Decimal(s['item_gbp'])+Decimal(s.get('delivery_gbp') or 0))
            result[mode].append({'role':part['role'],'variant_id':part['variant_id'],'listing_id':part['listing_id'],
                'title':part['title'],'quantity':part.get('quantity') or 1,'available':bool(eligible),
                'delivery_promised':mode!='flexible','sources':eligible,
                'reason':None if eligible else 'No current exact supplier offer meets this pace for this component.'})
    return result
