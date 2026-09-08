import tempfile
from pathlib import Path
import unittest
from transitions import StockState


class TransitionTests(unittest.TestCase):
    def test_initial_in_stock_and_repeat_never_alert(self):
        state = StockState(':memory:')
        self.assertEqual(state.observe('1', 'in_stock', now=1, eligible=True), 'baseline')
        for now in (2, 1000, 86400):
            self.assertEqual(state.observe('1', 'in_stock', now=now, eligible=True), 'unchanged')
        self.assertEqual(state.pending(86400), [])

    def test_out_in_alerts_once_and_unknown_does_not_rearm(self):
        state = StockState(':memory:')
        state.observe('1', 'out_of_stock', now=1)
        self.assertEqual(state.observe('1', 'in_stock', {'price': 20}, now=2, eligible=True), 'restock')
        state.observe('1', 'unknown', now=3)
        self.assertEqual(state.observe('1', 'in_stock', now=4, eligible=True), 'unchanged')
        self.assertEqual(len(state.pending(5)), 1)
        state.observe('1', 'out_of_stock', now=6)
        self.assertEqual(state.pending(7), [])
        state.observe('1', 'in_stock', now=8, eligible=True)
        self.assertEqual(len(state.pending(9)), 1)

    def test_restart_and_late_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite'
            state = StockState(path)
            state.observe('1', 'out_of_stock', now=10)
            state.observe('1', 'in_stock', now=11, eligible=True)
            state.db.close()
            state = StockState(path)
            self.assertEqual(state.observe('1', 'in_stock', now=12, eligible=True), 'unchanged')
            self.assertEqual(state.observe('1', 'out_of_stock', now=9), 'stale_observation')
            self.assertEqual(state.pending(200), [])

    def test_ineligible_transition_does_not_later_alert_without_stock_change(self):
        state = StockState(':memory:')
        state.observe('1', 'out_of_stock', now=1)
        self.assertEqual(state.observe('1', 'in_stock', now=2), 'ineligible_restock')
        self.assertEqual(state.observe('1', 'in_stock', now=3, eligible=True), 'unchanged')
        self.assertEqual(state.pending(4), [])
