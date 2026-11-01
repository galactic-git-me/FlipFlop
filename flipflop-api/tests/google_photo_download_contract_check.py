"""Regression checks for Google image downloads; no live provider calls."""
import asyncio
from unittest.mock import AsyncMock,patch
import httpx
from app.services import catalogue_image_search as service
async def main():
 loader=AsyncMock(side_effect=[httpx.ReadTimeout('original blocked'),b'valid-preview'])
 with patch.object(service,'load_remote_image',loader),patch.object(service,'save_catalogue_photo',return_value='https://local.test/saved.png'):
  result=await service.download_catalogue_photo('https://amd.test/original.png',thumbnail_url='https://preview.test/same-photo.jpg')
  assert result=='https://local.test/saved.png'
  assert loader.await_args_list[1].args[0]=='https://preview.test/same-photo.jpg'
 print('PASS: failed original falls back to the selected result preview')
 from fastapi import HTTPException
 loader=AsyncMock(side_effect=httpx.ReadTimeout('blocked'))
 with patch.object(service,'load_remote_image',loader):
  try: await service.download_catalogue_photo('https://amd.test/original.png',thumbnail_url='https://preview.test/same-photo.jpg')
  except HTTPException as exc: assert exc.status_code==422 and 'preview' in exc.detail
  else: raise AssertionError('Download failure was hidden')
 print('PASS: both sources failing returns an explicit actionable error')
if __name__=='__main__':asyncio.run(main())
