import unittest
from health_watchdog import connect, check, problems


class WatchdogTests(unittest.TestCase):
    def test_episode_dedup_and_recovery(self):
        db = connect(':memory:')
        check(db, ['failed'])
        check(db, ['different failure'])
        self.assertEqual(db.execute('SELECT count(*) FROM notifications').fetchone()[0], 1)
        db.execute("UPDATE notifications SET status='sent' WHERE id='outage:1'")
        check(db, [])
        check(db, [])
        self.assertEqual(db.execute("SELECT id FROM notifications WHERE status='pending'").fetchall(), [('recovery:1',)])
        check(db, ['failed again'])
        self.assertEqual(db.execute("SELECT id FROM notifications WHERE status='pending'").fetchall(), [('outage:2',)])

    def test_unsent_outage_cancels_without_orphan_recovery(self):
        db = connect(':memory:')
        check(db, ['failed'])
        check(db, [])
        self.assertEqual(db.execute("SELECT count(*) FROM notifications WHERE status='pending'").fetchone()[0], 0)

    def test_heartbeat_does_not_hide_failed_inventory(self):
        h = dict(completed_at=1000, catalog_keys=['bestbuy:1'], latest_observations={})
        self.assertTrue(problems(h, 1000))
        h['latest_observations']['bestbuy:1'] = dict(status='out_of_stock', observed_at=1000)
        self.assertFalse(problems(h, 1000))
        self.assertTrue(problems(h, 1400))
        h['cooldown_until'] = {'bestbuy': 1100}
        self.assertTrue(problems(h, 1000))
