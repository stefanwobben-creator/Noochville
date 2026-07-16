"""Kennisbank (laag 2) — store, veld van zekerheid en view.

Het acceptatiecriterium uit de bouwbrief staat hier als test: drie survey-bevindingen
uit dezelfde bron zijn één stem ("nog dun"); één onafhankelijke bron erbij → "stevig".
"""
from __future__ import annotations

import types

import pytest

from nooch_village.kennisbank import (KennisbankStore, field, verdict, atom_trust,
                                      independence_group, parse_blok, _bump)


def _atom(claim: str, source: str, provenance: str = "", **kw) -> dict:
    a = {"claim": claim, "source": source}
    if provenance:
        a["provenance"] = provenance
    a.update(kw)
    return a


def _links(*paren) -> list[dict]:
    return [{"atom_id": aid, "stance": stance} for aid, stance in paren]


# ── het veld van zekerheid ───────────────────────────────────────────────────

@pytest.mark.smoke
def test_woozle_guard_drie_uit_een_bron_is_dun_onafhankelijk_maakt_stevig():
    atoms = {
        "a1": _atom("51% wil €150", "waitlist-survey", "survey"),
        "a2": _atom("Idealist €100-129", "waitlist-survey", "survey"),
        "a3": _atom("Van Westendorp €120", "waitlist-survey", "survey"),
        "b1": _atom("prijstest elders", "extern marktonderzoek", "expert_opinion"),
    }
    drie = _links(("a1", "support"), ("a2", "support"), ("a3", "support"))
    v = verdict(field(drie, atoms))
    assert v["word"] == "dun"
    assert "allemaal uit één bron" in v["sentence"]      # 3 bevindingen ≠ 3 stemmen

    v2 = verdict(field(drie + _links(("b1", "support")), atoms))
    assert v2["word"] == "stevig"                         # 2 onafhankelijke bronnen, geen tegen


def test_verdict_ladder_dun_omstreden_groeit():
    atoms = {
        "s1": _atom("x", "bron-a"), "s2": _atom("y", "bron-b"),
        "c1": _atom("z", "bron-c"), "c2": _atom("w", "bron-d"),
        "c_leeg": _atom("v", ""),   # tegenspraak zonder bron telt niet als tegenstem
    }
    assert verdict(field([], atoms))["word"] == "dun"
    assert verdict(field(_links(("s1", "support")), atoms))["word"] == "dun"
    assert verdict(field(_links(("s1", "support"), ("s2", "support"),
                                ("c1", "counter")), atoms))["word"] == "groeit"
    assert verdict(field(_links(("s1", "support"), ("s2", "support"), ("c1", "counter"),
                                ("c2", "counter")), atoms))["word"] == "omstreden"
    assert verdict(field(_links(("s1", "support"), ("s2", "support"),
                                ("c_leeg", "counter")), atoms))["word"] == "stevig"


def test_trust_afgeleid_niet_handmatig():
    assert atom_trust(_atom("x", "j", "peer_reviewed")) == 0.90
    assert atom_trust(_atom("x", "j", evidence_type="measured")) == 0.75   # fallback
    assert atom_trust(_atom("x", "j")) == 0.20                             # unknown
    # ordening: peer_reviewed > certificaat > eigen data > survey > media > advocacy
    ladder = [atom_trust(_atom("x", "j", p))
              for p in ("peer_reviewed", "certificate", "internal_data",
                        "survey", "media", "advocacy")]
    assert ladder == sorted(ladder, reverse=True)


def test_independence_group_normaliseert_bron():
    assert independence_group(_atom("x", "Waitlist-Survey")) == \
        independence_group(_atom("y", "waitlist survey"))
    assert independence_group(_atom("x", "a", independence_group="groep-1")) == "groep-1"


# ── de store (append-only, geversioneerd) ────────────────────────────────────

