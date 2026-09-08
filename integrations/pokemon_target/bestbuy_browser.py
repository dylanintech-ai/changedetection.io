"""Read Best Buy offers without mistaking store inventory for shippable stock."""
import argparse
import asyncio
import json
from pathlib import Path
import time
from playwright.async_api import async_playwright


def extract(product, expected, controls):
    result = dict(retailer='bestbuy', sku=expected['sku'], url=expected['url'],
                  observed_at=time.time(), status='unknown', shipping_available=False)
    if str(product.get('sku')) != expected['sku']:
        return dict(result, error='product_identity_mismatch')
    offers = product.get('offers', [])
    if isinstance(offers, dict):
        offers = [offers]
    offers = [o for o in offers if str(o.get('sku')) == expected['sku']
              and (o.get('seller') or {}).get('name') == 'Best Buy']
    if len(offers) != 1:
        return dict(result, error='first_party_offer_not_unique')
    offer = offers[0]
    result.update(seller='Best Buy', price=offer.get('price'), currency=offer.get('priceCurrency'),
                  evidence=json.dumps({'offer': offer, 'controls': controls}))
    relevant = [c for c in controls if expected['sku'] in c.get('testid', '')]
    if any(c['text'].strip().lower() in ('in store only', 'coming soon', 'pre-order', 'pre-order now') for c in relevant):
        return result
    if any(c['text'].strip().lower() == 'sold out' for c in relevant):
        result['status'] = 'out_of_stock'
        return result
    # Structured InStock alone is insufficient: live store-only offers also say it.
    shipping = any(str(method).rstrip('/').split('/')[-1] in ('DeliveryModeParcelService', 'SHIPPING')
                   for method in offer.get('availableDeliveryMethod', []))
    cart = any(c['text'].strip().lower() == 'add to cart' and c.get('disabled') is False for c in relevant)
    if shipping and cart and offer.get('availability', '').endswith('/InStock'):
        result.update(status='in_stock', shipping_available=True)
    return result


async def collect(page, expected):
    try:
        await page.goto(expected['url'], wait_until='domcontentloaded', timeout=45000)
        await page.locator('h1').wait_for(timeout=15000)
        documents = await page.locator('script[type="application/ld+json"]').all_text_contents()
        products = []
        for raw in documents:
            try:
                value = json.loads(raw)
                if isinstance(value, dict) and value.get('@type') == 'Product':
                    products.append(value)
            except ValueError:
                continue
        controls = await page.locator('button[data-testid]').evaluate_all(
            '(buttons)=>buttons.map(b=>({text:b.innerText,disabled:b.disabled,testid:b.dataset.testid}))')
        product = next((p for p in products if str(p.get('sku')) == expected['sku']), {})
        return extract(product, expected, controls)
    except Exception as error:
        return dict(retailer='bestbuy', sku=expected['sku'], url=expected['url'],
                    observed_at=time.time(), status='unknown', error=type(error).__name__)


async def main(args):
    products = [p for p in json.loads(args.catalog.read_text())['products'] if p['retailer'] == 'bestbuy']
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel='chrome', headless=False)
        page = await browser.new_page()
        observations = []
        try:
            for product in products:
                result = await collect(page, product)
                observations.append(result)
                print(json.dumps({k: v for k, v in result.items() if k != 'evidence'}), flush=True)
        finally:
            await browser.close()
        args.output.write_text(json.dumps(observations, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
