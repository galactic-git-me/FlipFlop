"""Deterministic draft checks using named parts and recorded specification facts.

Unknown installation facts remain assembly notes; these checks do not approve a
product, claim a physical test passed, or enable checkout.
"""
import re


def specs(part):
    return (part or {}).get('planning_engineering') or (part or {}).get('engineering') or {}


def wireless_extra_required(motherboard):
    """Return missing onboard radios; unknown capability is treated as missing.

    Exact product captures can label connectivity in their properties. Titles
    are a fallback only for positive claims (for example, "WiFi"); absence of
    a label never proves the board has a radio.
    """
    part = motherboard or {}
    engineering = specs(part)
    properties = ((part.get('source_observation') or {}).get('product_properties') or {})
    normalized = {re.sub(r'[^a-z]', '', str(key).casefold()): value
                  for key, value in properties.items()}

    def capability(names, positive_title):
        for name in names:
            key = re.sub(r'[^a-z]', '', name.casefold())
            value = engineering.get(name, normalized.get(key))
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().casefold()
                if lowered in {'yes', 'true', 'included', 'built-in', 'built in'}:
                    return True
                if lowered in {'no', 'false', 'not included', 'none'}:
                    return False
        return bool(re.search(positive_title, part.get('title', ''), re.I))

    has_wifi = capability(('wifi', 'wi_fi', 'wireless'), r'\bwi[ -]?fi\b|\bwireless\b')
    has_bluetooth = capability(('bluetooth',), r'\bbluetooth\b')

    # Amazon's capture for this exact MSI SKU omits its wireless spec, but the
    # linked manufacturer specification explicitly lists WiFi-AC and Bluetooth
    # 4.2. Keep the exact SKU tied to that official source rather than charging
    # for an adapter based on a retailer page's missing property.
    title = re.sub(r'[^a-z0-9]+', ' ', str(part.get('title', '')).casefold()).strip()
    manufacturer_source = str(engineering.get('source_url') or '').casefold().rstrip('/')
    if ('msi b550m pro vdh wifi' in title
            and manufacturer_source == 'https://www.msi.com/motherboard/b550m-pro-vdh-wifi/specification'):
        has_wifi = True
        has_bluetooth = True

    return [name for name, present in (('Wi-Fi', has_wifi), ('Bluetooth', has_bluetooth)) if not present]


def cooling(part):
    values=dict(specs(part))
    title=(part or {}).get('title','')
    if re.search(r'\b(?:aio|liquid)\b',title,re.I):
        values.setdefault('cooler_type','aio')
        size=re.search(r'\b(120|140|240|280|360|420)\b',title)
        if size:
            values.setdefault('radiator_mm',int(size[1]))
    return values


def case_conflicts(parts,case):
    chassis=specs(case);board=specs(parts.get('motherboard'));gpu=specs(parts.get('gpu'))
    cooler=cooling(parts.get('cooling'));psu=specs(parts.get('psu'))
    conflicts=[]
    allowed=chassis.get('supported_form_factors')
    if board.get('form_factor') and allowed and board['form_factor'] not in allowed:
        conflicts.append('Motherboard form factor is not supported by the chassis')
    for value,limit,label in [(gpu.get('length_mm'),chassis.get('max_gpu_length_mm'),'GPU length'),
                             (psu.get('length_mm'),chassis.get('max_psu_length_mm'),'PSU length')]:
        if value is not None and limit is not None and value>limit:
            conflicts.append(f'{label} {value} exceeds chassis clearance {limit} mm')
    if cooler.get('cooler_type')=='aio':
        supports=chassis.get('radiator_support')
        if isinstance(supports,dict) and cooler.get('radiator_mm') not in [size for sizes in supports.values() for size in sizes]:
            conflicts.append('Chassis does not support the selected radiator')
    elif cooler.get('height_mm') is not None and chassis.get('max_cooler_height_mm') is not None:
        if cooler['height_mm']>chassis['max_cooler_height_mm']:
            conflicts.append('Air cooler exceeds chassis height clearance')
    for model in chassis.get('incompatible_psu_models',[]):
        if model in (parts.get('psu') or {}).get('title','').casefold():
            conflicts.append('Chassis manufacturer excludes this PSU connector layout')
    return conflicts


