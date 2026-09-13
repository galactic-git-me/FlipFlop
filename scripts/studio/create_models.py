"""Original lightweight illustrative PC parts, authored in Blender.
Run: blender --background --python scripts/studio/create_models.py -- OUTPUT_DIR
These are category illustrations, never measurements or product replicas.
World units are metres; export is glTF Y-up. Origins are component centres.
"""
import bpy, math, sys
from pathlib import Path

OUT = Path(sys.argv[sys.argv.index('--') + 1])
OUT.mkdir(parents=True, exist_ok=True)

def material(name, rgb, metallic=0.5, roughness=0.35):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return m

black = material('Graphite', (.018, .025, .035))
silver = material('Machined aluminium', (.38, .43, .48), .85)
board = material('PCB', (.015, .033, .037), .2)
gold = material('Contacts', (.6, .34, .08), .8)

def box(name, size, pos=(0,0,0), mat=black):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(pos[0], -pos[2], pos[1]))
    o = bpy.context.object
    o.name = name
    o.dimensions = (size[0], size[2], size[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if name in ('Chassis rail', 'Deck', 'PSU shroud', 'Graphics card shroud', 'PSU housing', 'Heat spreader'):
        bevel = o.modifiers.new('Edge highlights', 'BEVEL')
        bevel.width = min(size) * .08
        bevel.segments = 2
        bpy.ops.object.modifier_apply(modifier=bevel.name)
    return o

def export(category):
    # Join by material: bounded draw calls; no textures, lights or cameras.
    for mat in (black, silver, board, gold):
        bpy.ops.object.select_all(action='DESELECT')
        items = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.active_material == mat]
        if items:
            for o in items: o.select_set(True)
            bpy.context.view_layer.objects.active = items[0]
            bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(OUT / (category + '.glb')), export_format='GLB', use_selection=False, export_yup=True, export_materials='EXPORT', export_meshopt_compression_enable=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
box('PCB', (.244,.305,.006), mat=board)
box('CPU socket', (.06,.065,.01), (-.025,.065,.01))
for x in (.054,.069,.084,.099): box('DIMM socket', (.008,.135,.012), (x,.06,.012))
for y in (-.09,-.045): box('PCIe socket', (.125,.008,.014), (-.02,y,.013))
for i in range(9):
    box('VRM heatsink', (.009,.07,.025), (-.108+i*.009,.111,.023), silver)
for x,y in [(-.06,-.015),(.082,-.10),(-.08,-.12)]:
    box('Controller', (.025,.025,.006), (x,y,.008))
box('IO shield', (.025,.145,.03), (-.113,.038,.018), silver)
export('motherboard')
box('CPU substrate', (.043,.043,.003), mat=board)
box('Heat spreader', (.039,.039,.005), (0,0,.004), silver)
export('cpu')
box('Graphics card shroud', (.285,.052,.115))
box('Backplate', (.285,.003,.115), (0,.028,0), silver)
for i in range(38): box('Heatsink fin', (.002,.04,.105), (-.133+i*.007,0,0), silver)
box('PCI bracket', (.004,.06,.12), (-.145,0,0), silver)
export('gpu')
for x in (-.009,.009):
    box('Memory PCB', (.003,.135,.033), (x,0,0), board)
    box('Heat spreader', (.006,.128,.028), (x,0,.002))
    box('Contacts', (.004,.125,.004), (x,0,-.016), gold)
export('ram')
box('M2 PCB', (.08,.022,.002), mat=board)
for x in (-.025,0,.025): box('NAND', (.019,.017,.003), (x,0,.003))
box('Contacts', (.004,.022,.002), (.042,0,0), gold)
export('storage')
box('Cooler base', (.06,.06,.005), mat=silver)
for i in range(26): box('Fin', (.12,.002,.11), (0,-.059+i*.0045,.058), silver)
for x in (-.035,-.012,.012,.035): box('Heatpipe', (.005,.12,.005), (x,0,.035), gold)
export('cooling')
box('PSU housing', (.15,.086,.14))
for i in range(14): box('Vent', (.003,.065,.002), (-.06+i*.009,0,.071), silver)
box('Power socket', (.025,.025,.005), (-.04,-.015,-.072), silver)
export('psu')
for y in (-.112,0,.112):
    for z in (-.05,.05): box('Fan frame', (.012,.105,.007), (0,y,z))
    for dy in (-.05,.05): box('Fan frame', (.012,.007,.105), (0,y+dy,0))
export('fan')
for x in (-.205,.205):
    for z in (-.115,.115): box('Chassis rail', (.012,.46,.012), (x,0,z))
for y in (-.23,.23):
    box('Deck', (.422,.012,.24), (0,y,0))
box('Rear tray', (.42,.44,.006), (0,0,-.119))
box('PSU shroud', (.418,.075,.236), (0,-.187,0))
for z in (-.08,.08):
    for x in (-.15,.15): box('Foot', (.045,.015,.035), (x,-.246,z))
export('case')
print('Studio originals:', sum(p.stat().st_size for p in OUT.glob('*.glb')), 'bytes')
