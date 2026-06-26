"""Cockpit-opruiming (feedback ronde 1): backlog weg uit dashboard, inbox ingeklapt, projectpagina
toont deliverable + leesbare status, Field Notes leespagina, attributie in nette kaders."""
from __future__ import annotations
from nooch_village import cockpit


def test_project_pagina_toont_deliverable_en_status():
    p = {"id": "p1", "owner": "scout", "scope": "Blog over veganisme", "status": "running",
         "progress": "Een eerste blogdraft van 300 woorden.", "hypothesis": "meer bereik"}
    page = cockpit.render_project_edit(p, [{"id": "scout", "type": "role", "archived": False}], "t")
    # De uitwerking staat nu in de gesprekswall (geen apart 'Deliverable'-blok meer).
    assert "Gesprek met de rol" in page and "eerste blogdraft" in page
    assert "Blog over veganisme" in page


def test_fieldnotes_leeg_en_gevuld():
    leeg = cockpit.render_fieldnotes([], "", "", 0, 0)
    assert "Nog geen Field Notes" in leeg
    files = ["field_note_2026-06-25.md", "field_note_2026-06-24.md"]
    page = cockpit.render_fieldnotes(files, files[0], "# Field Note\nbezoekers stegen.", 1, 2)
    assert "Field Note 1 van 2" in page and "bezoekers stegen" in page
    assert "/fieldnotes?f=field_note_2026-06-24.md" in page   # blader-link naar de oudere


def test_watcher_dashboard_kaders_en_conversienoot():
    shop = {"ok": True, "window_days": 7, "pairs_sold": 1, "orders": 1, "revenue": 159,
            "currency": "EUR", "aov": 159.0, "orders_7d": 1,
            "by_country": [("NL", 1)], "top_products": [("THE 269 SPRING BLOOM", 1)],
            "channels": [("onbekend", 1)], "top_landing_pages": [], "top_keywords": []}
    page = cockpit._render_watcher_dashboard(shop, visitors_7d=115)
    assert "wbox" in page and "Orders per land" in page          # nette kaders
    assert "conversie (7d)" in page and "1 orders" in page       # conversienoot met de getallen


def test_watcher_dashboard_eerlijke_databaken_testorder():
    # 2 paren bij €0 omzet en 1 order = testorder + scope-waarschuwing
    shop = {"ok": True, "window_days": 0, "pairs_sold": 2, "orders": 1, "revenue": 0,
            "currency": "EUR", "aov": 0.0, "first_order_date": "2026-06-02"}
    page = cockpit._render_watcher_dashboard(shop, visitors_7d=0)
    assert "testorder" in page                                   # €0 bij verkochte paren
    assert "530-batch" in page and "footwear-nooch" in page      # scope + andere kanalen
