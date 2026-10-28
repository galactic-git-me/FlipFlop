"""Require a self-contained base-colour map before accepting generated GLBs."""
import json
import struct


def require_embedded_colour_texture(data: bytes) -> None:
    try:
        magic, version, total = struct.unpack_from("<III", data)
        if magic != 0x46546C67 or version != 2 or total != len(data):
            raise ValueError("Invalid GLB header")
        length, kind = struct.unpack_from("<II", data, 12)
        if kind != 0x4E4F534A or length > len(data)-20:
            raise ValueError("Invalid GLB JSON chunk")
        document = json.loads(data[20:20+length])
        textures = document.get("textures") or []
        images = document.get("images") or []
        views = document.get("bufferViews") or []
        materials = document.get("materials") or []
        for mesh in document.get("meshes",[]):
            for primitive in mesh.get("primitives",[]):
                if "material" not in primitive:
                    continue
                material = materials[primitive["material"]]
                texture = material.get("pbrMetallicRoughness",{}).get("baseColorTexture")
                if not texture or f"TEXCOORD_{texture.get('texCoord',0)}" not in primitive.get("attributes",{}):
                    continue
                definition = textures[texture["index"]]
                image_index = definition.get('source')
                if image_index is None:
                    image_index = (definition.get('extensions') or {}).get('EXT_texture_webp',{}).get('source')
                if image_index is None:
                    continue
                image = images[image_index]
                if image.get("uri", "").startswith("data:image/"):
                    return
                if "bufferView" in image and views[image["bufferView"]].get("byteLength",0) > 0:
                    return
    except (ValueError,TypeError,KeyError,IndexError,struct.error) as error:
        raise ValueError("Generated GLB has invalid or missing embedded colour textures") from error
    raise ValueError("Generated GLB has no embedded colour texture on its rendered geometry")
