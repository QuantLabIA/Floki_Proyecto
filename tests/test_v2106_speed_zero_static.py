from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_speed_zero_uses_same_beverage_product_and_zero_category():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert 'sale_kind" value="beverage_zero"' in dashboard
    assert 'name="beverage_id" value="{{ beverage[\'id\'] }}"' in dashboard
    assert 'category = "drink_zero"' in app
    assert 'unit_price = 0.0' in app
    assert 'if "speed" not in speed_text' in app


def test_zero_speed_is_not_paid_but_counts_for_stock_and_benefit_report():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "total = 0 if sale_kind in {\"rrpp_benefit\", \"beverage_zero\"}" in app
    assert "category IN ('drink_zero','rrpp_benefit','birthday_benefit')" in app
    assert "category IN ('drink','drink_zero','drink_special','rrpp_benefit','birthday_benefit','birthday_discount')" in app


def test_admin_can_choose_void_or_delete_for_open_beverage_movement():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
    close_cash = (ROOT / "templates" / "close_cash.html").read_text(encoding="utf-8")
    assert '@app.post("/movements/<int:movement_id>/delete")' in app
    assert 'movement["cash_status"] != "open"' in app
    assert "delete_beverage_movement" in dashboard
    assert "delete_beverage_movement" in close_cash
