"""Standalone Gmail SMTP delivery. No Codex, browser, or paid service required."""
import argparse
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from email.utils import formatdate
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import smtplib
import sqlite3
import ssl
import time
import webbrowser
from catalog import cutoff
from health_watchdog import connect as health_connect, check, problems

RUNTIME = Path.home() / 'projects/pokemon-restock-alerts'
CONFIG = Path.home() / '.config/pokemon-restock/smtp.json'
CATALOG = Path(__file__).with_name('retailer_catalog.json')
RECIPIENT = 'dylanwindow@gmail.com'


def smtp_login(config):
    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20, context=ssl.create_default_context())
    try:
        smtp.login(config['username'], config['password'])
    except Exception:
        smtp.close()
        raise
    return smtp


def configure():
    print('Create a Google app password named Pokemon restock. Paste it here, not into chat.')
    webbrowser.open('https://myaccount.google.com/apppasswords')
    password = getpass.getpass('Google app password (hidden): ').replace(' ', '')
    config = {'username': RECIPIENT, 'password': password}
    with closing(smtp_login(config)):
        pass
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(config, file)
    temporary.replace(CONFIG)
    print('Gmail authenticated. Credential saved privately on this Mac. Background delivery is enabled.')


def eligible(db, alert, now, catalog):
    row = db.execute('SELECT e.sku,e.expires,e.payload,e.status,s.status,s.observed FROM events e JOIN stock s ON s.sku=e.sku WHERE e.id=?', (alert.get('event_id'),)).fetchone()
    if not row or row[3] != 'queued' or row[4] != 'in_stock' or row[1] <= now or not 0 <= now-row[5] <= 180:
        return False
    product = catalog.get(row[0])
    if not product:
        return False
    try:
        payload = json.loads(row[2])
        price, msrp = Decimal(str(payload['price'])), Decimal(str(product['msrp']))
        today = date.fromtimestamp(now)
        return (price.is_finite() and msrp.is_finite() and 0 < price <= msrp
                and product.get('release_source') and product.get('msrp_source')
                and cutoff(today) <= date.fromisoformat(product['release_date']) <= today
                and alert.get('url') == product['url'] == payload['url'])
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return False


def send_claimed(db, table, identity, subject, body, config, sender=smtp_login, validate=lambda: True):
    # Authenticate before claiming: rejected credentials cannot have sent mail.
    with closing(sender(config)) as smtp:
        if not validate():
            return
        changed = db.execute(f"UPDATE {table} SET status='sending' WHERE id=? AND status='pending'", (identity,)).rowcount
        db.commit()
        if not changed:
            return
        message = EmailMessage()
        message['From'] = config['username']
        message['To'] = RECIPIENT
        message['Subject'] = subject
        message['Date'] = formatdate(localtime=True)
        message['Message-ID'] = '<pokemon-' + hashlib.sha256((table+identity).encode()).hexdigest() + '@gmail.com>'
        message.set_content(body)
        try:
            smtp.send_message(message)
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
            db.execute(f"UPDATE {table} SET status='pending' WHERE id=?", (identity,))
            db.commit()
            raise
        except Exception:
            # Disconnect after DATA could mean delivered. Never blindly resend.
            db.execute(f"UPDATE {table} SET status='uncertain' WHERE id=?", (identity,))
            db.commit()
            raise
        db.execute(f"UPDATE {table} SET status='sent',gmail_id=? WHERE id=?", (str(message['Message-ID']), identity))
        db.commit()


def run():
    lock = (RUNTIME/'local-mailer.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not CONFIG.exists():
            return {'status': 'needs_setup', 'detail': 'Run setup-email.command to authenticate Gmail locally.'}
        if CONFIG.stat().st_mode & 0o077:
            raise ValueError('SMTP config must have mode 0600')
        config = json.loads(CONFIG.read_text())
        now = time.time()
        with closing(health_connect(RUNTIME/'health-notifications.sqlite')) as db:
            try:
                issues = problems(json.loads((RUNTIME/'browser-health.json').read_text()), now)
            except (OSError, ValueError, TypeError, AttributeError):
                issues = ['Collector health file missing or unreadable.']
            check(db, issues)
            for identity, kind, body in db.execute("SELECT id,kind,body FROM notifications WHERE status='pending'").fetchall():
                send_claimed(db, 'notifications', identity,
                             'Pokémon monitor: ' + ('collection degraded' if kind == 'outage' else 'collection recovered'), body, config)
        catalog = {p['retailer']+':'+p['sku']: p for p in json.loads(CATALOG.read_text())['products']}
        with closing(sqlite3.connect(RUNTIME/'email.sqlite', timeout=15)) as db, closing(sqlite3.connect(RUNTIME/'retailer-state.sqlite', timeout=15)) as stock:
            db.execute("UPDATE outbox SET status='expired' WHERE status='pending' AND expires<=?", (time.time(),))
            db.commit()
            for identity, raw in db.execute("SELECT id,alert FROM outbox WHERE status='pending'").fetchall():
                alert = json.loads(raw)
                if eligible(stock, alert, time.time(), catalog):
                    send_claimed(db, 'outbox', identity, alert['title'], alert['message'], config,
                                 validate=lambda: eligible(stock, alert, time.time(), catalog))
        return {'status': 'ok'}
    finally:
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'configure'])
    args = parser.parse_args()
    if args.command == 'configure':
        try:
            configure()
        except Exception as error:
            print('Setup unsuccessful: ' + type(error).__name__ + '. No credential was saved.')
            raise SystemExit(1)
    else:
        try:
            status = run()
        except Exception as error:
            status = {'status': 'error', 'error_type': type(error).__name__}
        status['checked_at'] = time.time()
        temporary = RUNTIME/'mail-health.tmp'
        temporary.write_text(json.dumps(status))
        temporary.replace(RUNTIME/'mail-health.json')
