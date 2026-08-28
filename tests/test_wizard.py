"""Project-wizard (founder 20 jul): de LLM maakt een ruw idee scherp tot een toetsbare uitkomst
en stelt een checklist voor die per item tegen de skills van de rol wordt getoetst."""
from __future__ import annotations

import json

from nooch_village import cockpit2
from nooch_village.wizard import plan_items, sharpen_outcome


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_sharpen_fail_soft():
    # LLM levert niets → ruw idee terug (mens kan alsnog verder)
    assert sharpen_outcome("kijk naar zolen", reason_fn=lambda *a, **k: None) == "kijk naar zolen"
    assert sharpen_outcome("", reason_fn=lambda *a, **k: "x") == ""
    # LLM levert een uitkomst → schoongemaakt terug
    out = sharpen_outcome("zolen", reason_fn=lambda *a, **k: '  "Er ligt een overzicht van 3 zolen." ')
    assert out == "Er ligt een overzicht van 3 zolen."


CATALOG = [
    {"name": "epo_patents", "description": "patenten", "input": "query: str"},
    {"name": "openalex_evidence", "description": "studies", "input": "term: str"},
]
REQUIRED = {"epo_patents": ("query",), "openalex_evidence": ("term",)}


def _fake_plan(*a, **k):
    return json.dumps({"items": [
        {"tekst": "Zoek patenten op afbreekbare zolen", "skill": "epo_patents",
         "payload": {"query": "biodegradable outsole"}},
        {"tekst": "Haal studies op", "skill": "openalex_evidence", "payload": {}},   # payload mist
        {"tekst": "Bel drie leveranciers", "skill": None, "payload": {}},            # geen skill
        {"tekst": "Gebruik magie", "skill": "niet_bestaand", "payload": {}},         # skill niet van rol
    ]})


def test_plan_items_toetst_skills_en_payload():
    items = plan_items("Overzicht afbreekbare zolen", CATALOG,
                       reason_fn=_fake_plan, required_of=lambda s: REQUIRED.get(s, ()))
    assert len(items) == 4
    assert items[0]["skill"] == "epo_patents" and items[0]["ok"] is True
    assert items[1]["skill"] == "openalex_evidence" and items[1]["ok"] is False   # payload onvolledig
    assert "payload onvolledig" in items[1]["reden"]
    assert items[2]["skill"] is None and items[2]["ok"] is False                   # mens-taak
    assert items[3]["skill"] is None                                                # onbekende skill → null


def test_plan_items_fail_soft():
    assert plan_items("doel", CATALOG, reason_fn=lambda *a, **k: None) == []
    assert plan_items("", CATALOG, reason_fn=_fake_plan) == []


# ── één ingang: beide knoppen openen de wizard, voorgevuld ──────────────────

def test_de_wizard_neemt_voorvulling_mee_en_begint_op_de_juiste_stap(tmp_path):
    """Wat de mens al intypte hoort hij niet over te tikken — dat is precies waarom die kale
    formulieren bestonden."""
    import re
    from nooch_village.views.wizard import render_wizard
    st = _st(tmp_path)
    rid = "mother_earth__nooch__website_developer"
    h = render_wizard(st, "t", role=rid, ruw="doos scheurt", uitkomst="geen klachten meer")
    assert re.search(r"step:2", h)                      # met uitkomst → aanscherpen
    assert 'ruw:"doos scheurt"' in h and 'uitkomst:"geen klachten meer"' in h
    h2 = render_wizard(st, "t", role=rid, ruw="alleen een zaadje")
    assert re.search(r"step:1", h2)                     # alleen zaad → het idee
    assert re.search(r"step:0", render_wizard(st, "t"))  # niets → rolkeuze


def test_de_bordknop_en_de_inbox_knop_openen_dezelfde_wizard(tmp_path):
    """Drie manieren om een project te maken werd er één. Beide knoppen bouwen dezelfde URL."""
    from nooch_village.views.projects import _quickadd
    from nooch_village.views.inbox import _outcome_form
    bord = _quickadd("mother_earth__nooch__website_developer", "actief", "t", "/node?id=x")
    assert "/project/nieuw?" in bord and "proj_add" not in bord
    assert "ruw:" in bord and "uitkomst:" in bord        # titel én done-when reizen mee
    inbox = _outcome_form("project", "nid", "t", "de spanningstekst", "<option>r</option>", "",
                          "/inbox", "u1")
    assert "/project/nieuw?" in inbox and "notif_outcome" not in inbox
    assert "ruw:" in inbox and "role:" in inbox          # content als zaad, rol mee
    # de andere uitkomsttypen blijven gewoon opnemen
    ping = _outcome_form("ping", "nid", "t", "x", "<option>r</option>", "", "/inbox", "u2")
    assert "notif_outcome" in ping and "/project/nieuw" not in ping


def test_de_checklist_stap_is_overslaanbaar_en_faalt_open(tmp_path):
    """De AI-checklist is een bonus, geen poort: een trage of ontbrekende LLM mag niemand
    vasthouden bij een project op het bord zetten."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "Skip this step" in h                        # en wel METEEN, ook tijdens het wachten
    assert h.count("Skip this step") >= 2               # op de wachtkaart én op de lijst
    assert "AbortController" in h and "PLAN_TIMEOUT_MS" in h
    assert "Your project will be created either way" in h
