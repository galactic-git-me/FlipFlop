import json
import struct
import pytest
from app.services.glb_textures import require_embedded_colour_texture


def glb(embedded):
    document={'asset':{'version':'2.0'},'meshes':[{'primitives':[{'material':0,'attributes':{'TEXCOORD_0':0}}]}],
        'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}}}],
        'textures':[{'extensions':{'EXT_texture_webp':{'source':0}}}],
        'images':[{'bufferView':0,'mimeType':'image/webp'}] if embedded else [{'uri':'external.webp'}],
        'bufferViews':[{'buffer':0,'byteLength':4}], 'buffers':[{'byteLength':4}]}
    data=json.dumps(document).encode()
    data+=b' '*((-len(data))%4)
    return struct.pack('<III',0x46546C67,2,28+len(data))+struct.pack('<II',len(data),0x4E4F534A)+data+struct.pack('<II',0,0x004E4942)


def test_embedded_webp_colour_texture_is_accepted_for_web_models():
    require_embedded_colour_texture(glb(True))


def test_external_webp_texture_is_rejected():
    with pytest.raises(ValueError,match='no embedded colour texture'):
        require_embedded_colour_texture(glb(False))
