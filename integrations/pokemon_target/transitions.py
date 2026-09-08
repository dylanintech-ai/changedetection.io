"""Persistent availability transitions. Startup and unknown states never alert."""
import json
import sqlite3
import time


class StockState:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=15)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS stock (
            sku TEXT PRIMARY KEY, status TEXT NOT NULL, observed REAL NOT NULL,
            generation INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, sku TEXT NOT NULL, created REAL NOT NULL,
            expires REAL NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL);
        ''')

    def observe(self, sku, status, payload=None, now=None, eligible=False):
        now = time.time() if now is None else now
        if status not in ('in_stock', 'out_of_stock', 'unknown'):
            raise ValueError('Unsupported stock state')
        if status == 'unknown':
            return 'unknown'
        with self.db:
            previous = self.db.execute('SELECT status,observed,generation FROM stock WHERE sku=?', (sku,)).fetchone()
            if previous and now <= previous[1]:
                return 'stale_observation'
            generation = previous[2] if previous else 0
            transition = previous and previous[0] == 'out_of_stock' and status == 'in_stock'
            if transition:
                generation += 1
            self.db.execute('INSERT OR REPLACE INTO stock VALUES (?,?,?,?)', (sku, status, now, generation))
            if status == 'out_of_stock':
                self.db.execute("UPDATE events SET status='cancelled' WHERE sku=? AND status='pending'", (sku,))
            if transition and eligible:
                event_id = f'target:{sku}:{generation}'
                self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)',
                                (event_id, sku, now, now + 180, json.dumps(payload), 'pending'))
                return 'restock'
            if transition:
                return 'ineligible_restock'
            return 'baseline' if not previous else 'unchanged' if previous[0] == status else 'out_of_stock'

    def pending(self, now=None):
        now = time.time() if now is None else now
        with self.db:
            self.db.execute("UPDATE events SET status='expired' WHERE status='pending' AND expires<=?", (now,))
        return self.db.execute("SELECT id,payload FROM events WHERE status='pending' ORDER BY created").fetchall()
