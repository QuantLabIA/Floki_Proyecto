import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OfflineIsolationStaticTests(unittest.TestCase):
    def test_service_worker_is_scoped_to_offline_app(self):
        source = (ROOT / "static" / "offline_app" / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("url.pathname.startsWith('/offline-app/')", source)
        self.assertIn("if (url.pathname.startsWith('/api/')) return", source)
        self.assertNotIn("scope: '/'", source)

    def test_main_app_preserves_isolated_worker(self):
        source = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("pathname === '/'", source)
        self.assertIn("scope: '/offline-app/'", source)
        self.assertNotIn("registrations.map((registration) => registration.unregister())", source)

    def test_offline_manifest_has_isolated_scope(self):
        source = (ROOT / "static" / "offline_app" / "manifest.webmanifest").read_text(encoding="utf-8")
        self.assertIn('"scope": "/offline-app/"', source)
        self.assertIn('"start_url": "/offline-app/', source)

    def test_offline_template_does_not_load_main_app_js(self):
        source = (ROOT / "templates" / "offline_app.html").read_text(encoding="utf-8")
        self.assertNotIn('/static/js/app.js', source)
        self.assertIn('/offline-app/assets/offline-sync.js', source)


if __name__ == "__main__":
    unittest.main()
