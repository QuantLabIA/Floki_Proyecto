import tempfile
import unittest
from pathlib import Path

from database import connect_database, translate_postgres_sql


class DatabaseLayerTests(unittest.TestCase):
    def test_sqlite_connection_keeps_row_compatibility(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = connect_database('', Path(temp_dir) / 'test.db')
            db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
            cursor = db.execute('INSERT INTO users(name) VALUES (?)', ('Pablo',))
            self.assertEqual(cursor.lastrowid, 1)
            row = db.execute('SELECT * FROM users WHERE id=?', (1,)).fetchone()
            self.assertEqual(row['name'], 'Pablo')
            self.assertEqual(row[0], 1)
            db.close()

    def test_postgres_translation(self):
        sql, returns_id = translate_postgres_sql(
            'INSERT OR IGNORE INTO promoters(name, created_at) VALUES (?, ?)',
            append_returning=True,
        )
        self.assertIn('ON CONFLICT DO NOTHING', sql)
        self.assertIn('RETURNING id', sql)
        self.assertNotIn('?', sql)
        self.assertTrue(returns_id)

    def test_nocase_and_date_translation(self):
        sql, _ = translate_postgres_sql(
            'SELECT * FROM cash_sessions WHERE date(event_date)>=date(?) ORDER BY event_name COLLATE NOCASE',
            append_returning=False,
        )
        self.assertIn('CAST(event_date AS DATE)', sql)
        self.assertIn('lower(event_name)', sql)
        self.assertIn('%s', sql)


if __name__ == '__main__':
    unittest.main()
