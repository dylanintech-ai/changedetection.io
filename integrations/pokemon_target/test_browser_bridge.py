from datetime import datetime, timezone
import unittest
from browser_bridge import ingest, normalize
from transitions import StockState


class BrowserBridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 8, 16, tzinfo=timezone.utc).timestamp()
        self.product = dict(retailer='walmart', sku='123', title='Test Pokémon TCG',
                            url='https://www.walmart.com/ip/test/123', msrp=29.99,
                            msrp_source='https://example.test/price',
                            release_date='2025-12-12', release_source='https://example.test/release')
        self.observation = dict(retailer='walmart', sku='123', url=self.product['url'],
                                seller='Walmart', observed_at=self.now, evidence='Product page stock controls',
                                status='in_stock', shipping_available=True, price=29.99, currency='USD')

    def test_untrusted_stock_cannot_rearm(self):
        for change in ({'seller': 'Marketplace'}, {'error': 'blocked'},
                       {'observed_at': self.now - 181}, {'url': 'https://www.walmart.com/ip/test/124'},
                       {'status': 'store_only'}, {'shipping_available': False}, {'evidence': ''}):
            o = dict(self.observation, **change)
            self.assertEqual(normalize(o, self.product, self.now), ('unknown', False))
        for change in ({'price': 30}, {'price': 'NaN'}, {'currency': 'CAD'}):
            self.assertEqual(normalize(dict(self.observation, **change), self.product, self.now), ('in_stock', False))

    def test_transition_delivery_and_cancellation(self):
        state = StockState(':memory:', namespace='retail')
        catalog = {'walmart:123': self.product}
        queued, cancelled = [], []
        def enqueue(alert):
            queued.append(alert)
            return 'queued_for_email'
        def run(status, second):
            return ingest([dict(self.observation, status=status, observed_at=self.now+second)],
                          catalog, state, enqueue, cancelled.append, self.now+second)
        run('in_stock', 0)
        run('in_stock', 1)
        self.assertEqual(queued, [])
        run('out_of_stock', 2)
        run('unknown', 3)
        run('in_stock', 4)
        run('in_stock', 5)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]['event_id'], 'retail:walmart:123:1')
        run('out_of_stock', 6)
        self.assertEqual(cancelled, ['retail:walmart:123:1'])

    def test_release_window_and_missing_msrp(self):
        for change in ({'release_date': '2024-09-07'}, {'release_date': '2026-09-09'},
                       {'msrp_source': ''}, {'release_source': ''}, {'msrp': None}):
            self.assertEqual(normalize(self.observation, dict(self.product, **change), self.now), ('in_stock', False))


if __name__ == '__main__':
    unittest.main()
