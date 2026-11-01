"""Scheduled LLM assessment of the exact parts selected for a Playbook offer."""
import json
import re
import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CompatibilityCheck(BaseModel):
    model_config = ConfigDict(extra='ignore')
    pair: str
    verdict: str
    explanation: str = ''
    evidence: list[str] = Field(default_factory=list)
    confidence: str = 'low'


class CompatibilityPayload(BaseModel):
    model_config = ConfigDict(extra='ignore')
    summary: str = 'Compatibility review completed.'
    checks: list[CompatibilityCheck] = Field(default_factory=list)


_COMPATIBILITY_PROPERTY_KEYS = {
    'cpu': {'cpu socket', 'processor socket', 'socket', 'wattage', 'tdp'},
    'motherboard': {'cpu socket', 'processor socket', 'socket', 'ram memory technology',
        'memory technology', 'memory generation', 'available memory slots', 'memory slots',
        'form factor', 'chipset type', 'total sata ports', 'm.2 slots'},
    'ram': {'memory generation', 'ram memory technology', 'memory technology',
        'memory form factor', 'form factor', 'computer memory size', 'ram size',
        'memory speed', 'number of pins', 'voltage'},
    'gpu': {'graphics card length', 'length', 'vram', 'graphics memory size',
        'graphics card ram', 'wattage', 'tdp', 'power connectors'},
    'storage': {'hard disk interface', 'interface', 'hard disk form factor',
        'form factor', 'hardware connectivity', 'item dimensions l x w x thickness'},
    'storage_secondary': {'hard disk interface', 'interface', 'hard disk form factor',
        'form factor', 'hardware connectivity', 'item dimensions l x w x thickness'},
    'psu': {'form factor', 'output wattage', 'wattage', 'connector type',
        'connector types', 'item dimensions l x w x h'},
    'cooling': {'compatible sockets', 'supported sockets', 'socket', 'product dimensions',
        'item dimensions l x w x h', 'radiator size', 'height'},
    'case': {'form factor', 'supported form factors', 'motherboard support',
        'max gpu length', 'maximum gpu length', 'max cooler height', 'maximum cooler height',
        'max psu length', 'radiator support', 'dimensions'},
}


def _relevant_product_properties(role, values):
    if not isinstance(values, dict):
        return {}
    normalise=lambda value: re.sub(r'[^a-z0-9]+',' ',str(value).casefold()).strip()
    allowed={normalise(key) for key in _COMPATIBILITY_PROPERTY_KEYS.get(role,())}
    selected={}
    for key,value in values.items():
        if normalise(key) in allowed and value is not None:
            selected[str(key)[:60]]=str(value)[:120]
            if len(selected)>=8:
                break
    return selected


