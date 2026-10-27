"""Deterministic GPU-only guard check; no Ollama inference or restart."""
import asyncio,importlib.util,json,sys
from pathlib import Path
import httpx
from fastapi import HTTPException
path=Path(__file__).with_name('server.py')
spec=importlib.util.spec_from_file_location('gpu_gateway_contract',path)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
async def main():
 for vram,allowed in [(0,False),(50,False),(100,True)]:
  calls=[]
  def respond(request):
   calls.append(request)
   if request.url.path=='/api/generate':
    payload=json.loads(request.content)
    assert 'prompt' not in payload and 'messages' not in payload
    assert payload['options']['num_gpu']==999
    return httpx.Response(200,json={'done':True})
   return httpx.Response(200,json={'models':[{'name':'fixture:latest','size':100,'size_vram':vram}]})
  f=m.PriorityForwarder()
  async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
   f._client=client
   try:
    body=await f.gpu_request_body(json.dumps({'model':'fixture','messages':[{'role':'user','content':'private prompt'}],'options':{'num_gpu':0}}).encode())
    assert allowed and json.loads(body)['options']['num_gpu']==999
   except HTTPException as e:assert not allowed and e.status_code==503
  assert len(calls)==2
 print('PASS: CPU and partial offload blocked before prompt evaluation; full GPU allowed; forced-CPU option overridden')
asyncio.run(main())
