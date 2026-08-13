from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_shell_is_self_contained_and_recoverable():
    html = (ROOT / "templates" / "offline_app.html").read_text()
    assert 'rel="stylesheet" href="/offline-app/assets/app.css' not in html
    assert '/offline-recover' in html
    assert 'service-worker.js?v=2.10.4' in html


def test_worker_is_isolated_and_versioned():
    js = (ROOT / "static" / "offline_app" / "service-worker.js").read_text()
    assert "v2-10-4" in js
    assert "url.pathname.startsWith('/offline-app/')" in js
    assert "url.pathname.startsWith('/api/')" in js
    assert "fetch(request, { cache: 'no-store'" in js


def test_recovery_route_preserves_indexeddb():
    app = (ROOT / "app.py").read_text()
    block = app.split('@app.get("/offline-recover")', 1)[1].split('@app.get("/offline-operations")', 1)[0]
    assert 'unregister' in block
    assert 'floki-offline-app-' in block
    assert 'indexedDB.deleteDatabase' not in block
