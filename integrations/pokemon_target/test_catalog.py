from datetime import date
import unittest
from catalog import cutoff, extract


class CatalogTests(unittest.TestCase):
    def test_scope_and_conservative_price(self):
        dates = ['2024-09-08', '2024-09-07', '2026-09-09', None]
        items = [{'tcin': str(i), 'price': {'current_retail': 69.99, 'reg_retail': 69.99},
                  'item': {'primary_brand': {'name': 'Pokemon'}, 'mmbv_content': {'street_date': release},
                           'product_description': {'title': 'Pok&#233;mon'}}} for i, release in enumerate(dates)]
        rows, total = extract({'data': {'search': {'products': items, 'search_response': {'metadata': {'total_results': 4}}}}}, date(2026, 9, 8))
        self.assertEqual([r['scope'] for r in rows], ['recent', 'older', 'upcoming', 'unknown_release_date'])
        self.assertTrue(all(r['msrp'] is None and r['watch']['paused'] for r in rows))
        self.assertEqual(rows[0]['title'], 'Pokémon')
        self.assertEqual(cutoff(date(2024, 2, 29)), date(2022, 2, 28))


if __name__ == '__main__':
    unittest.main()
