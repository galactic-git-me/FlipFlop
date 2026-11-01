"""Exact-model manufacturer facts for draft planning, separate from sales approval."""
import re


def manufacturer_facts(role,title):
    text=title.casefold()
    if role=='motherboard' and re.search(r'\bwrx90\s+ws\s+evo\b',text):
        return {'source_url':'https://www.asrock.com/mb/AMD/WRX90%20WS%20EVO/index.asp',
                'socket':'str5','ram_type':'ddr5','ram_slots':8,'form_factor':'ssi-eeb',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],'m2_slots':2}
    if role=='case' and re.search(r'\blancool\s+217\s+(?:infinity|inf)\b',text):
        return {'source_url':'https://lian-li.com/product/lancool-217-inf/',
                'supported_form_factors':['itx','matx','atx','e-atx','ssi-eeb'],
                'max_gpu_length_mm':380,'max_cooler_height_mm':180,'max_psu_length_mm':220,
                'psu_form_factors':['atx'],'installed_fans':3,
                'assembly_layout':'EEB mode: remove the right bracket shielding plate and cable-routing grommets, per manufacturer instructions.'}
    if role=='cpu' and re.search(r'\b9975wx\b',text):
        return {'source_url':'https://www.amd.com/en/products/processors/workstations/ryzen-threadripper/9000-wx-series/amd-ryzen-threadripper-pro-9975wx.html',
                'socket':'str5','power_w':350,'integrated_graphics':False,'cpu_id':'9975wx'}
    if role=='motherboard' and re.search(r'\ba520m\s+k\s+v2\b',text):
        return {'source_url':'https://www.gigabyte.com/Motherboard/A520M-K-V2-rev-10/sp',
                'socket':'am4','ram_type':'ddr4','form_factor':'matx',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],
                'ram_slots':2,'m2_slots':1,'sata_ports':4}
    if role=='case' and re.search(r'\bframe\s+4000d\b',text):
        return {'source_url':'https://www.corsair.com/ww/en/p/pc-cases/cc-9011296-ww/frame-4000d-rs-argb-modular-mid-tower-pc-case-cc-9011296-ww',
                'supported_form_factors':['itx','matx','atx','e-atx'],
                'max_gpu_length_mm':430,'max_cooler_height_mm':170,
                'max_psu_length_mm':220,'psu_form_factors':['atx']}
    if role=='cpu' and re.search(r'\bryzen(?:sets)?\s*5\s+5600\b',text):
        return {'source_url':'https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-5-5600.html',
                'socket':'am4','power_w':65,'cpu_id':'5600','integrated_graphics':False}
    if role=='motherboard' and re.search(r'\bb550m[ -]+pro[ -]+vdh[ -]+wifi\b',text) and not re.search(r'\bvdh[ -]+wifi\s*6\b',text):
        return {'source_url':'https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI/Specification',
                'socket':'am4','ram_type':'ddr4','ram_slots':4,'form_factor':'matx',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],'m2_slots':2,'sata_ports':4,
                'm2_lengths':[2242,2260,2280]}
    if role=='ram' and 'cmk32gx4m2e3200c16' in text:
        return {'source_url':'https://www.corsair.com/uk/en/p/memory/cmk32gx4m2e3200c16/vengeance-lpx-32gb-2-x-16gb-ddr4-dram-3200mhz-c16-memory-kit-black-cmk32gx4m2e3200c16',
                'dimension_source_url':'https://www.littlebit.ch/media/productattach/l/1/l1124408.pdf',
                'ram_type':'ddr4','ram_modules':2,'ram_height_mm':34}
    if role=='gpu' and 'asus' in text and re.search(r'\brtx\s*5050\b',text) and 'dual' in text and re.search(r'\boc\b',text) and not re.search(r'\bevo\b|low.profile',text):
        return {'source_url':'https://www.asus.com/ie/motherboards-components/graphics-cards/dual/dual-rtx5050-o8g/techspec/',
                'power_reference_url':'https://www.nvidia.com/en-ph/geforce/graphics-cards/50-series/rtx-5050/',
                'gpu_interface':'pcie','vram_gb':8,'length_mm':203,'power_w':130,'recommended_psu_w':550,
                'gpu_power_connectors':{'8pin':1}}
    if role in {'storage','storage_secondary'} and 'kingston' in text and re.search(r'\bnv3\b',text) and re.search(r'\b2280\b|\bsnv3s/',text):
        return {'source_url':'https://www.kingston.com/en/ssd/nv3-nvme-pcie-ssd',
                'storage_interface':'nvme','m2_length':2280}
    if role=='psu' and re.search(r'\bsystem\s+power\s+11\b',text) and re.search(r'\b750\s*w\b',text):
        return {'source_url':'https://www.bequiet.com/en/powersupply/5906',
                'wattage':750,'form_factor':'atx','psu_connectors':{'8pin':3,'16pin':1}}
    if role=='cpu' and re.search(r'\b(?:250k|270k)\s+plus\b',text):
        is_250k='250k' in text
        return {'source_url':('https://www.intel.com/content/www/us/en/products/sku/245694/intel-core-ultra-5-processor-250k-plus-30m-cache-up-to-5-30-ghz/specifications.html'
                    if is_250k else 'https://www.intel.com/content/www/us/en/products/sku/245692/intel-core-ultra-7-processor-270k-plus-36m-cache-up-to-5-50-ghz/specifications.html'),
                'socket':'lga1851','integrated_graphics':True,
                'cpu_id':'250k plus' if is_250k else '270k plus'}
    if role=='cpu':
        match=re.search(r'\b(9600x|9700x|9800x3d|9850x3d)\b',text)
        if match:
            model=match[1]
            source_url={
                '9600x':'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-5-9600x.html',
                '9700x':'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9700x.html',
                '9800x3d':'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9800x3d.html',
                '9850x3d':'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9850x3d.html'}[model]
            return {'source_url':source_url,
                    'socket':'am5','power_w':120 if model in {'9800x3d','9850x3d'} else 65,
                    'integrated_graphics':True,'cpu_id':model}
    if role=='motherboard' and re.search(r'\bprime\s+x870[ -]p\b',text) and not re.search(r'\bwifi\b|\bwi[ -]?fi\b',text):
        return {'source_url':'https://www.asus.com/motherboards-components/motherboards/prime/prime-x870-p/techspec/',
                'socket':'am5','ram_type':'ddr5','ram_slots':4,'form_factor':'atx',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata']}
    if role=='motherboard' and re.search(r'\bproart\s+z890[ -]+creator\s+wifi\b',text):
        return {'source_url':'https://www.asus.com/motherboards-components/motherboards/proart/proart-z890-creator-wifi/techspec/',
                'socket':'lga1851','ram_type':'ddr5','ram_slots':4,'form_factor':'atx',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],
                'wifi':True,'bluetooth':True}
    if role=='motherboard' and re.search(r'\btuf\s+gaming\s+z890[ -]+plus\s+wifi\b',text):
        return {'source_url':'https://www.asus.com/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z890-plus-wifi/techspec/',
                'socket':'lga1851','ram_type':'ddr5','ram_slots':4,'form_factor':'atx',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],
                'wifi':True,'bluetooth':True}
    if role=='motherboard' and re.search(r'\brog\s+crosshair\s+x870e\s+hero\b',text):
        return {'source_url':'https://rog.asus.com/uk/motherboards/rog-crosshair/rog-crosshair-x870e-hero/spec/',
                'socket':'am5','ram_type':'ddr5','ram_slots':4,'form_factor':'atx',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],
                'wifi':True,'bluetooth':True}
    if role=='motherboard' and 'wrx90e-sage' in text:
        return {'source_url':'https://www.asus.com/motherboards-components/motherboards/workstation/pro-ws-wrx90e-sage-se/techspec/',
                'socket':'str5','ram_type':'ddr5','ram_slots':8,'form_factor':'ssi-eeb',
                'gpu_interfaces':['pcie'],'storage_interfaces':['nvme','sata'],'m2_slots':4,'m2_lengths':[2242,2260,2280,22110],
                'bios_cpu_ids':['7975wx']}
    if role=='case' and re.search(r'\blancool\s*207\b',text):
        return {'source_url':'https://lian-li.com/product/lancool-207/',
                'supported_form_factors':['atx','matx','itx'],'max_gpu_length_mm':375,
                'max_cooler_height_mm':180,'max_psu_length_mm':159,'psu_form_factors':['atx'],
                'radiator_support':{'top':[240,280,360]},'installed_fans':4,
                'incompatible_psu_models':['lian li rs']}
    if role=='psu' and 'pure power 12' in text and '850w' in text and not re.search(r'\b12\s*m\b',text):
        return {'source_url':'https://www.bequiet.com/en/powersupply/5253',
                'wattage':850,'length_mm':160,'form_factor':'atx',
                'psu_connectors':{'16pin':1,'8pin':3}}
    if role=='case' and 'apnx' in text and re.search(r'\bc1\b',text):
        return {'source_url':'https://www.apnx.com/product/c1/',
                'supported_form_factors':['atx','matx','itx'],'max_gpu_length_mm':395,
                'max_cooler_height_mm':166,'max_psu_length_mm':270,'psu_form_factors':['atx'],
                'radiator_support':{'top':[120,240,280,360],'side':[120,240,360]},'installed_fans':4}
    if role=='case' and 'ionz' in text and 'kz10' in text:
        return {'source_url':'https://www.beecomputers.co.uk/products/pc-gaming-case-only-ionz-kz10-black',
                'supported_form_factors':['atx','matx','itx'],'max_gpu_length_mm':320,
                'max_cooler_height_mm':150,'psu_form_factors':['atx'],'radiator_support':{}}
    if role=='cooling' and 'thermalright' in text and re.search(r'\bpeerless\s+assassin\s+120\s+se\b',text) and not re.search(r'\b(?:argb|rgb|white|black)\b',text):
        return {'source_url':'https://www.thermalright.com/product/peerless-assassin-120-se/',
                'supported_sockets':['am4','am5','lga1150','lga1151','lga1155','lga1156','lga1200','lga1700','lga1851'],
                'height_mm':155,'cooler_type':'air'}
    if role=='cooling' and re.search(r'\bnh-d15\s+g2\b',text):
        return {'source_url':'https://www.noctua.at/en/products/nh-d15-g2-chromax-black/specifications',
                'supported_sockets':['am4','am5','lga1700','lga1851'],'height_mm':168,'cooler_type':'air'}
    if role=='gpu' and 'msi' in text and '5090' in text and 'ventus' in text:
        return {'source_url':'https://www.msi.com/Graphics-Card/GeForce-RTX-5090-32G-VENTUS-3X-OC/Specification',
                'vram_gb':32,'length_mm':325,'power_w':575,'recommended_psu_w':1000,
                'gpu_power_connectors':{'16pin':1},'gpu_interface':'pcie'}
    if role=='gpu' and re.search(r'\brtx\s*6000\b',text) and re.search(r'\bada\b',text):
        return {'source_url':'https://www.pny.com/nvidia-rtx-6000-ada',
                'vram_gb':48,'power_w':300,'length_mm':266.7,
                'gpu_power_connectors':{'16pin':1},'gpu_interface':'pcie'}
    if role=='cpu' and re.search(r'\b7975wx\b',text):
        return {'source_url':'https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/amd-ryzen-threadripper-pro-7000-wx-series/amd-ryzen-threadripper-pro-7975wx.html',
                'socket':'str5','power_w':350,'integrated_graphics':False,'cpu_id':'7975wx'}
    if role=='case' and 'fractal' in text and re.search(r'\bdefine\s*7\s*xl\b',text):
        return {'source_url':'https://www.fractal-design.com/products/cases/define-series/define-7-xl/define-7-xl-black-light-tg/',
                'supported_form_factors':['atx','matx','itx','e-atx','ssi-eeb'],
                'max_gpu_length_mm':505,'max_cooler_height_mm':185,
                'max_psu_length_mm':250,'psu_form_factors':['atx'],'installed_fans':3,
                'assembly_layout':'Open layout with supplied front fans installed'}
    if role=='cooling' and re.search(r'\bnh-u14s\s+tr5-sp6\b',text):
        return {'source_url':'https://noctua.at/en/nh-u14s-tr5-sp6/specification?tab=comp',
                'supported_sockets':['str5','sp6'],'height_mm':165,'cooler_type':'air'}
    if role=='cooling' and re.search(r'\bfreezer\s+36\b',text) and not re.search(r'\b36-s\b',text):
        return {'source_url':'https://www.arctic.de/media/6b/50/57/1709195123/Spec_Sheet_Freezer_36_EN.pdf',
                'supported_sockets':['am4','am5','lga1700','lga1851'],'height_mm':159,'cooler_type':'air',
                **({'ram_clearance_mm':42.9,
                    'clearance_source_url':'https://support.arctic.de/products/freezer-36/techdocs/Freezer%2036%20%28Black%29%20-%202D%20Drawing.pdf'}
                   if 'black' in text and not re.search(r'a[- ]?rgb|\bco\b',text) else {})}
    return {}


