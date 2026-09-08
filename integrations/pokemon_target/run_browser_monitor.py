"""Run browser observations through durable transition and email-queue processing."""
import argparse
import asyncio
import fcntl
import importlib.util
import json
from pathlib import Path
import time
from playwright.async_api import async_playwright
from bestbuy_browser import collect as bestbuy_collect
from walmart_browser import collect as walmart_collect
from browser_bridge import ingest
from transitions import StockState


def scheduled(catalog, latest, limit=2):
    """Oldest attempted products first; errors cannot starve later SKUs."""
    counts = {}
    for key in sorted(catalog, key=lambda k: latest.get(k, {}).get('observed_at', 0)):
        retailer = catalog[key]['retailer']
        if counts.get(retailer, 0) < limit:
            counts[retailer] = counts.get(retailer, 0) + 1
            yield key, catalog[key]


async def run(args):
    # A second process must not race the same transition/outbox processing.
    lock = args.state.with_suffix('.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    spec = importlib.util.spec_from_file_location('email_outbox', args.email_module)
    email = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(email)
    state = StockState(args.state, namespace='retail')
    collectors = {'bestbuy': bestbuy_collect, 'walmart': walmart_collect}
    cooldown = {}
    latest = {}
    if args.health.exists():
        previous = json.loads(args.health.read_text())
        latest = previous.get('latest_observations', {})
        cooldown = {name: until for name, until in previous.get('cooldown_until', {}).items()
                    if name in collectors and isinstance(until, (int, float)) and until > time.time()}
    cycle = 0
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel='chrome', headless=False)
            page = await browser.new_page()
            try:
                while args.cycles == 0 or cycle < args.cycles:
                    started = time.time()
                    catalog = json.loads(args.catalog.read_text())['products']
                    catalog = {p['retailer'] + ':' + p['sku']: p for p in catalog
                               if p['retailer'] in args.retailers}
                    outcomes = []
                    for key, product in scheduled(catalog, latest):
                        retailer = product['retailer']
                        if cooldown.get(retailer, 0) > time.time():
                            continue
                        if outcomes:
                            await asyncio.sleep(5)
                        observation = await collectors[retailer](page, product)
                        outcome = ingest([observation], catalog, state, email.enqueue, email.cancel_event)
                        record = {k: v for k, v in observation.items() if k != 'evidence'}
                        record['pipeline'] = outcome[key]
                        outcomes.append(record)
                        latest[key] = record
                        print(json.dumps(record), flush=True)
                        if observation.get('error'):
                            cooldown[retailer] = time.time() + 600
                    cycle += 1
                    health = {'cycle': cycle, 'started_at': started, 'completed_at': time.time(),
                              'catalog_count': len(catalog), 'catalog_keys': list(catalog),
                              'latest_observations': latest, 'observations': outcomes,
                              'cooldown_until': cooldown,
                              'note': 'Queues emails for the standalone SMTP worker. At most two products per retailer per cycle. Catalog may be incomplete.'}
                    temporary = args.health.with_suffix('.tmp')
                    temporary.write_text(json.dumps(health, indent=2))
                    temporary.replace(args.health)
                    print(json.dumps({'cycle_completed': cycle, 'observations': len(outcomes)}), flush=True)
                    if args.cycles == 0 or cycle < args.cycles:
                        await asyncio.sleep(max(1, args.interval - (time.time() - started)))
            finally:
                await browser.close()
    finally:
        state.db.close()
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('catalog', 'state', 'email-module', 'health'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--retailers', nargs='+', choices=['bestbuy', 'walmart'], default=['bestbuy'])
    parser.add_argument('--cycles', type=int, default=1, help='0 runs continuously')
    parser.add_argument('--interval', type=float, default=60)
    args = parser.parse_args()
    if args.cycles < 0 or args.interval < 20:
        parser.error('cycles must be nonnegative and interval at least 20 seconds')
    asyncio.run(run(args))
