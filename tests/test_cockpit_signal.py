"""Cockpit 2.0 — het signaaldek: drie heldere kaarten (missie / aan jou / het dorp werkt),
'it takes a village to raise a CEO'."""
from __future__ import annotations
import json

from nooch_village import cockpit


def _snap(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "strategy.json").write_text(json.dumps({
        "purpose": "Nooch transforms the shoe industry, step by step.",
        "core_values": [{"title": "Do Right & Keep Going", "desc": "x"},
                        {"title": "Care for All", "desc": "y"}],
        "north_star": {"target": 1000000},
        "goals": [{"target": 1000, "active": True}]}), encoding="utf-8")
    for f in ("governance_records.json", "library.json", "human_inbox.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    return cockpit.gather(str(data))


def test_signaaldek_drie_kaarten(tmp_path):
    snap = _snap(tmp_path)
    page = cockpit.render_html(snap, "t")
    assert "🎯 De missie" in page
    assert "Aan jou" in page and "alleen jij beslist" in page
    assert "Het dorp werkt voor je" in page
    # missie lean: alleen purpose in de hero (review-1: target/BHAG → watcher, kernwaarden → huisregels)
    assert "Nooch transforms" in page
    assert "BHAG" not in page                       # BHAG bewust uit de hero gehaald
    # kernwaarden staan nu in de huisregels, niet in de hero
    assert "Do Right &amp; Keep Going" in page and "Kernwaarden" in page
    # target + conversie staan nu in de Website Watcher
    assert "Target (batch 4)" in page and "Conversie" in page
    # roloverleg-ingang staat altijd in 'Aan jou'
    assert 'href="/roloverleg"' in page
    # lopende projecten in het gele blok
    assert "Projecten lopen nu" in page


def test_signaal_toont_eerste_spanning_inline(tmp_path):
    snap = _snap(tmp_path)
    snap["backlog"] = [{"approvable": True, "title": "TikTok challenge", "iid": "op1",
                        "wat": "doe iets", "waarom": "omdat"}]
    snap["agenda_open"] = [{"id": "a"}]
    page = cockpit.render_html(snap, "t")
    assert "Kansen om te wegen" in page and "verwerk in focus" in page
    # de bovenste spanning is VOLLEDIG inline verwerkbaar (zelfde controls als werk-in-focus)
    assert "eerste spanning" in page and "TikTok challenge" in page
    assert "Hoe pak je dit op" in page and 'value="tac_project"' in page
    assert 'href="/triage"' in page          # 'alle spanningen' naar het overzicht
    assert "Roloverleg" in page


def test_eerste_spanning_readonly_valt_terug_op_link(tmp_path):
    snap = _snap(tmp_path)
    snap["backlog"] = [{"approvable": True, "title": "TikTok challenge", "iid": "op1"}]
    page = cockpit.render_html(snap)                 # geen token = read-only
    assert 'href="/triage?iid=op1"' in page          # alleen een linkje, geen inline-form
    assert "Hoe pak je dit op" not in page


def test_signaal_leeg_is_rustig(tmp_path):
    snap = _snap(tmp_path)
    page = cockpit.render_html(snap, "t")
    assert "Niks dat op je wacht" in page          # geen openstaande besluiten → rustige melding
