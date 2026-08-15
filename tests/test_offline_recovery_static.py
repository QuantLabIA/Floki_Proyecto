from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_shell_is_self_contained_and_fresh():
    html = (ROOT / "templates" / "floki_offline.html").read_text()
    assert 'rel="stylesheet" href="/floki-offline/assets/app.css' not in html
    assert '/floki-offline-reset' in html
    assert 'service-worker.js?v=2.10.6' in html
    assert 'PROTECCIÓN v2.10.6 · FRESH SCOPE' in html


def test_worker_is_isolated_and_versioned():
    js = (ROOT / "static" / "floki_offline" / "service-worker.js").read_text()
    assert "v2-10-6" in js or "v2.10.6" in js
    assert "url.pathname.startsWith('/floki-offline/')" in js
    assert "url.pathname.startsWith('/api/')" in js
    assert "fetch(request, { cache: 'no-store'" in js


def test_recovery_route_preserves_indexeddb():
    app = (ROOT / "app.py").read_text()
    block = app.split('@app.get("/floki-offline-reset")', 1)[1].split('@app.get("/offline-app/")', 1)[0]
    assert 'unregister' in block
    assert 'floki-offline-' in block
    assert 'indexedDB.deleteDatabase' not in block


def test_plain_deploy_probe_has_no_external_dependencies():
    app = (ROOT / "app.py").read_text()
    block = app.split('@app.get("/floki-offline-test")', 1)[1].split('@app.get("/floki-offline-reset")', 1)[0]
    assert 'Floki Offline OK' in block
    assert '<script' not in block
    assert '<link' not in block