def compatibility_review_input(offer):
    parts = []
    for part in offer.get('components') or []:
        role = str(part.get('role') or 'component')
        if role.startswith('os'):
            continue
        source = part.get('source_observation') or {}
        # Playbook proposals store the reviewed source facts used by the
        # deterministic planning gate under planning_engineering. Accept the
        # canonical engineering key as a fallback for older proposal shapes.
        engineering = part.get('planning_engineering') or part.get('engineering') or {}
        manufacturer = part.get('manufacturer_facts') or {}
        reviewed = engineering.get('reviewed') is True
        parts.append({
            'role': role,
            'title': str(part.get('title') or '')[:180],
            # Playbook proposals carry an explicit, reviewed planning snapshot
            # assembled from exact manufacturer references and approved
            # catalogue engineering captures. Do not discard these facts just
            # because they are represented under planning_engineering rather
            # than the catalogue configurator record.
            'reviewed_specs': ({key: value for key, value in engineering.items()
                if key not in {'reviewed', 'reviewed_by', 'reviewed_at', 'source_properties','source_url','engineering_reference',
                    'source_fingerprint','manufacturer_verified_fields','primary_source_resolutions'}}
                if reviewed or engineering.get('reviewed_by') in {
                    'automation:exact-source-core-facts',
                    'automation:exact-manufacturer-reference'} or part.get('planning_engineering') is not None else {}),
            'captured_product_properties': _relevant_product_properties(
                role,source.get('product_properties') or {}),
            'manufacturer_reference_specs':{key:value for key,value in manufacturer.items()
                if not key.endswith('url') and key not in {'observed_at','reviewed'}},
            'manufacturer_reference_url':manufacturer.get('source_url'),
        })

    deterministic = offer.get('compatibility', {}).get('checks', [])
    compact_checks = [{'code': row.get('code'), 'severity': row.get('severity'),
        'message': row.get('message'), 'affected': row.get('affected')}
        for row in deterministic if isinstance(row, dict)]
    pairs=[]
    role_map={part['role']:part for part in parts}
    for pair,roles_and_keys in {
        'cpu_motherboard':(('cpu','socket'),('motherboard','socket')),
        'ram_motherboard':(('ram','memory_generation'),('motherboard','memory_generation')),
        'gpu_motherboard':(('gpu','interface'),('motherboard','gpu_interfaces')),
        'motherboard_case':(('motherboard','form_factor'),('case','supported_form_factors')),
    }.items():
        evidence={}
        for role,key in roles_and_keys:
            part=role_map.get(role)
            if not part:
                continue
            aliases={
                'socket':{'socket','cpu_socket','processor_socket'},
                'memory_generation':{'memory_generation','ram_type','memory_technology','ram_memory_technology'},
                'interface':{'gpu_interface','interface','pcie_interface'},
                'gpu_interfaces':{'gpu_interfaces','expansion_interfaces','pcie_slots'},
                'form_factor':{'form_factor','motherboard_form_factor'},
                'supported_form_factors':{'supported_form_factors','motherboard_support'},
            }[key]
            source_values={}
            for group in ('reviewed_specs','captured_product_properties','manufacturer_reference_specs'):
                source_values.update(part.get(group) or {})
            def norm(value):
                return re.sub(r'[^a-z0-9]+','_',str(value).casefold()).strip('_')
            field=next((name for name in source_values if norm(name) in aliases),None)
            if field:
                evidence[f'{role}.{field}']=source_values[field]
        pairs.append({'pair':pair,'evidence':evidence})
    return {'build': {'cell_id': offer.get('cell_id'), 'name': offer.get('name')},
        'parts': parts, 'required_pair_evidence':pairs,'deterministic_checks': compact_checks}


def compatibility_evidence_fingerprint(offer):
    return hashlib.sha256(json.dumps(compatibility_review_input(offer), sort_keys=True,
        separators=(',', ':'), default=str).encode()).hexdigest()


def _normalised_fact(value):
    if isinstance(value, (list, tuple, set)):
        return [_normalised_fact(item) for item in value]
    return re.sub(r'[^a-z0-9]+', '', str(value).casefold())


def _deterministic_pair_verdict(pair, evidence):
    """Cross-check the LLM against the four exact source-backed rules."""
    def value(role, *fields):
        return next((v for ref,v in evidence.items()
            if ref.split('.',1)[0]==role and ref.split('.',1)[-1] in fields),None)
    if pair=='cpu_motherboard':
        left=value('cpu','socket','cpu_socket','processor_socket')
        right=value('motherboard','socket','cpu_socket','processor_socket')
        return ('compatible' if _normalised_fact(left)==_normalised_fact(right) else 'incompatible') if left and right else 'insufficient_evidence'
    if pair=='ram_motherboard':
        left=value('ram','ram_type','memory_generation','memory_technology','ram_memory_technology')
        right=value('motherboard','ram_type','memory_generation','memory_technology','ram_memory_technology')
        return ('compatible' if _normalised_fact(left)==_normalised_fact(right) else 'incompatible') if left and right else 'insufficient_evidence'
    if pair=='gpu_motherboard':
        gpu=value('gpu','gpu_interface','interface','pcie_interface')
        board=value('motherboard','gpu_interfaces','expansion_interfaces','pcie_slots')
        def has_pcie(item):
            if isinstance(item,(list,tuple,set)):
                return any(has_pcie(part) for part in item)
            normal=_normalised_fact(item)
            return 'pcie' in normal or 'pciexpress' in normal
        return 'compatible' if has_pcie(gpu) and has_pcie(board) else 'incompatible' if gpu and board else 'insufficient_evidence'
    if pair=='motherboard_case':
        board=value('motherboard','form_factor','motherboard_form_factor')
        supported=value('case','supported_form_factors','motherboard_support')
        if not board or not supported:
            return 'insufficient_evidence'
        board_norm=_normalised_fact(board)
        supported_values=supported if isinstance(supported,(list,tuple,set)) else [supported]
        return 'compatible' if board_norm in {_normalised_fact(item) for item in supported_values} else 'incompatible'
    return 'insufficient_evidence'


