"""Deterministic capacity handling, with no Meshy calls."""
import asyncio
from unittest.mock import AsyncMock,patch
import httpx
from app.services import meshy_generation as service
async def main():
 pending=httpx.Response(429,json={'message':'NoMorePendingTasks'})
 accepted=httpx.Response(200,json={'result':'existing-fixture-task'})
 client=AsyncMock();client.post.side_effect=[pending,accepted]
 callback=AsyncMock()
 with patch.object(service.asyncio,'sleep',AsyncMock()):
  result=await service._submit_image_with_capacity_wait(client,'https://example.test',{},callback)
 assert result is accepted and client.post.await_count==2
 assert callback.await_args.args[1]=='QUEUED'
 for code in (400,403,500):
  client=AsyncMock();client.post.return_value=httpx.Response(code,json={'message':'do not retry'})
  await service._submit_image_with_capacity_wait(client,'https://example.test',{},callback)
  assert client.post.await_count==1
 client=AsyncMock();client.post.side_effect=httpx.ReadTimeout('uncertain acceptance')
 try:await service._submit_image_with_capacity_wait(client,'https://example.test',{},callback)
 except httpx.ReadTimeout:pass
 else:raise AssertionError('Ambiguous submission retried')
 assert client.post.await_count==1
 print('PASS: full provider queue waits; other rejections and ambiguous timeouts are not resubmitted')
asyncio.run(main())
