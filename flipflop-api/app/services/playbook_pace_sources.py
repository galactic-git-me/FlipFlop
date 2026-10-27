"""Per-component exact supplier choices for the customer's delivery pace."""
from decimal import Decimal


def component_pace_sources(parts,policy):
    from app.services.playbook_service import (_current_suggested_supplier_source,
        _supplier_arrival_estimate,_supplier_fact_is_approvable)
    from app.services.playbook_commercial_quote import supplier_meets_delivery_commitment
    from app.services.commercial_quote_evidence import supplier_identity
    from app.services.commerce_pricing import SupplierOffer,Condition,FulfilmentMode,supplier_allowed
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
            choices[(source.get('url'),source.get('observation_id'))]=entry
        for mode,fulfilment in (('fast_track',FulfilmentMode.PRIORITY),('standard',FulfilmentMode.STANDARD),('flexible',FulfilmentMode.FLEXIBLE)):
            eligible=[]
            for source in choices.values():
                vendor=supplier_identity(source.get('source'),source['url'])
                software=part['role'].startswith('os')
                offer=SupplierOffer(vendor,'software' if software else 'retail',Condition.NEW,
                    Decimal(source['item_gbp']),Decimal(source.get('delivery_gbp') or 0),Decimal(0),Decimal(0),
                    source['observed_at'],True,True,source['delivery_working_days'])
                if not supplier_allowed(fulfilment,offer):continue
                if policy is None:continue
                if mode=='fast_track' and (source['delivery_working_days'] is None or source['delivery_working_days']>1):continue
                if mode=='standard' and (source['delivery_working_days'] is None or source['delivery_working_days']>3):continue
                if mode!='flexible' and not supplier_meets_delivery_commitment(source['delivery_working_days'],policy.modes[mode]):continue
                eligible.append({k:source.get(k) for k in ('url','source','item_gbp','delivery_gbp','postage_verified',
                    'postage_assumption','delivery_working_days','delivery_estimate_source','observed_at','observation_id','fingerprint')})
            eligible.sort(key=lambda s:Decimal(s['item_gbp'])+Decimal(s.get('delivery_gbp') or 0))
            result[mode].append({'role':part['role'],'variant_id':part['variant_id'],'listing_id':part['listing_id'],
                'title':part['title'],'quantity':part.get('quantity') or 1,'available':bool(eligible),
                'delivery_promised':mode!='flexible','sources':eligible,
                'reason':None if eligible else 'No current exact supplier offer meets this pace for this component.'})
    return result