def validate_compatibility_review(offer, review):
    """Use exact component facts as the verdict and retain the LLM as an audit signal."""
    if review.get('status') in {'review_pending','review_unavailable'}:
        return review
    review_input=compatibility_review_input(offer)
    parts=review_input['parts']
    roles={part['role'] for part in parts}
    relationships={}
    for first,second in (('motherboard','case'),('cpu','motherboard'),('ram','motherboard'),
            ('gpu','motherboard')):
        if first in roles and second in roles:
            relationships[f'{first}_{second}']={first,second}
    pair_evidence={row['pair']:row['evidence'] for row in review_input['required_pair_evidence']}
    checks=[];withheld=False;model_conflicts=[]
    for original in review.get('checks') or []:
        pair=original.get('pair')
        if pair not in relationships:
            continue
        check=dict(original)
        refs=[ref for ref in check.get('evidence') or []]
        verdict=check.get('model_verdict',check.get('verdict'))
        required_fields=pair_evidence.get(pair,{})
        deterministic=_deterministic_pair_verdict(pair,required_fields)
        if deterministic=='incompatible':
            # A source-backed mismatch is a hard stop, even if the LLM missed it.
            check.update(verdict='incompatible',confidence='high',
                explanation='Verified component specifications conflict.')
            refs=list(required_fields)
        elif deterministic=='compatible':
            # These four checks are literal compatibility rules. Once the exact
            # reviewed fields are present, their deterministic comparison is
            # authoritative; a small local model must not veto a proven match.
            # Keep its verdict visible for audit and follow-up if it disagrees.
            check.update(model_verdict=verdict,verdict='compatible',confidence='high',
                explanation=('Exact source specifications match. LLM agreed.' if verdict=='compatible'
                    else f'Exact source specifications match; LLM returned {verdict or "no verdict"}.'),
                authority='deterministic_source_facts',
                model_agreement='agree' if verdict=='compatible' else 'disagree_or_missing')
            if verdict!='compatible':model_conflicts.append(pair)
        else:
            check.update(model_verdict=verdict,verdict='insufficient_evidence',confidence='low',
                explanation='Required source specifications are incomplete.',
                authority='insufficient_source_facts',model_agreement='not_assessed')
            withheld=True
        check['evidence']=list(required_fields) if required_fields else refs
        checks.append(check)
    present={check['pair'] for check in checks}
    for pair in sorted(relationships.keys()-present):
        checks.append({'pair':pair,'verdict':'insufficient_evidence',
            'explanation':'The model omitted this required relationship.','evidence':[],'confidence':'low'})
    status=('incompatible' if any(check.get('verdict')=='incompatible' for check in checks)
        else 'insufficient_evidence' if any(check.get('verdict')!='compatible' for check in checks)
        or not checks else 'compatible')
    summary=('Exact source fields resolve the checks; the LLM disagreed or omitted: '+', '.join(model_conflicts)+'.'
        if model_conflicts else
        'Some checks still need exact source specifications.' if withheld else review.get('summary'))
    return {**review,'status':status,'checks':checks,'validation_version':9,
        'summary':summary,
        'motherboard_case':next((check for check in checks if check['pair']=='motherboard_case'),None)}


