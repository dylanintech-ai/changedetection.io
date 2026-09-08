import unittest
from bestbuy_browser import extract


class BestBuyTests(unittest.TestCase):
    def setUp(self):
        self.expected = {'sku': '6643669', 'url': 'https://www.bestbuy.com/product/test/sku/6643669'}
        self.offer = {'sku': '6643669', 'seller': {'name': 'Best Buy'}, 'price': 29.99,
                      'priceCurrency': 'USD', 'availability': 'https://schema.org/InStock',
                      'availableDeliveryMethod': []}
        self.product = {'sku': '6643669', 'offers': [self.offer]}

    def test_live_store_only_counterexample(self):
        controls = [{'testid': 'pdp-in-store-only-6643669', 'text': 'In Store Only', 'disabled': True}]
        self.assertEqual(extract(self.product, self.expected, controls)['status'], 'unknown')

    def test_recommendation_cart_cannot_trigger(self):
        self.offer['availableDeliveryMethod'] = ['https://schema.org/DeliveryModeParcelService']
        unrelated = [{'testid': 'cart-123', 'text': 'Add to cart', 'disabled': False}]
        self.assertEqual(extract(self.product, self.expected, unrelated)['status'], 'unknown')
        matching = [{'testid': 'cart-6643669', 'text': 'Add to cart', 'disabled': False}]
        self.assertEqual(extract(self.product, self.expected, matching)['status'], 'in_stock')
        self.offer['seller']['name'] = 'Marketplace'
        self.assertIn('error', extract(self.product, self.expected, matching))

    def test_explicit_sold_out(self):
        controls = [{'testid': 'pdp-sold-out-6643669', 'text': 'Sold Out', 'disabled': True}]
        self.assertEqual(extract(self.product, self.expected, controls)['status'], 'out_of_stock')


if __name__ == '__main__':
    unittest.main()