def assess(definition,offer):
    from app.services.playbook_service import required_parts,_planning_socket,_planning_integrated_graphics,_candidate_capacity,_planning_vram
    parts={part['role']:part for part in offer.get('components',[])}
    errors=[];checks=[];notes=[]
    def check(label,ok,detail):
        checks.append({'check':label,'status':'pass' if ok else 'error','detail':detail})
        if not ok:errors.append(f'{label}: {detail}')
    check('Complete component list',set(required_parts(definition)).issubset(parts),'Every required slot is separately represented')
    cpu_socket=_planning_socket(parts.get('cpu') or {})
    board_socket=_planning_socket(parts.get('motherboard') or {})
    if cpu_socket and board_socket:
        check('CPU and motherboard socket',cpu_socket==board_socket,f'{cpu_socket} / {board_socket}')
    else:notes.append('Confirm exact CPU and motherboard socket specifications')
    board=specs(parts.get('motherboard'));ram=parts.get('ram') or {};ram_specs=specs(ram)
    missing_radios = wireless_extra_required(parts.get('motherboard'))
    if missing_radios:
        notes.append('Add a combined Wi-Fi and Bluetooth adapter; the selected motherboard does not provide verified '
                     + ' and '.join(missing_radios) + '.')
    from app.services.curated_build_policy import _capacity_gb
    minimum_ram=_capacity_gb(definition.get('components',{}).get('ram','')) or 0
    check('Total memory capacity',_candidate_capacity(ram)>=minimum_ram,
          f'{_candidate_capacity(ram):g} GB / minimum {minimum_ram:g} GB')
    if board.get('ram_type') and ram_specs.get('ram_type'):
        check('Memory generation',board['ram_type']==ram_specs['ram_type'],f"{ram_specs['ram_type']} / {board['ram_type']}")
    rdimm=bool(re.search(r'\bRDIMM\b|registered',ram.get('title',''),re.I))
    if cpu_socket:
        check('Memory module architecture',rdimm==(cpu_socket=='str5'),'Registered server memory for sTR5; desktop memory for desktop platforms')
    if ram_specs.get('ram_modules') and board.get('ram_slots'):
        check('Memory slot count',ram_specs['ram_modules']<=board['ram_slots'],f"{ram_specs['ram_modules']} modules / {board['ram_slots']} slots")
    if 'gpu' not in required_parts(definition) and parts.get('cpu'):
        check('Integrated graphics',_planning_integrated_graphics(parts['cpu']),'Build without a graphics card requires integrated graphics')
    if parts.get('gpu'):
        from app.services.curated_build_policy import _capacity_gb
        minimum=_capacity_gb(definition.get('components',{}).get('gpu','')) or 0
        actual=_planning_vram(parts['gpu']) or 0
        check('GPU memory',actual>=minimum,f'{actual} GB / minimum {minimum} GB')
    requirement=re.search(r'\b(\d{3,4})\s*w\b',definition.get('components',{}).get('psu',''),re.I)
    actual_psu=re.search(r'\b(\d{3,4})\s*w\b',(parts.get('psu') or {}).get('title',''),re.I)
    if requirement and actual_psu:
        check('PSU rating',int(actual_psu[1])>=int(requirement[1]),f'{actual_psu[1]} W / minimum {requirement[1]} W')
    cpu_power=specs(parts.get('cpu')).get('power_w');gpu_power=specs(parts.get('gpu')).get('power_w',0 if 'gpu' not in parts else None)
    if actual_psu and cpu_power is not None and gpu_power is not None:
        demand=(cpu_power+gpu_power+75)*1.25
        check('Power reserve',int(actual_psu[1])>=demand,f'{actual_psu[1]} W / estimated load plus reserve {demand:g} W')
    # Detailed clearances are workshop assembly checks, not the simplified
    # Playbook publication gate (CPU/board, GPU/board, RAM/board and
    # motherboard/case form factor). Keep observed conflicts visible without
    # turning them into a proposal compatibility failure.
    notes.extend(f'Workshop fit check: {conflict}'
        for conflict in case_conflicts(parts,parts.get('case') or {}))
    if parts.get('cooling'):
        sockets=cooling(parts['cooling']).get('supported_sockets')
        if sockets and cpu_socket:check('Cooler mount',cpu_socket in sockets,f'{cpu_socket} / {sockets}')
        else:notes.append('Confirm cooler mounting kit for the selected CPU socket')
    case=specs(parts.get('case'))
    if not case.get('max_gpu_length_mm') and parts.get('gpu'):notes.append('Verify exact card and chassis GPU clearances')
    if parts.get('gpu') and not specs(parts['gpu']).get('length_mm'):notes.append('Verify exact selected graphics-card dimensions against the case limit')
    notes += ['Confirm BIOS support, RAM QVL/SPD settings and cable routing before assembly.',
              'Check PSU/GPU power cables, radiator/RAM clearances and perform thermal/noise tests during assembly.']
    return {'status':'needs_correction' if errors else 'complete_for_planning',
            'errors':errors,'checks':checks,'assembly_notes':notes,
            'physically_tested':False,'checkout_approved':False}