async def review_compatibility_evidence(offer):
    """Review the physical BOM using supplied facts; save an advisory result."""
    from app.services.model_selection_service import model_selection_service

    review_input=compatibility_review_input(offer)
    parts=review_input['parts']
    roles = {row['role'] for row in parts}
    expected_pairs = {'motherboard_case'}
    for first, second in (('cpu', 'motherboard'), ('ram', 'motherboard'), ('gpu', 'motherboard')):
        if first in roles and second in roles:
            expected_pairs.add(f'{first}_{second}')

    # Keep the inference payload focused on the four physical facts the user
    # asked us to check. The wider proposal and raw supplier descriptions are
    # not needed and can cause local queue timeouts or prompt injection.
    model_input={'build':review_input['build'],'required_pair_evidence':[
        {'pair':row['pair'],'facts':[{'reference':ref,'value':value}
            for ref,value in row['evidence'].items()]}
        for row in review_input['required_pair_evidence'] if row['pair'] in expected_pairs]}
    prompt = (
        'Check this PC hardware evidence. For every listed pair decide compatible, incompatible, or insufficient_evidence. '
        'CPU to motherboard: socket values must match. RAM to motherboard: memory generations must match. '
        'GPU to motherboard: both must provide PCIe expansion interface. Motherboard to case: board form factor must occur in the case supported-form-factors list. '
        'Use only supplied facts; missing, ambiguous, or conflicting facts mean insufficient_evidence. Never infer from product names. '
        'Return only one pair and verdict for each check. Do not explain or cite; the application attaches source evidence. '
        f'Use these exact pair identifiers: {", ".join(sorted(expected_pairs))}. '
        'Return JSON only: {"checks":[{"pair":"motherboard_case","verdict":"compatible|incompatible|insufficient_evidence"}]}.\n'
        + '\n\n' + json.dumps(model_input, ensure_ascii=True, separators=(',', ':'))
    )
    result = await model_selection_service.complete(
        task='Scheduled Playbook build compatibility assessment',
        messages=[{'role': 'user', 'content': prompt}],
        system_prompt='Follow the supplied four compatibility rules. Return only the requested JSON pair verdicts. Do not add evidence, explanation, or extra checks.',
        max_tokens=180,
        # DEV shares a priority queue with production and other local clients;
        # a compatibility request can wait before Ollama starts generating.
        timeout=300,
        json_mode=True,
        local_only=True,
    )
    match = re.search(r'\{[\s\S]*\}', result.text or '')
    if not match:
        raise ValueError('The compatibility reviewer returned no JSON object')
    try:
        raw_payload=json.loads(match.group())
        # Small local models occasionally emit this single typo for verdict.
        if isinstance(raw_payload,dict):
            for row in raw_payload.get('checks') or []:
                if isinstance(row,dict) and 'verdict' not in row and isinstance(row.get('verdt'),str):
                    row['verdict']=row.pop('verdt')
        payload = CompatibilityPayload.model_validate(raw_payload)
    except (ValidationError, ValueError) as error:
        raise ValueError('The compatibility reviewer returned malformed compatibility JSON') from error

    checks = []
    for check in payload.checks[:32]:
        verdict = check.verdict if check.verdict in {'compatible', 'incompatible', 'insufficient_evidence'} else 'insufficient_evidence'
        checks.append({
            'pair': str(check.pair or 'unspecified')[:80],
            'verdict': verdict,
            'explanation': str(check.explanation or '')[:300],
            'evidence': [],
            'confidence': check.confidence if check.confidence in {'low', 'medium', 'high'} else 'low',
        })
    pairs = {row['pair'] for row in checks}
    for pair in sorted(expected_pairs-pairs):
        checks.append({'pair':pair,'verdict':'insufficient_evidence',
            'explanation':'The model omitted this required relationship.',
            'evidence':[],'confidence':'low'})
    motherboard_case = next((row for row in checks if row['pair'] == 'motherboard_case'), None)
    status = ('incompatible' if any(row['verdict'] == 'incompatible' for row in checks) else
        'insufficient_evidence' if any(row['verdict'] == 'insufficient_evidence' for row in checks)
        or expected_pairs - pairs else 'compatible')
    return validate_compatibility_review(offer,{
        'status': status,
        'summary': str(payload.summary or 'Compatibility review completed.')[:400],
        'motherboard_case': motherboard_case,
        'checks': checks,
        'authority': 'advisory_only',
        'provider': getattr(result, 'provider', None),
        'model': getattr(result, 'model', None),
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
    })
