"""Offline draft validation and rendering; never imports application code."""
import hashlib
import json
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    import jsonschema
    spec = json.loads((ROOT / 'specifications.json').read_text(encoding='utf-8'))
    schema = json.loads((ROOT / 'schema.json').read_text(encoding='utf-8'))
    evidence = json.loads((ROOT / 'evidence.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(spec, schema)
    archived = json.loads((ROOT / 'history/0.1.0.json').read_text(encoding='utf-8'))
    jsonschema.validate(archived['specifications'], archived['schema'])
    previous_by_id = {c['id']: c for c in archived['specifications']['cells']}
    events = [json.loads(line) for line in (ROOT / 'changes.jsonl').read_text(encoding='utf-8').splitlines()]
    for event in events:
        if event.get('previous_snapshot'):
            assert event['previous_snapshot_sha256'] == hashlib.sha256((ROOT / event['previous_snapshot']).read_bytes()).hexdigest()
            previous_snapshot=json.loads((ROOT / event['previous_snapshot']).read_text(encoding='utf-8'))
            jsonschema.validate(previous_snapshot['specifications'],previous_snapshot['schema'])
    ids = [c['id'] for c in spec['cells']]
    assert len(ids) == len(set(ids)) == 24
    source = Path(__file__).resolve().parents[4] / 'flipflop-api/data/curated_build_definitions.json'
    active = json.loads(source.read_text(encoding='utf-8'))['builds']
    assert set(ids) == {c['id'] for c in active}
    active_by_id = {c['id']: c for c in active}
    assert spec['dimension_model']['columns'] == 'capability_tier'
    assert spec['dimension_model']['direction_status'] == 'owner_approved'
    refs = {e['id'] for e in evidence['sources']}
    repository = Path(__file__).resolve().parents[4]
    for e in evidence['sources']:
        if 'path' in e:
            assert hashlib.sha256((repository / e['path']).read_bytes()).hexdigest() == e['sha256'], e['id']
    inversions, proposed_overlap = [], []
    for c in spec['cells']:
        level = c['capability_tier']
        assert 'tier' not in c, 'Ambiguous spending-tier field must not define capability'
        assert level['key'] == ('essential', 'enhanced', 'advanced')[level['rank'] - 1]
        assert level['rank'] == int(c['id'][-1])
        assert level['outcome'] == c['tier_benefit']
        assert c['legacy_tier'] == active_by_id[c['id']]['tier']
        previous = previous_by_id[c['id']]
        assert c['legacy_tier'] == previous['tier']
        assert c['commercial']['existing_snapshot'] == previous['commercial']['existing_snapshot']
        assert all(c['commercial']['existing_policy_floor'][key] == value
                   for key, value in previous['commercial']['existing_policy_floor'].items())
        assert c['commercial']['derived_delivered_price_gbp'] is None
        if c['segment'] == 'AI Workstation':
            profile = c['ai_workload_profile']
            assert profile and not profile['frontier_model_claim']
            assert profile['interactive_users'] == profile['simultaneous_requests']
            assert profile['all_thresholds_status'] == 'proposed_not_measured'
            assert profile['resident_model_count'] is None
            if level['rank'] > 1:
                assert 'image_understanding' in profile['modalities']
        else:
            assert c['ai_workload_profile'] is None
        assert set(c['source_refs']) <= refs
        for product in c['products'].values():
            assert set(product['source_refs']) <= refs
        assert c['last_reviewed'] < c['next_review']
        assert len(c['optional_upgrades']) == 2
        assert c['commercial']['landed_bom_gbp'] is None
        assert not c['publishable']
        assert set(c['products']) == set(spec['required_roles'])
        assert all(p['supplier_quote_gbp'] is None for p in c['products'].values())
        constraints = c['constraints']
        socket = constraints['cpu']['socket']
        assert constraints['memory']['generation'] == ('DDR4' if socket == 'AM4' else 'DDR5')
        assert constraints['memory']['module_type'] == ('ECC RDIMM' if socket == 'sTR5' else 'UDIMM')
        assert constraints['storage']['external_usb_substitution_allowed'] is False
        assert constraints['storage']['capacity_tb'] > 0
        if constraints['graphics']['dedicated']:
            assert constraints['graphics']['vram_gb_min'] > 0
        else:
            assert 'integrated' in c['products']['gpu']['recommended'].lower()
        assert constraints['power']['vendor_recommendation_and_transients_gate']
        for requirement in c['acceptance']:
            assert requirement['status'] == 'proposed_not_measured'
        p = c['commercial']['experimental_delivered_price_gbp']
        if p:
            low, high = map(Decimal, p)
            assert low < high
            for margin in ('0.10', '0.12'):
                cap = ((Decimal('0.8985') - Decimal(margin)) * low - Decimal('41.20')) / Decimal('1.10')
                expected = str(cap.quantize(Decimal('.01'), rounding=ROUND_FLOOR))
                assert c['commercial']['landed_parts_ceiling_at_low_price'][margin] == expected
    for segment in dict.fromkeys(c['segment'] for c in spec['cells']):
        cells = sorted((c for c in spec['cells'] if c['segment'] == segment), key=lambda c: c['capability_tier']['rank'])
        assert [c['capability_tier']['rank'] for c in cells] == [1, 2, 3]
        assert len({c['capability_tier']['label'] for c in cells}) == 3
        for a, b in zip(cells, cells[1:]):
            pa, pb = a['commercial']['existing_snapshot']['current'], b['commercial']['existing_snapshot']['current']
            if pa and pb and Decimal(pa) >= Decimal(pb):
                inversions.append([a['id'], b['id'], pa, pb])
            pa, pb = a['commercial']['experimental_delivered_price_gbp'], b['commercial']['experimental_delivered_price_gbp']
            if pa and pb and Decimal(pa[1]) >= Decimal(pb[0]):
                proposed_overlap.append([a['id'], b['id']])
    lines = [f"# Capability-led Playbook matrix — specification {spec['specification_version']}", '',
             'Generated from specifications.json; edit that source and rerun render_validate.py.', '',
             'Owner-approved direction: customer use case × capability tier. Budget filters suitable offers; selling prices are derived from validated costs and market evidence.', '',
             'All acceptance thresholds are proposals, all replacement landed costs unknown, all cells blocked from sale.', '',
             '## Customer benefits', '',
             '| Customer use case | Essential | Enhanced | Advanced |',
             '|---|---|---|---|']
    for segment in dict.fromkeys(c['segment'] for c in spec['cells']):
        cells = sorted((c for c in spec['cells'] if c['segment'] == segment), key=lambda c: c['capability_tier']['rank'])
        labels = [f"**{c['capability_tier']['label']}** ({c['id']}) — {c['capability_tier']['outcome']}; {c['lifecycle']}" for c in cells]
        lines.append(f"| {segment} | " + ' | '.join(labels) + ' |')
    lines += ['', '## Candidate hardware and commercial status', '',
             'Legacy labels are compatibility mappings only. Old price experiments remain in the source/history and do not define capability levels. No current selling price has been established.', '',
             '| Cell | Use case / capability profile | Disposition | CPU / GPU | RAM / internal storage | Derived delivered price |',
             '|---|---|---|---|---|---|']
    for c in spec['cells']:
        lines.append(f"| {c['id']} | {c['segment']} / {c['capability_tier']['label']} | {c['lifecycle']} | {c['products']['cpu']['recommended']} / {c['products']['gpu']['recommended']} | {c['constraints']['memory']['capacity_gb']}GB / {c['constraints']['storage']['capacity_tb']}TB | Not established |")
    for c in spec['cells']:
        lines += ['', f"## {c['id']} — {c['segment']} / {c['capability_tier']['label']}", '',
                  f"Capability level: {c['capability_tier']['key']}; legacy mapping: {c['legacy_tier']} (unchanged operational policy).", '',
                  f"Disposition: **{c['lifecycle']}**. {c['decision_reason']}", '',
                  f"Customer: {c['customer']}", '', f"Work: {'; '.join(c['workloads'])}.", '',
                  f"Excludes: {'; '.join(c['exclusions'])}.", '', f"Tier benefit: {c['tier_benefit']}", '',
                  f"Architecture: {c['constraints']['architecture']}; {c['constraints']['form_factor']}.", '',
                  '| Role | Current proposed product / permitted alternative | Quoted landed price |', '|---|---|---|']
        for role, p in c['products'].items():
            lines.append(f"| {role} | {p['recommended']}; alternatives: {'; '.join(p['alternatives'])} | Unknown |")
        lines += ['', 'Proposed acceptance (not measured):', '']
        lines += [f"- {r['test']}: {r['threshold']}" for r in c['acceptance']]
        if c['ai_workload_profile']:
            lines += ['', 'AI service profile (proposed; no measured promise):', '']
            lines += [f"- {key}: {json.dumps(value)}" for key, value in c['ai_workload_profile'].items()]
        lines += ['', f"Optional upgrades: {'; '.join(c['optional_upgrades'])}.", '',
                  f"Substitution: {'; '.join(c['substitution_rules'])}.", '',
                  f"Commercial: {c['commercial']['feasibility']}. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.", '',
                  f"Archived 0.1.0 price experiment: {json.dumps(c['commercial']['experimental_delivered_price_gbp'])}.", '',
                  f"Existing selected-build snapshot (not this proposal): {json.dumps(c['commercial']['existing_snapshot'])}", '',
                  f"Affordable landed-parts ceilings at the lower trial price: {json.dumps(c['commercial']['landed_parts_ceiling_at_low_price'])}; these are budgets, not supplier costs.", '',
                  f"Evidence IDs: {', '.join(c['source_refs'])}. Confidence: {c['confidence']}.", '',
                  f"Questions: {'; '.join(c['open_questions'])}. Review: {c['last_reviewed']} → {c['next_review']}."]
    (ROOT / 'matrix.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    result = {'schema_validation': 'passed', 'coverage': len(ids), 'source_reference_validation': 'passed',
              'constraint_validation': 'socket/RAM class, internal storage, dedicated VRAM and power gate consistency passed; exact SKU fit and physical tests not verified',
              'commercial_ceiling_arithmetic': 'passed; approximate analysis only, not production penny-rounded quote',
              'existing_snapshot_inversions': inversions, 'proposed_price_envelope_overlap': proposed_overlap,
              'capability_mapping': '24 stable IDs, unique ranked benefit labels per use case and unchanged legacy mappings passed',
              'history_validation': '0.1.0 and 0.2.0 pass their archived schemas; archive hashes and preserved snapshot/floor mappings passed',
              'ai_profile_validation': 'explicit modalities, context, concurrency, quality/latency gates present; no measured or frontier claims',
              'tier_progression': 'capability ranks and proposed benefits checked; workload performance unverified; no price ordering inferred from capability rank',
              'sale_ready_cells': 0, 'spec_sha256': hashlib.sha256((ROOT / 'specifications.json').read_bytes()).hexdigest()}
    (ROOT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
