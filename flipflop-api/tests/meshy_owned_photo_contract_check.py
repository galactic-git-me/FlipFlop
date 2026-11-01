"""Focused provider-input contract: no Meshy requests or paid tasks."""
import asyncio,base64,json
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
import httpx
from pathlib import Path
from app.services.model_reference_images import meshy_reference_inputs
async def main():
 filename='b12cbfde0d2dddb53cbeb6c3c7b7a4a607e0eb866352ce144da9eff3b19b2166.jpg'
 path=Path('data/uploads/catalogue-photos')/filename
 url='http://127.0.0.1:4311/api/uploads/catalogue-photos/'+filename
 result=await meshy_reference_inputs([url])
 assert result[0].startswith('data:image/jpeg;base64,')
 assert base64.b64decode(result[0].split(',',1)[1])==path.read_bytes()
 assert await meshy_reference_inputs(['https://example.test/public.jpg'])==['https://example.test/public.jpg']
 for unsafe in ['http://127.0.0.1:4311/api/uploads/catalogue-photos/missing.jpg','http://localhost/private.jpg','http://127.0.0.1:4311/api/uploads/../../.env.local']:
  try:await meshy_reference_inputs([unsafe])
  except ValueError:pass
  else:raise AssertionError('Invalid private source accepted')
 from app.services import meshy_generation as meshy
 original_client=httpx.AsyncClient
 requests=[]
 def respond(request):
  requests.append(request)
  payload=json.loads(request.content)
  assert payload['image_url']==result[0]==payload['texture_image_url']
  assert payload['should_texture'] and payload['enable_pbr'] and payload['target_formats']==['glb']
  return httpx.Response(200,json={'result':'fixture-existing-task'})
 completed=meshy.MeshyGenerationResult('fixture-existing-task','SUCCEEDED','https://example.test/model.glb',None,None)
 with patch.object(meshy,'get_settings',return_value=SimpleNamespace(meshy_api_key='fixture-key')), patch.object(meshy.httpx,'AsyncClient',side_effect=lambda **kw: original_client(transport=httpx.MockTransport(respond),**kw)), patch.object(meshy,'poll_multi_image_asset',AsyncMock(return_value=completed)):
  generated=await meshy.generate_multi_image_asset([url])
  assert generated.reference_image_urls==[url] and len(requests)==1
 print('PASS: Meshy payload uses image bytes for geometry and texture, preserving original provenance URLs')
 print('PASS: actual approved Corsair photo sent as exact bytes, public URLs preserved, inaccessible/private paths rejected')
asyncio.run(main())
