"""Cockpit 2.0 — het signaaldek: drie heldere kaarten (missie / aan jou / het dorp werkt),
'it takes a village to raise a CEO'."""
from __future__ import annotations
import json

from nooch_village import cockpit


def _snap(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    for f in ("governance_records.json", "library.json", "human_inbox.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    return cockpit.gather(str(data))


def test_signaaldek_drie_kaarten(tmp_path):
    snap = _snap(tmp_path)
    page = cockpit.render_html(snap, "t")
    assert "🎯 De missie" in page
    assert "Aan jou" in page and "alleen jij beslist" in page
    assert "Het dorp werkt voor je" in page
    assert "Het dorp brengt de CEO groot" in page
    # roloverleg-ingang staat altijd in 'Aan jou'
    assert 'href="/roloverleg"' in page


def test_signaal_toont_aandachtspunten(tmp_path):
    snap = _snap(tmp_path)
    # injecteer iets dat jouw besluit vraagt
    snap["backlog"] = [{"approvable": True, "title": "x"}]
    snap["competitor_candidates"] = [{"brand": "Veja"}]
    snap["agenda_open"] = [{"id": "a"}]
    page = cockpit.render_html(snap, "t")
    assert "Kansen om te wegen" in page and "▶ verwerk" in page
    assert "Nieuwe concurrenten" in page
    assert "Roloverleg" in page


def test_signaal_leeg_is_rustig(tmp_path):
    snap = _snap(tmp_path)
    page = cockpit.render_html(snap, "t")
    assert "Niks dat op je wacht" in page          # geen openstaande besluiten → rustige melding
