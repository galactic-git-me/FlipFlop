"""Gateway resource ownership checks; fake upstream, no live service changes."""
import asyncio,sys,time,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import server
import httpx
from starlette.requests import ClientDisconnect

class GatewayCapacity(unittest.IsolatedAsyncioTestCase):
 async def test_closing_unstarted_response_releases_generation_slot(self):
  forwarder=server.PriorityForwarder();await forwarder.start()
  await forwarder._client.aclose()
  forwarder._client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=b'{"done":true}')))
  forwarder.gpu_request_body=AsyncMock(side_effect=lambda body:body)
  try:
   for _ in range(server.GENERATION_CONCURRENCY):
    _,_,body=await asyncio.wait_for(forwarder.submit(priority=1,method='POST',path='/api/chat',query='',body=b'{}',headers={}),timeout=1)
    await body.aclose()
   self.assertEqual(forwarder._generation_slots._value,server.GENERATION_CONCURRENCY,'Abandoned response bodies leaked all inference slots')
  finally:await forwarder.stop()
 async def test_stream_completion_and_double_close_release_exactly_once(self):
  class Bytes(httpx.AsyncByteStream):
   async def __aiter__(self):yield b'one';yield b'two'
  release=unittest.mock.Mock()
  upstream=httpx.Response(200,stream=Bytes())
  body=server.ManagedBody(upstream,release)
  self.assertEqual(b''.join([chunk async for chunk in body]),b'onetwo')
  await body.aclose();release.assert_called_once();self.assertTrue(upstream.is_closed)

 async def test_client_disconnect_before_body_iteration_closes_owner(self):
  release=unittest.mock.Mock()
  body=server.ManagedBody(httpx.Response(200,content=b'body'),release)
  response=server.ManagedStreamingResponse(body)
  with self.assertRaises(ClientDisconnect):
   await response({'type':'http','asgi':{'spec_version':'2.4'}},AsyncMock(),AsyncMock(side_effect=OSError('client disconnected')))
  self.assertTrue(body.closed);release.assert_called_once()

 async def test_expired_queued_call_is_pruned_before_admission(self):
  forwarder=server.PriorityForwarder()
  with patch.object(server,'QUEUE_WAIT_SECONDS',0.01):
   with self.assertRaises(server.HTTPException) as error:
    await forwarder.submit(priority=1,method='POST',path='/api/chat',query='',body=b'{}',headers={})
  self.assertEqual(error.exception.status_code,504)
  forwarder.prune_cancelled();self.assertEqual(forwarder._queue.qsize(),0)
  await asyncio.wait_for(forwarder._queue.join(),timeout=0.1)

 async def test_upstream_timeout_returns_capacity(self):
  forwarder=server.PriorityForwarder();await forwarder.start()
  await forwarder._client.aclose()
  def fail(request):raise httpx.ReadTimeout('upstream stalled')
  forwarder._client=httpx.AsyncClient(transport=httpx.MockTransport(fail))
  forwarder.gpu_request_body=AsyncMock(side_effect=lambda body:body)
  try:
   with self.assertRaises(server.HTTPException) as error:
    await forwarder.submit(priority=1,method='POST',path='/api/chat',query='',body=b'{}',headers={})
   self.assertEqual(error.exception.status_code,502)
   self.assertEqual(forwarder._generation_slots._value,server.GENERATION_CONCURRENCY)
  finally:await forwarder.stop()

 async def test_stalled_close_cannot_hold_generation_slot(self):
  release=unittest.mock.Mock()
  response=httpx.Response(200,content=b'body')
  async def stalled_close():
   try:
    await asyncio.sleep(1)
   except asyncio.CancelledError:
    await asyncio.sleep(0.02)
  response.aclose=AsyncMock(side_effect=stalled_close)
  body=server.ManagedBody(response,release)
  with patch.object(server,'UPSTREAM_CLOSE_SECONDS',0.01):
   await asyncio.wait_for(body.aclose(),timeout=0.1)
  release.assert_called_once()
  await asyncio.sleep(0.03)

 async def test_full_queue_restart_requires_sustained_no_progress(self):
  forwarder=server.PriorityForwarder()
  loop=asyncio.get_running_loop()
  request=server.QueuedRequest(1,1,'POST','/api/chat','',b'{}',{},loop.create_future())
  with patch.object(server,'MAX_QUEUE',1),patch.object(server,'FULL_QUEUE_STALL_SECONDS',60):
   await forwarder._queue.put((1,1,request))
   self.assertFalse(forwarder.should_restart_stalled_queue(now=1000))
   forwarder._full_queue_since=900
   forwarder._last_progress_at=900
   self.assertTrue(forwarder.should_restart_stalled_queue(now=1000))
   forwarder.record_progress()
   self.assertFalse(forwarder.should_restart_stalled_queue(now=time.monotonic()))

 async def test_not_full_queue_never_triggers_restart(self):
  forwarder=server.PriorityForwarder()
  with patch.object(server,'MAX_QUEUE',1):
   self.assertFalse(forwarder.should_restart_stalled_queue())
   self.assertIsNone(forwarder._full_queue_since)

 async def test_supervisor_restarts_gateway_after_nonzero_exit(self):
  failed=unittest.mock.Mock(wait=unittest.mock.Mock(return_value=75))
  stopped=unittest.mock.Mock(wait=unittest.mock.Mock(return_value=0))
  with patch.object(server.subprocess,'Popen',side_effect=[failed,stopped]) as spawn,patch.object(server.time,'sleep') as sleep:
   server.supervise_gateway()
  self.assertEqual(spawn.call_count,2)
  sleep.assert_called_once_with(30)

if __name__=='__main__':unittest.main()
