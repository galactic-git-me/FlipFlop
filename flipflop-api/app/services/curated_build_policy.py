"""A curated core with capacity choices, shared by catalogue and checkout."""
from copy import deepcopy
import json
import re
from pathlib import Path


def definitions():
    return json.loads((Path(__file__).resolve().parents[2] / 'data/curated_build_definitions.json').read_text(encoding='utf-8'))


def matches_spec(title, specification):
    # Exact normalized product descriptions only; never substitute a nearby GPU/CPU.
    normalize = lambda value: re.sub(r'[^a-z0-9]', '', str(value).lower())
    return bool(specification) and normalize(specification) == normalize(title)


def curated_slots(slots, definition=None):
    result = deepcopy(slots)
    for slot in result:
        tiers = slot['variants_by_tier']
        ranked = [v for tier in ('mid', 'budget', 'high')
                  for v in sorted(tiers.get(tier, []), key=lambda v: (-(v.get('gem_score') or 0), v['id']))]
        default = ranked[0] if ranked else None
        if definition and slot['slot_type'] in definition['components']:
            specification = definition['components'][slot['slot_type']]
            default = next((v for v in ranked if matches_spec(v['title'], specification)), None)
        slot['default_variant_id'] = default['id'] if default else None
        slot['customization'] = {'ram': 'capacity', 'storage': 'ssd_type_capacity'}.get(slot['slot_type'], 'fixed')
        choices = {}
        for variant in ranked if default else []:
            option = variant.get('customer_option') or {}
            capacity = option.get('capacity_gb')
            if slot['slot_type'] == 'ram' and isinstance(capacity, (int, float)) and capacity > 0:
                # Memory generation remains the curated platform's generation.
                baseline = (default.get('customer_option') or {}).get('memory_type')
                if not baseline or option.get('memory_type') != baseline:
                    continue
                key = (capacity,)
                variant['choice_label'] = f'{capacity:g} GB RAM'
            elif slot['slot_type'] == 'storage' and isinstance(capacity, (int, float)) and capacity > 0 and option.get('interface') in ('SATA', 'NVMe'):
                key = (option['interface'], capacity)
                variant['choice_label'] = f"{option['interface']} SSD · {capacity:g} GB"
            else:
                continue
            choices.setdefault(key, variant)
        if slot['customization'] == 'fixed':
            allowed = [default] if default else []
        else:
            allowed = list(choices.values())
            # Unknown specifications never become arbitrary replacement choices.
            if default and default not in allowed:
                default['choice_label'] = 'Included configuration'
                allowed.insert(0, default)
        slot['variants_by_tier'] = {'budget': [], 'mid': allowed, 'high': []}
    if definition:
        present = {s['slot_type'] for s in result}
        for category in definition['components']:
            if category != 'case' and category not in present:
                # Explicitly incomplete; never price a partial build as complete.
                result.append(dict(slot_id=-len(result)-1, slot_type=category, customization='fixed', default_variant_id=None,
                    variants_by_tier={'budget': [], 'mid': [], 'high': []}, tier_names={}))
    return result


def validate_curated_selection(slots, selections):
    if set(selections) != {slot['slot_id'] for slot in slots}:
        raise ValueError('Select every component in the curated build; components cannot be removed or added.')
    for slot in slots:
        allowed = {v['id'] for values in slot['variants_by_tier'].values() for v in values}
        if selections.get(slot['slot_id']) not in allowed:
            raise ValueError(f"The curated {slot['slot_type']} selection is fixed or is not an approved capacity option.")
