"""Shopify-verkoopskill: pure aggregatie, gepagineerde fetch (gemockte POST), fail-closed zonder
token, en het cockpit-dashboard. Geen netwerk, geen PII."""
from __future__ import annotations
from types import SimpleNamespace

from datetime import datetime, timezone
from nooch_village.skills_impl.shopify_sales import (
    aggregate_orders, fetch_orders, get_access_token, ShopifySalesSkill)


def _order(country, cur, total, items):
    return {"created_at": "2026-06-01", "country": country, "currency": cur,
            "total": total, "line_items": [{"title": t, "quantity": q} for t, q in items]}


def test_aggregate_orders():
    orders = [
        _order("NL", "EUR", 120.0, [("Sneaker Groen", 1), ("Sneaker Zwart", 1)]),
        _order("NL", "EUR", 60.0, [("Sneaker Groen", 1)]),
        _order("DE", "EUR", 180.0, [("Sneaker Groen", 2)]),
    ]
    agg = aggregate_orders(orders, 28)
    assert agg["pairs_sold"] == 5 and agg["orders"] == 3
    assert agg["revenue"] == 360.0 and agg["currency"] == "EUR"
    assert agg["aov"] == 120.0
    assert dict(agg["by_country"])["NL"] == 2 and dict(agg["by_country"])["DE"] == 1
    assert agg["top_products"][0] == ("Sneaker Groen", 4)


def test_aggregate_leeg():
    agg = aggregate_orders([], 28)
    assert agg["pairs_sold"] == 0 and agg["orders"] == 0 and agg["aov"] == 0.0


def _gql_page(nodes, has_next, cursor=None):
    return {"data": {"orders": {
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "nodes": nodes}}}


def _node(country, amount, items):
    return {"createdAt": "2026-06-01",
            "currentTotalPriceSet": {"shopMoney": {"amount": str(amount), "currencyCode": "EUR"}},
            "shippingAddress": {"countryCodeV2": country},
            "lineItems": {"nodes": [{"title": t, "quantity": q} for t, q in items]}}


def test_fetch_orders_pagineert():
    pages = [
        _gql_page([_node("NL", 100, [("A", 1)])], True, "c1"),
        _gql_page([_node("DE", 50, [("B", 2)])], False),
    ]
    calls = {"n": 0}
    def fake_post(query, variables):
        i = calls["n"]; calls["n"] += 1
        if i == 0:
            assert variables["cursor"] is None and "created_at:>=" in variables["q"]
        else:
            assert variables["cursor"] == "c1"
        return pages[i]
    orders = fetch_orders("x.myshopify.com", "tok", "2026-05-01", _post=fake_post)
    assert len(orders) == 2 and calls["n"] == 2
    assert orders[0]["country"] == "NL" and orders[1]["line_items"][0]["quantity"] == 2


def test_aggregate_7d_subvenster():
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    orders = [
        {"created_at": "2026-06-24T10:00:00Z", "country": "NL", "currency": "EUR",
         "total": 90.0, "line_items": [{"title": "Groen", "quantity": 1}]},   # binnen 7d
        {"created_at": "2026-06-01T10:00:00Z", "country": "NL", "currency": "EUR",
         "total": 60.0, "line_items": [{"title": "Groen", "quantity": 1}]},   # ouder dan 7d
    ]
    agg = aggregate_orders(orders, 28, now=now)
    assert agg["orders"] == 2 and agg["pairs_sold"] == 2
    assert agg["orders_7d"] == 1 and agg["pairs_7d"] == 1


def test_aggregate_gemiddelden_per_maand():
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    # eerste order 60 dagen geleden → span ~2 maanden; 10 paar → ~5/maand
    orders = [
        {"created_at": "2026-04-26T00:00:00Z", "country": "NL", "currency": "EUR",
         "total": 300.0, "line_items": [{"title": "A", "quantity": 5}]},
        {"created_at": "2026-06-20T00:00:00Z", "country": "NL", "currency": "EUR",
         "total": 300.0, "line_items": [{"title": "A", "quantity": 5}]},
    ]
    agg = aggregate_orders(orders, 0, now=now)
    assert agg["pairs_sold"] == 10 and agg["first_order_date"] == "2026-04-26"
    assert agg["span_days"] >= 59
    assert 4.0 <= agg["avg_pairs_month"] <= 6.0          # ~5 paar/maand


