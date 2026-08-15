from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_base_has_no_offline_mode_controls_or_bridge():
    html = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "Modo offline" not in html
    assert "offline-bridge.js" not in html
    assert "url_for('offline_app')" not in html


def test_settings_has_no_offline_panel():
    html = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
    assert 'id="modo-offline"' not in html
    assert "Offline aislado" not in html


def test_backend_offline_routes_removed():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for decorator in [
        '@app.get("/api/offline/bootstrap")', '@app.post("/api/offline/sync")',
        '@app.get("/offline-app/")', '@app.get("/floki-offline/")',
        '@app.get("/offline-recover")', '@app.get("/offline-operations")'
    ]:
        assert decorator not in source
    assert '"offline_mode": "removed"' in source
    assert '"connection_mode": "online_only"' in source


def test_offline_assets_removed():
    assert not (ROOT / "static" / "floki_offline").exists()
    assert not (ROOT / "static" / "offline_app").exists()
    assert not (ROOT / "static" / "js" / "offline-bridge.js").exists()
