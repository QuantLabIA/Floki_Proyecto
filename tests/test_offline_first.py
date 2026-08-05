import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ["FLOKI_SECRET_KEY"] = "test-secret"
import app as app_module


class OfflineFirstTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = app_module.app.config["DATABASE"]
        app_module.app.config.update(TESTING=True, DATABASE=self.db_path, DATABASE_URL="")
        app_module.init_db()
        self.client = app_module.app.test_client()
        self.token = self.login()
        self.open_cash()

    def tearDown(self):
        app_module.app.config["DATABASE"] = self.original_db
        Path(self.db_path).unlink(missing_ok=True)

    def login(self):
        self.client.get("/login")
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]
        response = self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123", "csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            return sess["csrf_token"]

    def open_cash(self):
        response = self.client.post(
            "/cash/open",
            data={
                "event_name": "Offline Test",
                "event_date": "2026-08-05",
                "opening_amount": "0",
                "capacity": "100",
                "csrf_token": self.token,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

    def post_sync(self, operations):
        return self.client.post(
            "/api/offline/sync",
            json={"device_id": "device-test-123456", "operations": operations},
            headers={"X-CSRF-Token": self.token},
        )

    def test_bootstrap_contains_event_and_catalog(self):
        response = self.client.get("/api/offline/bootstrap")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["cash_session"]["event_name"], "Offline Test")
        self.assertEqual(payload["user"]["username"], "admin")
        self.assertTrue(payload["entry_prices"])
        self.assertTrue(payload["beverages"])
        self.assertEqual(payload["csrf_token"], self.token)

    def test_quick_sale_sync_is_idempotent(self):
        bootstrap = self.client.get("/api/offline/bootstrap").get_json()
        session_id = bootstrap["cash_session"]["id"]
        user_id = bootstrap["user"]["id"]
        operation = {
            "operation_id": "op-test-entry-000001",
            "operation_type": "quick_sale",
            "cash_session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().replace(hour=1, minute=15, second=0, microsecond=0).isoformat(sep=" "),
            "payload": {
                "sale_kind": "entry",
                "category": "general",
                "quantity": "2",
                "payment_method": "cash",
                "promoter_id": "",
            },
        }
        first = self.post_sync([operation])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["summary"]["applied"], 1)
        second = self.post_sync([operation])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["results"][0]["status"], "applied")

        connection = sqlite3.connect(self.db_path)
        movement_count = connection.execute(
            "SELECT COUNT(*) FROM movements WHERE category='general' AND quantity=2"
        ).fetchone()[0]
        operation_count = connection.execute(
            "SELECT COUNT(*) FROM offline_operations WHERE operation_id='op-test-entry-000001'"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(movement_count, 1)
        self.assertEqual(operation_count, 1)

    def test_offline_guest_checkin_and_duplicate_conflict(self):
        bootstrap = self.client.get("/api/offline/bootstrap").get_json()
        session_id = bootstrap["cash_session"]["id"]
        user_id = bootstrap["user"]["id"]
        connection = sqlite3.connect(self.db_path)
        common_id = connection.execute("SELECT id FROM promoters WHERE is_common=1").fetchone()[0]
        guest_id = connection.execute(
            """INSERT INTO promoter_guests(
                   cash_session_id,promoter_id,guest_name,normalized_name,source_filename,imported_at,imported_by
               ) VALUES (?,?,?,?,?,?,?)""",
            (session_id, common_id, "Ana Offline", "ana offline", "test", app_module.now_iso(), user_id),
        ).lastrowid
        connection.commit()
        connection.close()

        first = {
            "operation_id": "op-test-checkin-0001",
            "operation_type": "guest_checkin",
            "cash_session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().replace(hour=1, minute=20, second=0, microsecond=0).isoformat(sep=" "),
            "payload": {"guest_id": guest_id},
        }
        second = {**first, "operation_id": "op-test-checkin-0002"}
        response = self.post_sync([first, second])
        payload = response.get_json()
        self.assertEqual(payload["results"][0]["status"], "applied")
        self.assertEqual(payload["results"][1]["status"], "conflict")
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM guest_checkins").fetchone()[0], 1)
        connection.close()


if __name__ == "__main__":
    unittest.main()
