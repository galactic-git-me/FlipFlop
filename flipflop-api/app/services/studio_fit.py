"""Pure, conservative physical checks. Unknown measurements never mean a pass.

Listing.raw_specs['configurator'] is an optional, reviewed engineering record.
No dimension is inferred from a product family name or a generated mesh.
"""
from math import isfinite


SPEC_KEYS = {
    'gpu_interface','gpu_interfaces',
    'socket', 'supported_sockets', 'form_factor', 'supported_form_factors',
    'ram_type', 'ram_slots', 'ram_modules', 'ram_height_mm', 'ram_clearance_mm',
    'length_mm', 'height_mm', 'width_mm', 'depth_mm', 'max_gpu_length_mm',
    'max_cooler_height_mm', 'max_psu_length_mm', 'psu_form_factors',
    'power_w', 'wattage', 'recommended_psu_w', 'gpu_power_connectors',
    'psu_connectors', 'storage_interface', 'storage_interfaces', 'm2_lengths',
    'm2_length', 'sata_bays', 'cooler_type', 'radiator_mm', 'radiator_support',
    'front_radiator_depth_mm', 'installed_fans', 'cooling_capacity_w',
    'bios_cpu_ids', 'reviewed', 'source_url', 'cpu_id', 'm2_slots', 'sata_ports', 'integrated_graphics',
}


def engineering_specs(raw):
    value = raw.get('configurator', {}) if isinstance(raw, dict) else {}
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in SPEC_KEYS if key in value}


def evaluate_fit(parts, case, *, gpu_required=True):
    """parts: {category: reviewed engineering dict}; case: catalogue fields.

    A result has stable code, severity, message and affected categories.
    Numeric boundary equality fits. Power includes 25% reserve + 75W system load.
    Airflow remains a recommendation, not a thermal simulation.
    """
    checks = []

    def add(code, severity, message, *affected):
        checks.append(dict(code=code, severity=severity, message=message, affected=list(affected)))

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0

    def measured(code, value, limit, label, *affected):
        if not number(value) or not number(limit):
            add(code, 'unknown', f'{label}: verified measurements needed.', *affected)
        elif value > limit:
            add(code, 'error', f'{label}: {value:g} exceeds {limit:g}.', *affected)
        else:
            add(code, 'pass', f'{label}: {value:g} / {limit:g}.', *affected)

    p = {key: value if value.get('reviewed') is True else {} for key, value in parts.items()}
    cpu, board, gpu, ram, cooler, psu = [p.get(key, {}) for key in ('cpu', 'motherboard', 'gpu', 'ram', 'cooling', 'psu')]
    storages={key:value for key,value in p.items() if key=='storage' or key.startswith('storage_')}
    gpu_selected = 'gpu' in parts
    gpu_checks_required = gpu_required or gpu_selected
    if not gpu_checks_required:
        graphics=cpu.get('integrated_graphics')
        add('INTEGRATED_GRAPHICS','pass' if graphics is True else 'error' if graphics is False else 'unknown',
            'Integrated graphics confirmed.' if graphics is True else
            'This CPU has no integrated graphics; a graphics card is required.' if graphics is False else
            'Verify integrated graphics for this build without a graphics card.','cpu','gpu')
    case = case or {}
    case_specs = case.get('engineering', {})
    def match(code, actual, allowed, label, *affected):
        if not actual or not isinstance(allowed, list):
            add(code, 'unknown', f'{label}: verified specification needed.', *affected)
        elif str(actual).lower() not in [str(item).lower() for item in allowed]:
            add(code, 'error', f'{label}: {actual} is not supported ({", ".join(map(str, allowed))}).', *affected)
        else:
            add(code, 'pass', f'{label}: {actual}.', *affected)

    match('CPU_SOCKET', cpu.get('socket'), [board['socket']] if board.get('socket') else None, 'CPU socket', 'cpu', 'motherboard')
    match('COOLER_SOCKET', cpu.get('socket'), cooler.get('supported_sockets'), 'Cooler mounting', 'cpu', 'cooling')
    match('RAM_TYPE', ram.get('ram_type'), [board['ram_type']] if board.get('ram_type') else None, 'Memory generation', 'ram', 'motherboard')
    measured('RAM_SLOTS', ram.get('ram_modules'), board.get('ram_slots'), 'Memory modules / slots', 'ram', 'motherboard')
    factors = {'atx': ['atx', 'matx', 'itx'], 'matx': ['matx', 'itx'], 'itx': ['itx']}
    match('BOARD_FIT', board.get('form_factor'), case.get('supported_form_factors') or factors.get(str(case.get('form_factor', '')).lower()), 'Motherboard fit', 'motherboard', 'case')
    if gpu_checks_required:
        gpu_limit = case.get('max_gpu_length_mm')
        if number(gpu_limit) and number(cooler.get('front_radiator_depth_mm')):
            gpu_limit -= cooler['front_radiator_depth_mm']
        measured('GPU_LENGTH', gpu.get('length_mm'), gpu_limit, 'GPU length (mm)', 'gpu', 'case', 'cooling')
    if cooler.get('cooler_type') == 'aio':
        radiators = case.get('radiator_support')
        sizes = [size for values in radiators.values() if isinstance(values, list) for size in values] if isinstance(radiators, dict) else None
        match('RADIATOR_FIT', cooler.get('radiator_mm'), sizes, 'Radiator mounting (mm)', 'cooling', 'case')
        add('RADIATOR_CLEARANCE', 'unknown', 'Verify radiator thickness, tube routing and motherboard clearance.', 'cooling', 'motherboard', 'case')
    else:
        measured('COOLER_HEIGHT', cooler.get('height_mm'), case.get('max_cooler_height_mm'), 'Cooler height (mm)', 'cooling', 'case')
        measured('RAM_CLEARANCE', ram.get('ram_height_mm'), cooler.get('ram_clearance_mm'), 'RAM clearance (mm)', 'ram', 'cooling')
    match('PSU_FORMAT', psu.get('form_factor'), case_specs.get('psu_form_factors'), 'PSU format', 'psu', 'case')
    measured('PSU_LENGTH', psu.get('length_mm'), case_specs.get('max_psu_length_mm'), 'PSU length (mm)', 'psu', 'case')
    nvme_roles=[];sata_roles=[]
    for role,ssd in storages.items():
        interface=ssd.get('storage_interface')
        code_suffix='' if role=='storage' else f'_{role.upper()}'
        match(f'SSD_INTERFACE{code_suffix}',interface,board.get('storage_interfaces'),
            f'{role.replace("_"," ").title()} interface',role,'motherboard')
        if interface in {'nvme','m2'}:
            nvme_roles.append(role)
            match(f'SSD_MOUNT{code_suffix}',ssd.get('m2_length'),board.get('m2_lengths'),
                f'{role.replace("_"," ").title()} M.2 mounting',role,'motherboard')
        elif interface=='sata':
            sata_roles.append(role)
        else:
            add(f'SSD_MOUNT_{role.upper()}','unknown',
                f'{role.replace("_"," ").title()}: verified M.2/SATA interface needed.',role,'motherboard','case')
    if nvme_roles:
        m2_slot_count=board.get('m2_slots')
        if m2_slot_count is None and len(nvme_roles)==1 and board.get('m2_lengths'):
            # A reviewed supported-length list proves at least one usable slot,
            # but cannot prove capacity for a second or later NVMe drive.
            m2_slot_count=1
        measured('M2_SLOT_COUNT',len(nvme_roles),m2_slot_count,'NVMe drives / M.2 slots',*nvme_roles,'motherboard')
    if sata_roles:
        measured('SATA_PORT_COUNT',len(sata_roles),board.get('sata_ports'),'SATA drives / motherboard ports',*sata_roles,'motherboard')
        measured('SATA_BAY_COUNT',len(sata_roles),case_specs.get('sata_bays'),'SATA drives / case bays',*sata_roles,'case')
    demand = None
    if number(cpu.get('power_w')) and (number(gpu.get('power_w')) or not gpu_checks_required):
        demand = (cpu['power_w'] + (gpu.get('power_w') or 0) + 75) * 1.25
        if gpu_checks_required and number(gpu.get('recommended_psu_w')):
            demand = max(demand, gpu['recommended_psu_w'])
    measured('POWER', demand, psu.get('wattage'), 'PSU reserve (W)', 'cpu', 'gpu', 'psu')
    required, supplied = gpu.get('gpu_power_connectors'), psu.get('psu_connectors')
    if not gpu_checks_required:
        pass
    elif isinstance(required, dict) and isinstance(supplied, dict):
        for name, count in required.items():
            measured('POWER_CONNECTOR_' + name, count, supplied.get(name, 0), f'{name} connectors', 'gpu', 'psu')
    else:
        add('POWER_CONNECTORS', 'unknown', 'Verify GPU power connectors and cable bend clearance.', 'gpu', 'psu')
    if not cpu.get('cpu_id') or cpu['cpu_id'] not in board.get('bios_cpu_ids', []):
        add('BIOS', 'unknown', 'Confirm the installed BIOS supports this exact CPU.', 'cpu', 'motherboard')
    else:
        add('BIOS', 'pass', 'CPU support confirmed in engineering record.', 'cpu', 'motherboard')
    add('AIRFLOW', 'warning', 'Keep intake and exhaust paths clear. Fan layout and temperatures require a build test.', 'case', 'cooling')
    return checks


