import unittest
from datetime import date
from run_browser_monitor import scheduled, active_products


class ScheduleTests(unittest.TestCase):
    def test_upcoming_activates_on_release_without_slowing_current_checks(self):
        products = [{'sku':'current'}, {'sku':'future', 'watch_from':'2026-09-16'}]
        self.assertEqual(active_products(products, date(2026,9,8)), products[:1])
        self.assertEqual(active_products(products, date(2026,9,16)), products)

    def test_failures_do_not_starve_unchecked_products(self):
        catalog = {str(i): {'retailer': 'bestbuy'} for i in range(6)}
        latest = {'0': {'observed_at': 10}, '1': {'observed_at': 11, 'error': 'Error'}}
        self.assertEqual([k for k, _ in scheduled(catalog, latest)], ['2', '3'])
        latest.update({'2': {'observed_at': 12}, '3': {'observed_at': 13}})
        self.assertEqual([k for k, _ in scheduled(catalog, latest)], ['4', '5'])

    def test_per_retailer_limit_and_oldest_retry(self):
        catalog = {'a': {'retailer': 'bestbuy'}, 'b': {'retailer': 'walmart'}, 'c': {'retailer': 'bestbuy'}}
        latest = {'a': {'observed_at': 2}, 'b': {'observed_at': 3}, 'c': {'observed_at': 1}}
        self.assertEqual([k for k, _ in scheduled(catalog, latest, 1)], ['c', 'b'])
