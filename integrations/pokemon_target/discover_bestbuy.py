"""Discover candidates; verify page counts and keep them separate from alert watches."""
import argparse,asyncio,json,re,time
from pathlib import Path
from playwright.async_api import async_playwright
async def main(output):
 results={}; pages=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(channel='chrome',headless=False)
  page=await browser.new_page()
  url='https://www.bestbuy.com/site/searchpage.jsp?id=pcat17071&qp=bbyonly_facet%3DSold+%26+shipped+by%7EBest+Buy&st=pokemon+trading+card'
  try:
   for n in range(10):
    await page.goto(url,wait_until='domcontentloaded',timeout=45000)
    await page.locator('a[href*="/product/"]').first.wait_for(timeout=20000)
    body=await page.locator('body').inner_text()
    summary=re.search(r'(\d+)[–-](\d+) of ([\d,]+) items',body)
    expected=int(summary[2])-int(summary[1])+1 if summary else None
    all_links={}
    for _ in range(24):
     links=await page.locator('a[href*="/product/"]').evaluate_all('(els)=>els.map(e=>({url:e.href,title:e.innerText}))')
     for item in links:
      if item['title'] and re.fullmatch(r'https://www\.bestbuy\.com/product/[^?#]+/sku/\d+',item['url']):
       all_links[item['url']]=item
     if expected and len(all_links)>=expected:break
     await page.mouse.wheel(0,700)
     await page.wait_for_timeout(1200)
    links=list(all_links.values())
    count=0
    for item in links:
     m=re.fullmatch(r'https://www\.bestbuy\.com/product/[^?#]+/sku/(\d+)',item['url'])
     if not m or not item['title']:continue
     count+=1
     if item['title'].startswith('Pokémon -'):
      results[m[1]]=dict(retailer='bestbuy',sku=m[1],title=item['title'],url=item['url'],release_date=None,release_source=None,msrp=None,msrp_source=None)
    pages.append({'url':page.url,'expected':expected,'product_links':count,'complete':expected is not None and count==expected})
    output.write_text(json.dumps({'coverage':'Discovery candidates only; release dates, MSRP and live seller/stock require verification. Not a production watchlist.','observed_at':time.time(),'pages':pages,'products':list(results.values())},indent=2))
    print(json.dumps({'page':n+1,'page_products':count,'pokemon_candidates':len(results)}),flush=True)
    next_link=page.get_by_role('link',name='Next page',exact=True)
    if await next_link.count()!=1:break
    href=await next_link.get_attribute('href')
    if not href:break
    from urllib.parse import urljoin
    url=urljoin(page.url,href)
    await page.wait_for_timeout(3000)
  except Exception as e: print('stopped:',type(e).__name__,flush=True)
  finally:await browser.close()
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 asyncio.run(main(parser.parse_args().output))
