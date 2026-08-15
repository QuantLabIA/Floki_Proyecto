import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OfflineIsolationStaticTests(unittest.TestCase):
    def test_service_worker_is_scoped_to_fresh_namespace(self):
        source = (ROOT / "static" / "floki_offline" / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("url.pathname.startsWith('/floki-offline/')", source)
        self.assertIn("if (url.pathname.startsWith('/api/')) return", source)
        self.assertNotIn("scope: '/'", source)

    def test_main_app_never_registers_service_worker(self):
        source = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        bridge = (ROOT / "static" / "js" / "offline-bridge.js").read_text(encoding="utf-8")
        self.assertNotIn("serviceWorker.register", source)
        self.assertNotIn("serviceWorker.register", bridge)

    def test_offline_manifest_has_fresh_scope(self):
        source = (ROOT / "static" / "floki_offline" / "manifest.webmanifest").read_text(encoding="utf-8")
        self.assertIn('"scope": "/floki-offline/"', source)
        self.assertIn('"start_url": "/floki-offline/', source)

    def test_offline_template_does_not_load_main_app_js(self):
        source = (ROOT / "templates" / "floki_offline.html").read_text(encoding="utf-8")
        self.assertNotIn('/static/js/app.js', source)
        self.assertIn('/floki-offline/assets/offline-sync.js', source)


if __name__ == "__main__":
    unittest.main()
