"""Read changedetection watch results and queue verified Target transitions."""
import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
import importlib.util
import json
from pathlib import Path
import re
import time
from catalog import cutoff
from transitions import StockState


def normalize(watch, product, now):
    url = watch.get('url', '')
    match = re.fullmatch(r'https://www\.target\.com/p/(?:[^?#]*/)?-/A-(\d+)', url)
    if not match or match[1] != product['tcin']:
        return 'unknown', False
    checked = watch.get('last_checked') or 0
    if watch.get('last_error') or not 0 <= now - checked <= 180:
        return 'unknown', False
    restock = watch.get('restock') or {}
    available = restock.get('in_stock')
    if type(available) is not bool:
        return 'unknown', False
    status = 'in_stock' if available else 'out_of_stock'
    try:
        price = Decimal(str(restock.get('price')))
        msrp = Decimal(str(product.get('msrp')))
        released = date.fromisoformat(product['street_date'])
        today = date.fromtimestamp(now)
        allowed = (price.is_finite() and msrp.is_finite() and 0 < price <= msrp
                   and restock.get('currency') == 'USD' and product.get('seller_verified') is True
                   and bool(product.get('msrp_source')) and cutoff(today) <= released <= today)
    except (InvalidOperation, ValueError, TypeError, KeyError):
        allowed = False
    return status, allowed


def run(datastore, catalog, state, enqueue, now=None, cancel=None):
    now = time.time() if now is None else now
    outcomes = {}
    for path in datastore.glob('*/watch.json'):
        try:
            watch = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        match = re.search(r'/A-(\d+)(?:$|[?#])', watch.get('url', ''))
        if not match or match[1] not in catalog:
            continue
        product = catalog[match[1]]
        status, eligible = normalize(watch, product, now)
        payload = dict(product, current_price=(watch.get('restock') or {}).get('price'))
        outcomes[match[1]] = state.observe(match[1], status, payload, watch.get('last_checked') or now, eligible)
        if status == 'out_of_stock' and cancel and outcomes[match[1]] != 'stale_observation':
            for (identity,) in state.db.execute("SELECT id FROM events WHERE sku=? AND status='queued'", (match[1],)).fetchall():
                cancel(identity)
                with state.db:
                    state.db.execute("UPDATE events SET status='cancelled' WHERE id=?", (identity,))
    for identity, payload in state.pending(now):
        product = json.loads(payload)
        alert = {'title': f"Target restock: {product['title']}", 'url': product['url'],
                 'message': f"{product['title']}\nTarget: ${product['current_price']} (MSRP ${product['msrp']})\n{product['url']}\nDetected out of stock → in stock. Availability may change before checkout.",
                 'event_id': identity}
        expires = state.db.execute('SELECT expires FROM events WHERE id=?', (identity,)).fetchone()[0]
        alert['expires_at'] = expires
        if enqueue(alert) == 'queued_for_email':
            with state.db:
                state.db.execute("UPDATE events SET status='queued' WHERE id=?", (identity,))
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datastore', required=True, type=Path)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--email-module', required=True, type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('email_outbox', args.email_module)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    products = json.loads(args.catalog.read_text())['products']
    state = StockState(args.state)
    print(json.dumps(run(args.datastore, {p['tcin']: p for p in products}, state, module.enqueue, cancel=module.cancel_event)))


if __name__ == '__main__':
    main()
