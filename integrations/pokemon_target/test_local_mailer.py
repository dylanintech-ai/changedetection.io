import sqlite3
import unittest
from local_mailer import send_claimed


class SMTP:
    def __init__(self, error=None):
        self.messages = []
        self.error = error
    def send_message(self, message):
        self.messages.append(message)
        if self.error:
            raise self.error
    def close(self):
        pass


class MailerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE outbox(id TEXT PRIMARY KEY, status TEXT, gmail_id TEXT)')
        self.db.execute("INSERT INTO outbox VALUES('one','pending',NULL)")
        self.db.commit()
    def deliver(self, smtp):
        send_claimed(self.db, 'outbox', 'one', 'Restock', 'Buy link', {'username':'dylanwindow@gmail.com'}, lambda _: smtp)
    def test_success_is_not_repeated(self):
        smtp = SMTP()
        self.deliver(smtp)
        self.deliver(smtp)
        self.assertEqual(len(smtp.messages), 1)
        self.assertEqual(self.db.execute('SELECT status FROM outbox').fetchone()[0], 'sent')
    def test_ambiguous_disconnect_is_not_retried(self):
        smtp = SMTP(ConnectionResetError())
        with self.assertRaises(ConnectionResetError):
            self.deliver(smtp)
        self.assertEqual(self.db.execute('SELECT status FROM outbox').fetchone()[0], 'uncertain')
        self.deliver(smtp)
        self.assertEqual(len(smtp.messages), 1)
    def test_auth_failure_leaves_message_pending(self):
        def fail(_):
            raise PermissionError()
        with self.assertRaises(PermissionError):
            send_claimed(self.db, 'outbox', 'one', 'Restock', 'Buy link', {}, fail)
        self.assertEqual(self.db.execute('SELECT status FROM outbox').fetchone()[0], 'pending')
