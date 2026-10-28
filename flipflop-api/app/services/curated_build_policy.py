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


def _capacity_gb(value):
    match = re.search(r'(?<!\d)(\d+(?:\.\d+)?)\s*(TB|GB)\b', str(value or ''), re.I)
    if not match:
        return None
    amount = float(match.group(1))
    return amount * 1024 if match.group(2).upper() == 'TB' else amount


def _customer_option(category, title, option):
    option = dict(option or {})
    if category not in ('ram', 'storage'):
        return option
    capacity = option.get('capacity_gb') or _capacity_gb(title)
    if capacity and not option.get('capacity_gb'):
        option['capacity_gb'] = capacity
    if category == 'ram':
        generation = re.search(r'\bDDR\s*([345])\b', str(title), re.I)
        if generation and not option.get('memory_type'):
            option['memory_type'] = 'DDR' + generation.group(1)
    else:
        name = str(title).lower()
        interface = 'NVMe' if 'nvme' in name else ('SATA' if 'sata' in name and ('ssd' in name or 'solid state' in name) else None)
        if interface and not option.get('interface'):
            option['interface'] = interface
    return option


def _matches_curated_spec(category, variant, specification):
    title = variant['title']
    if matches_spec(title, specification):
        return True
    if category not in ('ram', 'storage'):
        return False
    wanted = _customer_option(category, specification, {})
    actual = _customer_option(category, title, variant.get('customer_option'))
    keys = ('capacity_gb', 'memory_type') if category == 'ram' else ('capacity_gb', 'interface')
    return all(wanted.get(key) is not None and wanted.get(key) == actual.get(key) for key in keys)


def _capacity_label(capacity):
    if capacity >= 1024:
        return f'{capacity / 1024:g} TB'
    return f'{capacity:g} GB'


def curated_slots(slots, definition=None, selected_variant_ids=None):
    result = deepcopy(slots)
    for slot in result:
        tiers = slot['variants_by_tier']
        ranked = [v for tier in ('mid', 'budget', 'high')
                  for v in sorted(tiers.get(tier, []), key=lambda v: (-(v.get('gem_score') or 0), v['id']))]
        default = ranked[0] if ranked else None
        if definition:
            operating_system=str(definition.get('components',{}).get('os') or '')
            windows=re.search(r'windows\s+11\s+(home|pro)',operating_system,re.I)
            ubuntu=re.search(r'ubuntu\s+(\d{2}\.\d{2})',operating_system,re.I)
            dual_boot=bool(windows and ubuntu)
            if slot['slot_type']=='os':
                if windows:
                    edition=windows.group(1)
                    default=next((v for v in ranked if re.search(
                        rf'\bwindows\s+11\s+{edition}\b',v['title'],re.I)),None)
                elif operating_system:
                    default=next((v for v in ranked if _matches_curated_spec(
                        'os',v,operating_system)),None)
            elif slot['slot_type']=='os_secondary':
                default=(next((v for v in ranked if 'ubuntu' in v['title'].casefold()
                    and ubuntu.group(1) in v['title']),None) if dual_boot else None)
            elif slot['slot_type']=='wireless_adapter':
                # Wireless is a required extra only for cells whose selected
                # motherboard lacks verified Wi-Fi or Bluetooth. Never add it
                # to another cell's baseline by choosing an arbitrary default.
                default=None
            elif slot['slot_type'] in definition.get('components',{}):
                specification = definition['components'][slot['slot_type']]
                default = next((v for v in ranked if _matches_curated_spec(slot['slot_type'], v, specification)), None)
        if selected_variant_ids is not None:
            selected_id = selected_variant_ids.get(slot['slot_type'])
            default = next((variant for variant in ranked if variant['id'] == selected_id), None)
        slot['default_variant_id'] = default['id'] if default else None
        slot['customization'] = {'ram': 'capacity', 'storage': 'ssd_type_capacity'}.get(slot['slot_type'], 'fixed')
        choices = {}
        for variant in ranked if default else []:
            option = _customer_option(slot['slot_type'], variant['title'], variant.get('customer_option'))
            if option:
                variant['customer_option'] = option
            capacity = option.get('capacity_gb')
            if slot['slot_type'] == 'ram' and isinstance(capacity, (int, float)) and capacity > 0:
                # Memory generation remains the curated platform's generation.
                baseline = (default.get('customer_option') or {}).get('memory_type')
                baseline_capacity = _customer_option('ram', default['title'], default.get('customer_option')).get('capacity_gb')
                if not baseline or option.get('memory_type') != baseline:
                    continue
                if baseline_capacity and capacity < baseline_capacity:
                    continue
                key = (capacity,)
                variant['choice_label'] = f'{capacity:g} GB RAM'
            elif slot['slot_type'] == 'storage' and isinstance(capacity, (int, float)) and capacity > 0 and option.get('interface') in ('SATA', 'NVMe'):
                baseline_capacity = _customer_option('storage', default['title'], default.get('customer_option')).get('capacity_gb')
                if baseline_capacity and capacity < baseline_capacity:
                    continue
                key = (option['interface'], capacity)
                variant['choice_label'] = _capacity_label(capacity)
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
