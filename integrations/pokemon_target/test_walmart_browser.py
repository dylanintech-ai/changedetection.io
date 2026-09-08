import unittest
from walmart_browser import extract


class WalmartExtractionTests(unittest.TestCase):
    def setUp(self):
        self.expected = dict(sku='123', url='https://www.walmart.com/ip/123')
        self.product = dict(usItemId='123', sellerName='Walmart.com', sellerType='INTERNAL',
                            availabilityStatus='IN_STOCK', preOrder={'isPreOrder': False},
                            priceInfo={'currentPrice': {'price': 20, 'currencyUnit': 'USD'}},
                            fulfillmentOptions=[{'type': 'SHIPPING', 'availabilityStatus': 'IN_STOCK'}])

    def test_shipping_not_store_availability(self):
        self.assertEqual(extract(self.product, self.expected)['status'], 'in_stock')
        self.product['fulfillmentOptions'] = [{'type': 'PICKUP', 'availabilityStatus': 'IN_STOCK'}]
        self.assertEqual(extract(self.product, self.expected)['status'], 'unknown')
        self.product['fulfillmentOptions'] = [{'type': 'SHIPPING', 'availabilityStatus': 'OUT_OF_STOCK'}]
        self.assertEqual(extract(self.product, self.expected)['status'], 'out_of_stock')

    def test_identity_restrictions_and_preorders(self):
        self.assertIn('error', extract(self.product, dict(self.expected, sku='456')))
        self.product['preOrder']['isPreOrder'] = True
        self.assertEqual(extract(self.product, self.expected)['status'], 'unknown')
        self.product['preOrder']['isPreOrder'] = False
        self.product['fulfillmentOptions'][0]['restricted'] = True
        self.assertEqual(extract(self.product, self.expected)['status'], 'unknown')

    def test_marketplace_not_normalized_as_walmart(self):
        self.product['sellerName'] = 'Some Seller'
        self.product['sellerType'] = 'EXTERNAL'
        self.assertEqual(extract(self.product, self.expected)['seller'], 'Some Seller')


if __name__ == '__main__':
    unittest.main()