def test_fetch_orders_hele_historie_geen_filter():
    seen = {}
    def fake_post(query, variables):
        seen["q"] = variables["q"]
        return _gql_page([_node("NL", 50, [("A", 1)])], False)
    fetch_orders("x.myshopify.com", "tok", None, _post=fake_post)
    assert seen["q"] is None                              # geen datumfilter bij hele historie


def test_get_access_token_geinjecteerd():
    tok = get_access_token("x.myshopify.com", "cid", "sec",
                           _post=lambda s, i, c: "shpat_runtime_123")
    assert tok == "shpat_runtime_123"


def test_skill_failclosed_zonder_credentials():
    ctx = SimpleNamespace(settings={}, data_dir="/tmp")
    assert ShopifySalesSkill().run({}, ctx).get("ok") is None
    assert "ontbreekt" in ShopifySalesSkill().run({}, ctx)["error"]
    # store maar geen token/credentials → ook fail-closed
    ctx2 = SimpleNamespace(settings={"SHOPIFY_STORE": "x.myshopify.com"}, data_dir="/tmp")
    assert "CLIENT_ID" in ShopifySalesSkill().run({}, ctx2)["error"]


def test_skill_met_static_token():
    ctx = SimpleNamespace(settings={"SHOPIFY_STORE": "x.myshopify.com", "SHOPIFY_TOKEN": "tok"},
                          data_dir="/tmp")
    post = lambda q, v: _gql_page([_node("NL", 90, [("Groen", 1)])], False)
    res = ShopifySalesSkill().run({"window_days": 7, "_post": post}, ctx)
    assert res["ok"] and res["pairs_sold"] == 1 and res["orders"] == 1 and res["window_days"] == 7


def test_skill_met_client_credentials():
    ctx = SimpleNamespace(settings={"SHOPIFY_STORE": "x.myshopify.com",
                                    "SHOPIFY_CLIENT_ID": "cid", "SHOPIFY_CLIENT_SECRET": "sec"},
                          data_dir="/tmp")
    res = ShopifySalesSkill().run({
        "window_days": 7,
        "_token_post": lambda s, i, c: "shpat_runtime",
        "_post": lambda q, v: _gql_page([_node("NL", 90, [("Groen", 1)])], False)}, ctx)
    assert res["ok"] and res["pairs_sold"] == 1


def test_cockpit_dashboard_render():
    from nooch_village import cockpit
    shop = {"ok": True, "window_days": 28, "pairs_sold": 42, "orders": 30,
            "revenue": 5400, "currency": "EUR", "aov": 180.0, "orders_7d": 8,
            "by_country": [("NL", 20), ("DE", 10)], "top_products": [("Sneaker Groen", 25)]}
    page = cockpit._render_watcher_dashboard(shop, visitors_7d=400)
    assert "Website Watcher" in page and "42" in page and "paren verkocht" in page
    assert "laatste 28 dagen" in page
    assert "Sneaker Groen" in page and "NL" in page
    assert "bezoekers (7d)" in page and "conversie (7d)" in page and "2.0%" in page  # 8/400
    # hele historie → gemiddelden + 'sinds'
    allt = {"ok": True, "window_days": 0, "pairs_sold": 120, "orders": 80, "revenue": 14400,
            "currency": "EUR", "aov": 180.0, "by_country": [], "top_products": [],
            "avg_pairs_month": 20.0, "avg_revenue_month": 2400.0, "first_order_date": "2026-01-01"}
    p2 = cockpit._render_watcher_dashboard(allt)
    assert "hele historie" in p2 and "gem. paren/maand" in p2 and "sinds 2026-01-01" in p2
    # leeg → hint, geen crash
    assert "Nog geen Shopify-data" in cockpit._render_watcher_dashboard({})
