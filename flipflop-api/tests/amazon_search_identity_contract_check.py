"""Replay Amazon search layouts through the actual browser extraction script."""
import ast,asyncio,inspect
from playwright.async_api import async_playwright
from app.scrapers.amazon_scraper import _search_amazon_term
async def checks():
 tree=ast.parse(inspect.getsource(_search_amazon_term))
 script=next(node.args[0].value for node in ast.walk(tree) if isinstance(node,ast.Call)
             and isinstance(node.func,ast.Attribute) and node.func.attr=='evaluate'
             and node.args and isinstance(node.args[0],ast.Constant))
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  try:
   page=await browser.new_page()
   for headings in [
       '<h2>AMD</h2><a href="https://www.amazon.co.uk/dp/B012345678"><h2 aria-label="Ryzen 5 5600G processor"><span>Ryzen 5 5600G processor</span></h2></a>',
       '<h2><a href="https://www.amazon.co.uk/dp/B012345678"><span>AMD Ryzen 5 5600G processor</span></a></h2>'
   ]:
    await page.set_content('<div data-component-type="s-search-result">'+headings+'<span class="a-price-whole">100</span><span class="a-price-fraction">00</span></div>')
    rows=await page.evaluate(script)
    assert len(rows)==1 and '5600G' in rows[0]['title'], 'Brand heading replaced product identity'
    assert '/dp/B012345678' in rows[0]['href']
  finally:await browser.close()
 print('PASS: actual Amazon extraction on brand-first and legacy product headings')
if __name__=='__main__':asyncio.run(checks())
