from datetime import datetime, timezone
import unittest
from bridge import normalize


class BridgeTests(unittest.TestCase):
    def test_freshness_price_and_exact_identity(self):
        now = datetime(2026, 9, 8, tzinfo=timezone.utc).timestamp()
        p = {'tcin': '1', 'street_date': '2025-01-01', 'msrp': 20, 'msrp_source': 'fixture', 'seller_verified': True}
        w = {'url': 'https://www.target.com/p/-/A-1', 'last_checked': now,
             'restock': {'in_stock': True, 'price': 20, 'currency': 'USD'}}
        self.assertEqual(normalize(w, p, now), ('in_stock', True))
        self.assertEqual(normalize(dict(w, last_error='Blocked'), p, now), ('unknown', False))
        self.assertEqual(normalize(w, p, now + 181), ('unknown', False))
        self.assertEqual(normalize(w, dict(p, seller_verified=False), now), ('in_stock', False))
        self.assertEqual(normalize(w, dict(p, msrp=19), now), ('in_stock', False))
        self.assertEqual(normalize(w, dict(p, tcin='2'), now), ('unknown', False))