# Field-level primary references checked on 25 October 2026. Generic family
# pages above remain planning-only; they cannot certify a product's dimensions.
_VERIFIED_REFERENCE_FIELDS = {
    'https://www.asrock.com/mb/AMD/WRX90%20WS%20EVO/index.asp': {
        'socket','ram_type','ram_slots','form_factor','gpu_interfaces','storage_interfaces','m2_slots'},
    'https://lian-li.com/product/lancool-217-inf/': {
        'supported_form_factors','max_gpu_length_mm','max_cooler_height_mm','max_psu_length_mm',
        'psu_form_factors','installed_fans'},
    'https://www.amd.com/en/products/processors/workstations/ryzen-threadripper/9000-wx-series/amd-ryzen-threadripper-pro-9975wx.html': {
        'socket','power_w','integrated_graphics','cpu_id'},
    'https://www.thermalright.com/product/peerless-assassin-120-se/': {'supported_sockets','height_mm','cooler_type'},
    'https://www.kingston.com/en/ssd/nv3-nvme-pcie-ssd': {'storage_interface','m2_length'},
    'https://www.bequiet.com/en/powersupply/5906': {'wattage','form_factor','psu_connectors'},
    'https://www.arctic.de/media/6b/50/57/1709195123/Spec_Sheet_Freezer_36_EN.pdf': {'supported_sockets','height_mm','cooler_type','ram_clearance_mm'},
    'https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI/Specification': {
        'socket','ram_type','ram_slots','form_factor','storage_interfaces',
        'm2_slots','sata_ports','m2_lengths','gpu_interfaces'},
    'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-5-9600x.html': {
        'socket','power_w','integrated_graphics','cpu_id'},
    'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9700x.html': {
        'socket','power_w','integrated_graphics','cpu_id'},
    'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9800x3d.html': {
        'socket','power_w','integrated_graphics','cpu_id'},
    'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9850x3d.html': {
        'socket','power_w','integrated_graphics','cpu_id'},
    'https://www.intel.com/content/www/us/en/products/sku/245694/intel-core-ultra-5-processor-250k-plus-30m-cache-up-to-5-30-ghz/specifications.html': {
        'socket','integrated_graphics','cpu_id'},
    'https://www.intel.com/content/www/us/en/products/sku/245692/intel-core-ultra-7-processor-270k-plus-36m-cache-up-to-5-50-ghz/specifications.html': {
        'socket','integrated_graphics','cpu_id'},
    'https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/amd-ryzen-threadripper-pro-7000-wx-series/amd-ryzen-threadripper-pro-7975wx.html': {
        'socket','power_w','integrated_graphics','cpu_id'},
    'https://www.asus.com/motherboards-components/motherboards/prime/prime-x870-p/techspec/': {
        'socket','ram_type','ram_slots','form_factor','gpu_interfaces','storage_interfaces'},
    'https://www.asus.com/motherboards-components/motherboards/proart/proart-z890-creator-wifi/techspec/': {
        'socket','ram_type','ram_slots','form_factor','gpu_interfaces','storage_interfaces'},
    'https://www.asus.com/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z890-plus-wifi/techspec/': {
        'socket','ram_type','ram_slots','form_factor','gpu_interfaces','storage_interfaces'},
    'https://rog.asus.com/uk/motherboards/rog-crosshair/rog-crosshair-x870e-hero/spec/': {
        'socket','ram_type','ram_slots','form_factor','gpu_interfaces','storage_interfaces'},
    'https://www.asus.com/ie/motherboards-components/graphics-cards/dual/dual-rtx5050-o8g/techspec/': {
        'length_mm','recommended_psu_w','gpu_power_connectors','gpu_interface'},
    'https://www.apnx.com/product/c1/': {
        'supported_form_factors','max_gpu_length_mm','max_cooler_height_mm',
        'max_psu_length_mm','psu_form_factors','radiator_support','installed_fans'},
    'https://www.msi.com/Graphics-Card/GeForce-RTX-5090-32G-VENTUS-3X-OC/Specification': {
        'gpu_interface'},
    'https://www.pny.com/nvidia-rtx-6000-ada': {'gpu_interface'},
    'https://www.asus.com/motherboards-components/motherboards/workstation/pro-ws-wrx90e-sage-se/techspec/': {
        'socket','ram_type','ram_slots','form_factor','gpu_interfaces'},
    'https://www.fractal-design.com/products/cases/define-series/define-7-xl/define-7-xl-black-light-tg/': {
        'supported_form_factors'},
}


def resolve_primary_engineering(part):
    """Resolve certified fields from exact primary references, without publishing.

    Preserve human-reviewed conflicts for review. Primary specifications can
    supersede automated retailer extraction, with the discrepancy recorded.
    Missing fields stay missing; other planning references remain advisory.
    """
    facts=manufacturer_facts(part['role'],part['title'])
    fields=_VERIFIED_REFERENCE_FIELDS.get(facts.get('source_url'),set())
    values={key:facts[key] for key in fields if key in facts}
    current=dict(part.get('engineering') or {})
    if not values:return current
    conflicts={key:{'captured':current[key],'manufacturer':value}
        for key,value in values.items() if key in current and current[key]!=value}
    actor=current.get('reviewed_by','')
    if conflicts and current.get('reviewed') and actor and not actor.startswith('automation:'):
        return {**current,'reviewed':False,'reference_conflicts':conflicts}
    # Do not certify unrelated unreviewed draft fields along with primary facts.
    base=current if current.get('reviewed') is True else {}
    return {**base,**values,'reviewed':True,
        'engineering_reference':facts['source_url'],
        'manufacturer_verified_fields':sorted(values),
        'primary_source_resolutions':conflicts,
        'reviewed_by':'automation:exact-manufacturer-reference'}
