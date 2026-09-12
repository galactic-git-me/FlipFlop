"""Pure, conservative physical checks. Unknown measurements never mean a pass.

Listing.raw_specs['configurator'] is an optional, reviewed engineering record.
No dimension is inferred from a product family name or a generated mesh.
"""
from math import isfinite


SPEC_KEYS = {
    'socket', 'supported_sockets', 'form_factor', 'supported_form_factors',
    'ram_type', 'ram_slots', 'ram_modules', 'ram_height_mm', 'ram_clearance_mm',
    'length_mm', 'height_mm', 'width_mm', 'depth_mm', 'max_gpu_length_mm',
    'max_cooler_height_mm', 'max_psu_length_mm', 'psu_form_factors',
    'power_w', 'wattage', 'recommended_psu_w', 'gpu_power_connectors',
    'psu_connectors', 'storage_interface', 'storage_interfaces', 'm2_lengths',
    'm2_length', 'sata_bays', 'cooler_type', 'radiator_mm', 'radiator_support',
    'front_radiator_depth_mm', 'installed_fans', 'cooling_capacity_w',
    'bios_cpu_ids', 'reviewed', 'source_url', 'cpu_id',
}


def engineering_specs(raw):
    value = raw.get('configurator', {}) if isinstance(raw, dict) else {}
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in SPEC_KEYS if key in value}


def evaluate_fit(parts, case):
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
    cpu, board, gpu, ram, cooler, psu, ssd = [p.get(key, {}) for key in ('cpu', 'motherboard', 'gpu', 'ram', 'cooling', 'psu', 'storage')]
    case = case or {}
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
    match('BOARD_FIT', board.get('form_factor'), factors.get(str(case.get('form_factor', '')).lower()), 'Motherboard fit', 'motherboard', 'case')
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
    case_specs = case.get('engineering', {})
    match('PSU_FORMAT', psu.get('form_factor'), case_specs.get('psu_form_factors'), 'PSU format', 'psu', 'case')
    measured('PSU_LENGTH', psu.get('length_mm'), case_specs.get('max_psu_length_mm'), 'PSU length (mm)', 'psu', 'case')
    match('SSD_INTERFACE', ssd.get('storage_interface'), board.get('storage_interfaces'), 'SSD interface', 'storage', 'motherboard')
    if ssd.get('storage_interface') == 'sata':
        measured('SSD_MOUNT', 1, case_specs.get('sata_bays'), 'SATA mounting bays', 'storage', 'case')
    else:
        match('SSD_MOUNT', ssd.get('m2_length'), board.get('m2_lengths'), 'M.2 mounting', 'storage', 'motherboard')
    demand = None
    if number(cpu.get('power_w')) and number(gpu.get('power_w')):
        demand = (cpu['power_w'] + gpu['power_w'] + 75) * 1.25
        if number(gpu.get('recommended_psu_w')):
            demand = max(demand, gpu['recommended_psu_w'])
    measured('POWER', demand, psu.get('wattage'), 'PSU reserve (W)', 'cpu', 'gpu', 'psu')
    required, supplied = gpu.get('gpu_power_connectors'), psu.get('psu_connectors')
    if isinstance(required, dict) and isinstance(supplied, dict):
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
