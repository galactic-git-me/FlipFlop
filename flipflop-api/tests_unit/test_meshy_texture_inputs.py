"""Isolated Meshy request checks. All HTTP and provider jobs are simulated."""
import sys,io,json,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from PIL import Image
from app.services import meshy_generation as service

class TextureInputChecks(unittest.IsolatedAsyncioTestCase):
    async def generate(self,urls,edge=500):
        body=io.BytesIO();Image.new("RGB",(edge,edge),"brown").save(body,format="JPEG")
        posts=[]
        async def handle(request):
            if request.url.host=="m.media-amazon.com":return httpx.Response(200,content=body.getvalue())
            if request.method=="POST":
                posts.append(json.loads(request.content));return httpx.Response(200,json={"result":"fake-task"})
            return httpx.Response(200,json={"status":"SUCCEEDED","progress":100,"model_urls":{"glb":"https://assets.example/textured.glb"}})
        client=httpx.AsyncClient
        with patch.object(service,"get_settings",return_value=SimpleNamespace(meshy_api_key="fake-test-key")),patch.object(service.httpx,"AsyncClient",side_effect=lambda **kwargs:client(transport=httpx.MockTransport(handle),**kwargs)),patch.object(service.asyncio,"sleep",new=AsyncMock()):
            result=await service.generate_multi_image_asset(urls)
        return result,posts
    async def test_selected_amazon_thumbnail_uses_original_size_for_geometry_and_texture(self):
        result,posts=await self.generate(["https://m.media-amazon.com/images/I/41RmXmwB43L._AC_US40_.jpg"])
        self.assertEqual(result.status,"SUCCEEDED")
        self.assertEqual(posts[0]["image_url"],"https://m.media-amazon.com/images/I/41RmXmwB43L.jpg")
        self.assertEqual(posts[0]["texture_image_url"],posts[0]["image_url"])
        self.assertTrue(posts[0]["should_texture"]);self.assertTrue(posts[0]["enable_pbr"])
    async def test_tiny_original_is_rejected_before_a_paid_job(self):
        result,posts=await self.generate(["https://m.media-amazon.com/images/I/41RmXmwB43L._AC_US40_.jpg"],40)
        self.assertEqual(result.status,"SOURCE_IMAGES_INVALID")
        self.assertEqual(posts,[])
    async def test_multiple_views_preserve_owner_order_and_use_all_views_for_textures(self):
        urls=["https://m.media-amazon.com/images/I/FRONT._AC_US40_.jpg","https://m.media-amazon.com/images/I/BACK._AC_US40_.jpg"]
        result,posts=await self.generate(urls)
        self.assertEqual(posts[0]["image_urls"],["https://m.media-amazon.com/images/I/FRONT.jpg","https://m.media-amazon.com/images/I/BACK.jpg"])
        self.assertEqual(posts[0]["texture_image_urls"],posts[0]["image_urls"])
        self.assertEqual(len(urls),2)

class TextureArtifactChecks(unittest.TestCase):
    def glb(self,doc):
        import struct
        raw=json.dumps(doc).encode();raw+=b" "*((-len(raw))%4)
        return struct.pack("<IIIII",0x46546C67,2,20+len(raw),len(raw),0x4E4F534A)+raw
    def test_geometry_without_a_colour_map_is_rejected(self):
        from app.services.glb_textures import require_embedded_colour_texture
        with self.assertRaisesRegex(ValueError,"colour texture"):
            require_embedded_colour_texture(self.glb({"materials":[{}],"meshes":[{"primitives":[{"material":0,"attributes":{"TEXCOORD_0":0}}]}]}))
    def test_external_texture_file_is_not_mistaken_for_an_embedded_texture(self):
        from app.services.glb_textures import require_embedded_colour_texture
        doc={"materials":[{"pbrMetallicRoughness":{"baseColorTexture":{"index":0}}}],"textures":[{"source":0}],"images":[{"uri":"missing-texture.jpg"}],"meshes":[{"primitives":[{"material":0,"attributes":{"TEXCOORD_0":0}}]}]}
        with self.assertRaisesRegex(ValueError,"colour texture"):
            require_embedded_colour_texture(self.glb(doc))
    def test_known_cdn_renditions_keep_the_same_photo_identity(self):
        from app.services.model_reference_images import original_image_url
        self.assertEqual(original_image_url("https://m.media-amazon.com/images/I/41A._AC_US40_.jpg"),"https://m.media-amazon.com/images/I/41A.jpg")
        self.assertEqual(original_image_url("https://m.media-amazon.com.attacker.invalid/images/I/41A._AC_US40_.jpg"),"https://m.media-amazon.com.attacker.invalid/images/I/41A._AC_US40_.jpg")
        self.assertEqual(original_image_url("https://i.ebayimg.com/images/g/key/s-l64.jpg"),"https://i.ebayimg.com/images/g/key/s-l1600.jpg")

if __name__=="__main__":unittest.main()