def evaluate_playbook_fit(parts, case, *, gpu_required=True):
    """Apply the owner-selected minimum Playbook compatibility gate.

    Publication checks are CPU/motherboard socket, GPU/motherboard interface,
    RAM generation/motherboard and motherboard/case form factor. A build without
    a discrete GPU must have verified integrated graphics. Other physical,
    electrical and installation checks remain workshop work and do not block
    Playbook proposal approval.
    """
    checks=evaluate_fit(parts,case,gpu_required=gpu_required)
    core={'CPU_SOCKET','RAM_TYPE','BOARD_FIT','INTEGRATED_GRAPHICS','GPU_INTERFACE'}
    for check in checks:
        if check['code'] in core:
            check['stage']='publication'
        else:
            check['stage']='workshop'
            # This checklist is intentionally narrower than the complete
            # workshop fit report. Slot count, clearances, PSU sizing/cabling,
            # BIOS and storage mounting are workshop verification items.
            check['severity']='warning'
    if gpu_required or 'gpu' in parts:
        gpu=parts.get('gpu') or {};board=parts.get('motherboard') or {}
        actual=gpu.get('gpu_interface') if gpu.get('reviewed') is True else None
        supported=board.get('gpu_interfaces') if board.get('reviewed') is True else None
        severity=('unknown' if not actual or not isinstance(supported,list)
            else 'pass' if str(actual).casefold() in [str(v).casefold() for v in supported] else 'error')
        checks.append({'code':'GPU_INTERFACE','severity':severity,'stage':'publication',
            'message':'GPU and motherboard expansion interface: '+('compatible.' if severity=='pass' else 'incompatible.' if severity=='error' else 'source specifications needed.'),
            'affected':['gpu','motherboard']})
    return checks