@pytest.mark.smoke
def test_store_happy_path_persist_en_versies(tmp_path):
    pad = str(tmp_path / "kennisbank.json")
    kb = KennisbankStore(pad)
    iid = kb.add("Wachttijd is een feature", why="mensen kopen tóch", subject="vraag", by="test")

    assert kb.link(iid, "atom1", "support", annotation="eigen data", by="test")
    assert kb.link(iid, "atom2", "counter", by="test")
    assert not kb.link(iid, "atom3", "gek")               # ongeldige richting → geweigerd
    assert kb.discuss(iid, "sterke claim, zwak bewijs", by="stefan")
    assert kb.annotate(iid, "atom1", "dit is de kern")

    # herformuleren = versie-bump + vorige versie mét evidence-snapshot in history
    assert kb.reformulate(iid, title="Wachttijd bindt de kern-doelgroep",
                          reframe="wachttijd is gewoon een kost",
                          falsifier="kortere wachttijd verkoopt aantoonbaar meer") == "1.1"

    vers = KennisbankStore(pad)                            # refresh-persistent (fase 1-criterium)
    ins = vers.get(iid)
    assert ins["title"] == "Wachttijd bindt de kern-doelgroep"
    assert ins["version"] == "1.1"
    assert ins["history"][0]["title"] == "Wachttijd is een feature"
    assert len(ins["history"][0]["evidence_snapshot"]) == 2
    assert [l["atom_id"] for l in ins["evidence"]] == ["atom1", "atom2"]   # set stroomt door
    assert ins["evidence"][0]["annotation"] == "dit is de kern"
    assert ins["discussion"][0]["by"] == "stefan"

    # loskoppelen verwijdert alleen de link (de kaart blijft in de bibliotheek)
    assert vers.unlink(iid, "atom2")
    assert [l["atom_id"] for l in vers.get(iid)["evidence"]] == ["atom1"]
    # ...maar de snapshot van v1.0 blijft onaangetast (reproduceerbaar)
    assert len(vers.get(iid)["history"][0]["evidence_snapshot"]) == 2


def test_link_idempotent_geen_dubbele_stem(tmp_path):
    kb = KennisbankStore(str(tmp_path / "kb.json"))
    iid = kb.add("claim")
    kb.link(iid, "a", "support")
    kb.link(iid, "a", "counter", annotation="toch tegen")   # zelfde kaart → richting draait
    ev = kb.get(iid)["evidence"]
    assert len(ev) == 1 and ev[0]["stance"] == "counter" and ev[0]["annotation"] == "toch tegen"


def test_parse_blok_en_bump():
    blok = ("ruis\n=== INZICHT ===\nTITEL: Kort\nCLAIM: De claim.\n"
            "REFRAME: De andere kant.\nFALSIFIER: Iets zichtbaars.\n=== EINDE ===")
    p = parse_blok(blok)
    assert (p["title"], p["claim"], p["reframe"], p["falsifier"]) == \
        ("Kort", "De claim.", "De andere kant.", "Iets zichtbaars.")
    assert parse_blok("geen blok")["claim"] == ""
    assert _bump("1.0") == "1.1" and _bump("2.9") == "2.10" and _bump("") == "1.1"


# ── de view (geen machinerie naar buiten) ────────────────────────────────────

def test_view_toont_woord_en_meter_geen_percentages(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path)
    kb = KennisbankStore(f"{dd}/kennisbank.json")
    iid = kb.add("Prijs blokkeert onze kern-doelgroep", why="drie signalen, één survey",
                 subject="prijs")
    st = types.SimpleNamespace(dd=dd, kennisbank=kb)

    html = render_kennisbank(st, csrf_token="tok")
    assert "Wat Nooch weet" in html and "nog dun" in html
    # de machinerie blijft binnen: geen ruwe trust/strength/groep-ids in de UI
    for verboden in ("strength", "agreement", "independence_group", "0.9", "trust"):
        assert verboden not in html

    detail = render_kennisbank(st, kid=iid, csrf_token="tok")
    assert "kn-drawer" in detail and "Nog geen bewijs verzameld." in detail
    assert "kb_reformulate" in detail and "=== INZICHT ===" in detail
