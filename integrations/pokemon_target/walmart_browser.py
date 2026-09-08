"""Collect Walmart's current product offer using ordinary visible Chrome."""
import argparse
import asyncio
import json
import importlib.util
from pathlib import Path
import time
from urllib.parse import urlencode
from playwright.async_api import async_playwright
from browser_bridge import ingest
from transitions import StockState


def extract(product, expected):
    observation = dict(retailer='walmart', sku=expected['sku'], url=expected['url'],
                       observed_at=time.time(), status='unknown', shipping_available=False)
    if str(product.get('usItemId')) != expected['sku']:
        return dict(observation, error='product_identity_mismatch')
    shipping = next((o for o in product.get('fulfillmentOptions', [])
                     if o.get('type') == 'SHIPPING'), {})
    price = (product.get('priceInfo') or {}).get('currentPrice') or {}
    observation.update(seller='Walmart' if product.get('sellerName') == 'Walmart.com'
                       and product.get('sellerType') == 'INTERNAL' else product.get('sellerName'),
                       price=price.get('price'), currency=price.get('currencyUnit'),
                       location=shipping.get('locationText'),
                       evidence=json.dumps({k: product.get(k) for k in
                                            ('usItemId', 'sellerName', 'sellerType', 'availabilityStatus', 'preOrder')}))
    status = shipping.get('availabilityStatus')
    if (product.get('preOrder') or {}).get('isPreOrder') is True:
        return observation
    if shipping.get('restricted') is True or shipping.get('viewOnly') is True:
        return observation
    if status == 'IN_STOCK' and product.get('availabilityStatus') == 'IN_STOCK':
        observation.update(status='in_stock', shipping_available=True)
    elif status == 'OUT_OF_STOCK':
        observation['status'] = 'out_of_stock'
    observation['evidence'] += '\nShipping: ' + json.dumps(shipping)
    return observation


async def collect(page, product):
    try:
        query = urlencode({'filters': json.dumps([{'intent': 'retailer', 'values': ['Walmart']}])})
        await page.goto(product['url'] + '?' + query, wait_until='domcontentloaded', timeout=45000)
        if 'robot or human' in (await page.title()).lower():
            raise ValueError('retailer_challenge')
        raw = await page.locator('script#__NEXT_DATA__').text_content(timeout=15000)
        data = json.loads(raw)['props']['pageProps']['initialData']['data']['product']
        return extract(data, product)
    except Exception as error:
        # Never expose response payloads, cookies or URL query strings in errors.
        return dict(retailer='walmart', sku=product['sku'], url=product['url'],
                    observed_at=time.time(), status='unknown',
                    error='retailer_challenge' if str(error) == 'retailer_challenge' else type(error).__name__)


async def main(args):
    products = [p for p in json.loads(args.catalog.read_text())['products'] if p['retailer'] == 'walmart']
    state = email = None
    if args.state:
        spec = importlib.util.spec_from_file_location('email_outbox', args.email_module)
        email = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(email)
        state = StockState(args.state, namespace='retail')
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel='chrome', headless=False)
        page = await browser.new_page()
        try:
            for cycle in range(args.cycles):
                observations = []
                for product in products:
                    observation = await collect(page, product)
                    observations.append(observation)
                    print(json.dumps({k: v for k, v in observation.items() if k != 'evidence'}), flush=True)
                    if observation.get('error') == 'retailer_challenge':
                        break
                temporary = args.output.with_suffix('.tmp')
                temporary.write_text(json.dumps(observations, indent=2))
                temporary.replace(args.output)
                if state:
                    result = ingest(observations, {p['retailer'] + ':' + p['sku']: p for p in products},
                                    state, email.enqueue, email.cancel_event)
                    print(json.dumps({'pipeline': result}), flush=True)
                if cycle + 1 < args.cycles:
                    delay = max(args.interval, 600) if any(o.get('error') == 'retailer_challenge' for o in observations) else args.interval
                    print(json.dumps({'next_check_seconds': delay}), flush=True)
                    await asyncio.sleep(delay)
        finally:
            await browser.close()
            if state:
                state.db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--interval', type=float, default=60)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--email-module', type=Path)
    args = parser.parse_args()
    if bool(args.state) != bool(args.email_module):
        parser.error('--state and --email-module must be supplied together')
    if args.cycles < 1 or args.interval < 15:
        parser.error('cycles must be positive and interval must be at least 15 seconds')
    asyncio.run(main(args))
