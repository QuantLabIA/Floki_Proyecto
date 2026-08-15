from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_offline_shell_has_iphone_safe_render_overrides():
    html = (ROOT / "templates" / "floki_offline.html").read_text(encoding="utf-8")
    assert "backdrop-filter: none !important" in html
    assert "body.offline-operations-page .ambient { display: none !important" in html


def test_offline_shell_does_not_force_reload_after_worker_install():
    html = (ROOT / "templates" / "floki_offline.html").read_text(encoding="utf-8")
    assert "location.reload()" not in html


def test_offline_worker_uses_brand_new_scope_and_cache():
    sw = (ROOT / "static" / "floki_offline" / "service-worker.js").read_text(encoding="utf-8")
    assert "floki-offline-v2105-" in sw
    assert "url.pathname.startsWith('/floki-offline/')" in sw
