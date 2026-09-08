"""Independent persistent outage/recovery queue, checked by a launchd timer."""
import argparse
import json
from pathlib import Path
import sqlite3
import time


def problems(health, now):
    if now - health.get('completed_at', 0) > 180:
        return ['Collector heartbeat missing or more than 3 minutes old.']
    issues = []
    latest = health.get('latest_observations', {})
    keys = health.get('catalog_keys', [])
    if not keys:
        issues.append('No verified catalog observations are available yet.')
    for key in keys:
        obs = latest.get(key, {})
        if obs.get('error') or obs.get('status') not in ('in_stock', 'out_of_stock'):
            issues.append(key + ': inventory unavailable (' + str(obs.get('error_reason') or obs.get('error') or 'not observed') + ').')
        elif now - obs.get('observed_at', 0) > 300:
            issues.append(key + ': inventory observation more than 5 minutes old.')
    for retailer, until in health.get('cooldown_until', {}).items():
        if until > now:
            issues.append(retailer + ': backing off after a collection error.')
    return issues


def connect(path):
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, unhealthy INTEGER, episode INTEGER);
      INSERT OR IGNORE INTO state VALUES (1, 0, 0);
      CREATE TABLE IF NOT EXISTS notifications
      (id TEXT PRIMARY KEY, episode INTEGER, kind TEXT, body TEXT, status TEXT, gmail_id TEXT);
    ''')
    return db


def check(db, issues):
    unhealthy, episode = db.execute('SELECT unhealthy, episode FROM state WHERE id=1').fetchone()
    if issues and not unhealthy:
        episode += 1
        body = ('Pokémon monitor needs attention. Stock collection is degraded; alerts may be missed.\n\n'
                + '\n'.join(issues) + '\n\nThe background service will continue retrying with cooldowns. '
                'You will receive one recovery email after all configured products have fresh inventory observations. '
                'Catalog coverage is still incomplete. Delivery uses the locally configured email worker.')
        db.execute('INSERT INTO notifications VALUES (?, ?, ?, ?, ?, NULL)',
                   (f'outage:{episode}', episode, 'outage', body, 'pending'))
    elif not issues and unhealthy:
        delivered = db.execute("SELECT 1 FROM notifications WHERE id=? AND status='sent'", (f'outage:{episode}',)).fetchone()
        db.execute("UPDATE notifications SET status='cancelled' WHERE episode=? AND status='pending'", (episode,))
        if delivered:
            db.execute('INSERT INTO notifications VALUES (?, ?, ?, ?, ?, NULL)',
                       (f'recovery:{episode}', episode, 'recovery',
                        'Pokémon monitor recovered. All configured products have fresh inventory observations again. '
                        'This describes collector health, not complete catalog coverage or a stock restock.', 'pending'))
    if issues:
        db.execute("UPDATE notifications SET status='cancelled' WHERE kind='recovery' AND status='pending'")
    db.execute('UPDATE state SET unhealthy=?, episode=? WHERE id=1', (bool(issues), episode))
    db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'pending', 'sent'])
    parser.add_argument('--health', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--id')
    parser.add_argument('--gmail-id')
    args = parser.parse_args()
    db = connect(args.database)
    try:
        if args.command in ('check', 'pending'):
            try:
                health = json.loads(args.health.read_text())
                issues = problems(health, time.time())
            except (OSError, ValueError, TypeError, AttributeError):
                issues = ['Collector health file missing or unreadable.']
            check(db, issues)
            if args.command == 'pending':
                print(json.dumps([dict(id=r[0], kind=r[1], body=r[2]) for r in db.execute(
                    "SELECT id, kind, body FROM notifications WHERE status='pending'")]))
        else:
            if not args.id or not args.gmail_id:
                parser.error('sent requires --id and --gmail-id after confirmed delivery')
            db.execute("UPDATE notifications SET status='sent', gmail_id=? WHERE id=? AND status='pending'", (args.gmail_id, args.id))
            db.commit()
    finally:
        db.close()


if __name__ == '__main__':
    main()
