from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_offline_shell_has_iphone_safe_render_overrides():
    html = (ROOT / "templates" / "offline_app.html").read_text(encoding="utf-8")
    assert "Render seguro iPhone/iPad" in html
    assert "backdrop-filter: none !important" in html
    assert "body.offline-operations-page .ambient { display: none !important" in html

def test_offline_shell_does_not_force_reload_after_worker_install():
    html = (ROOT / "templates" / "offline_app.html").read_text(encoding="utf-8")
    assert "location.reload()" not in html

def test_offline_worker_is_still_isolated_and_cache_bumped():
    sw = (ROOT / "static" / "offline_app" / "service-worker.js").read_text(encoding="utf-8")
    assert "v2-10-3" in sw
    assert "url.pathname.startsWith('/offline-app/')" in sw
