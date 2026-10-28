"""Offline check: four open streams, a queued fifth, priority, and stream isolation."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys

import httpx

spec = importlib.util.spec_from_file_location('parallel_gateway_check', Path(__file__).with_name('server.py'))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

async def main():
    m.GENERATION_CONCURRENCY = 4
    active = 0
    maximum = 0
    opened = []

    class Stream(httpx.AsyncByteStream):
        def __init__(self, value):
            self.value = value
        async def __aiter__(self):
            yield self.value
        async def aclose(self):
            nonlocal active
            active -= 1

    async def respond(request):
        nonlocal active, maximum
        value = json.loads(request.content)['id']
        opened.append(value)
        active += 1
        maximum = max(maximum, active)
        return httpx.Response(200, stream=Stream(str(value).encode()))

    forwarder = m.PriorityForwarder()
    async def passthrough(body):
        return body
    forwarder.gpu_request_body = passthrough  # No provider or inference calls.
    await forwarder.start()
    await forwarder._client.aclose()
    forwarder._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    def submit(value, priority=1):
        return asyncio.create_task(forwarder.submit(priority=priority,method='POST',
            path='/api/generate',query='',body=json.dumps({'id':value}).encode(),headers={}))
    async def consume(result):
        return b''.join([chunk async for chunk in result[2]])
    try:
        initial = await asyncio.wait_for(asyncio.gather(*(submit(i) for i in range(4))),2)
        assert active == 4
        waiting_dev = submit(4)
        waiting_production = submit(5, priority=0)
        await asyncio.sleep(0.02)
        assert not waiting_dev.done() and not waiting_production.done() and len(opened) == 4
        assert await consume(initial[0]) == b'0'
        production = await asyncio.wait_for(waiting_production,2)
        assert opened[-1] == 5 and not waiting_dev.done()
        assert await consume(initial[1]) == b'1'  # Must retain its own upstream response.
        development = await asyncio.wait_for(waiting_dev,2)
        assert await consume(initial[2]) == b'2'
        assert await consume(initial[3]) == b'3'
        assert await consume(production) == b'5'
        assert await consume(development) == b'4'
        assert maximum == 4 and active == 0
        await asyncio.wait_for(forwarder._queue.join(),2)
    finally:
        await forwarder.stop()
    print('PASS: four simultaneous streams, fifth waits, production priority retained, responses isolated, slots released')

asyncio.run(main())
