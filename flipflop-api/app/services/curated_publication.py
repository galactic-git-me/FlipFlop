"""One deterministic gate for Playbook publication and baseline pricing."""
from math import isfinite

from app.services.curated_build_policy import curated_slots, matches_spec


class PublicationError(ValueError):
    pass


def positive_price(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return False
    return isfinite(amount) and amount > 0


def publication_snapshot(definition, segment, catalogue_slots, cases, *, require_live=True):
    if segment is None or (require_live and not segment.is_live):
        raise PublicationError('This Playbook cell is not published')
    if not positive_price(segment.selling_price):
        raise PublicationError('Set an approved selling price before publishing this Playbook cell')
    chosen_ids = segment.components or {}
    slots = curated_slots(catalogue_slots, definition, chosen_ids)
    required = {'cpu', 'motherboard', 'ram', 'storage', 'cooling', 'psu'}
    required.update(set(definition.get('components', {})) - {'case'})
    present = {slot['slot_type'] for slot in slots}
    if required - present:
        raise PublicationError('The Playbook is missing required component slots')
    components = {}
    selections = {}
    for slot in slots:
        if slot['slot_type'] == 'case':
            continue
        default = next((part for values in slot['variants_by_tier'].values() for part in values
                        if part['id'] == slot.get('default_variant_id')), None)
        if not default or default.get('availability') != 'active' or not positive_price(default.get('display_price')):
            raise PublicationError(f"Select an available, priced {slot['slot_type']} in this Playbook cell")
        selections[int(slot['slot_id'])] = int(default['id'])
        components[slot['slot_type']] = default['title']
    case_variant = next((part for slot in catalogue_slots if slot['slot_type'] == 'case'
                         for values in slot['variants_by_tier'].values() for part in values
                         if part['id'] == chosen_ids.get('case') and part.get('availability') == 'active'), None)
    case = next((item for item in cases if case_variant and matches_spec(item['name'], case_variant['title'])
                 and positive_price(item.get('rrp_gbp'))), None)
    if not case:
        raise PublicationError('Select an available case with a matching priced case-catalogue identity')
    components['case'] = case['name']
    baseline = sum(next(part['display_price'] for values in slot['variants_by_tier'].values() for part in values
                        if part['id'] == slot['default_variant_id']) for slot in slots if slot['slot_type'] != 'case') + case['rrp_gbp']
    for slot in slots:
        slot['approved_build_price'] = float(segment.selling_price)
        slot['baseline_parts_total'] = float(baseline)
    return {'slots': slots, 'components': components, 'default_slot_selections': selections,
            'default_case_id': case['id'], 'price_gbp': float(segment.selling_price)}


def curated_total(approved_price, baseline_parts_total, current_parts_total, overhead_rate):
    if not all(positive_price(value) for value in (approved_price, baseline_parts_total, current_parts_total)):
        raise PublicationError('The Playbook baseline or selected parts price is unavailable')
    total = round(float(approved_price) + (float(current_parts_total) - float(baseline_parts_total)) * (1 + overhead_rate), 2)
    if not positive_price(total):
        raise PublicationError('The selected configuration does not have a valid selling price')
    return total
