"""Ingest fresh, product-page browser observations; never infer stock from search snippets.

The browser collector supplies JSON observations. Catalog metadata is reviewed separately.
This adapter does not itself navigate browsers or bypass retailer access controls.
"""
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

RETAILERS = {
    'bestbuy': ('Best Buy', r'https://www\.bestbuy\.com/product/[^?#]+/sku/(\d+)'),
    'walmart': ('Walmart', r'https://www\.walmart\.com/ip/(?:[^/?#]+/)?(\d+)'),
}


def normalize(observation, product, now):
    retailer = product.get('retailer')
    if retailer not in RETAILERS:
        return 'unknown', False
    seller, pattern = RETAILERS[retailer]
    match = re.fullmatch(pattern, observation.get('url', ''))
    checked = observation.get('observed_at', 0)
    if (not match or match[1] != product.get('sku')
            or observation.get('url') != product.get('url')
            or not isinstance(checked, (int, float)) or not 0 <= now - checked <= 180
            or observation.get('error') or not observation.get('evidence')
            or observation.get('seller') != seller):
        return 'unknown', False
    # Store-only, preorders, unavailable delivery locations and ambiguous controls
    # cannot establish an online stock transition.
    status = observation.get('status', 'unknown')
    if status not in ('in_stock', 'out_of_stock'):
        return 'unknown', False
    if status == 'in_stock' and observation.get('shipping_available') is not True:
        return 'unknown', False
    try:
        price = Decimal(str(observation.get('price')))
        msrp = Decimal(str(product.get('msrp')))
        released = date.fromisoformat(product['release_date'])
        today = date.fromtimestamp(now)
        eligible = (price.is_finite() and msrp.is_finite() and 0 < price <= msrp
                    and observation.get('currency') == 'USD'
                    and bool(product.get('msrp_source')) and bool(product.get('release_source'))
                    and cutoff(today) <= released <= today)
    except (InvalidOperation, ValueError, TypeError, KeyError):
        eligible = False
    return status, eligible


def ingest(observations, catalog, state, enqueue, cancel, now=None):
    now = time.time() if now is None else now
    outcomes = {}
    for observation in observations:
        key = observation.get('retailer', '') + ':' + observation.get('sku', '')
        product = catalog.get(key)
        if not product:
            outcomes[key] = 'not_in_catalog'
            continue
        status, eligible = normalize(observation, product, now)
        payload = dict(product, price=observation.get('price'))
        outcomes[key] = state.observe(key, status, payload, observation.get('observed_at', now), eligible)
        if status == 'out_of_stock' and outcomes[key] != 'stale_observation':
            for identity, in state.db.execute("SELECT id FROM events WHERE sku=? AND status='queued'", (key,)).fetchall():
                cancel(identity)
                with state.db:
                    state.db.execute("UPDATE events SET status='cancelled' WHERE id=?", (identity,))
    for identity, raw in state.pending(now):
        p = json.loads(raw)
        label = RETAILERS[p['retailer']][0]
        expires = state.db.execute('SELECT expires FROM events WHERE id=?', (identity,)).fetchone()[0]
        alert = {'title': f"{label} restock: {p['title']}", 'url': p['url'],
                 'event_id': identity, 'expires_at': expires,
                 'message': f"{p['title']}\n{label}: ${p['price']} (MSRP ${p['msrp']})\n{p['url']}\nObserved out of stock → in stock for shipping. Availability may change before checkout."}
        if enqueue(alert) == 'queued_for_email':
            with state.db:
                state.db.execute("UPDATE events SET status='queued' WHERE id=?", (identity,))
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('observations', 'catalog', 'state', 'email-module'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('email_outbox', args.email_module)
    email = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(email)
    products = json.loads(args.catalog.read_text())['products']
    catalog = {p['retailer'] + ':' + p['sku']: p for p in products}
    result = ingest(json.loads(args.observations.read_text()), catalog,
                    StockState(args.state, namespace='retail'), email.enqueue, email.cancel_event)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
