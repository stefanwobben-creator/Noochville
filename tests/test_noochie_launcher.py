"""Globale Noochie-launcher (cockpit 2): dunne balk + venster, geleide mini-triage, context-chip."""
from __future__ import annotations

from nooch_village import cockpit2


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_chrome_balk_en_cta(tmp_path):
    # de globale chrome bevat de linkerbalk + Noochie-CTA + venster-overlay
    chrome = cockpit2._noochie_chrome()
    assert "noo-rail" in chrome and "noo-cta" in chrome and "Noochie" in chrome
    assert "id='novl'" in chrome and "/noochie?fragment=1" in chrome


def test_venster_opent_met_eerste_vraag(tmp_path):
    dd = _dd(tmp_path)
    frag = cockpit2.render_noochie(cockpit2._Stores(dd), csrf="t")
    # opent met de eerste triage-vraag (spanning), niet een open 'hoe kan ik helpen'
    assert "noo-win" in frag and "Noochie" in frag and "welke spanning" in frag.lower()
    assert "noochie_send" in frag


def test_geleide_triage_spanning_dan_behoefte_dan_suggestie(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "noochie_send", {"text": ["bezoekers dalen"], "next": ["/"]})
    s = cockpit2._Stores(dd).noochie
    assert s.phase == "ask_need" and s.state()["spanning"] == "bezoekers dalen"
    assert any("nodig" in m["text"].lower() for m in s.messages)   # tweede vraag gesteld
    cockpit2.dispatch(dd, "noochie_send", {"text": ["meer content"], "next": ["/"]})
    s2 = cockpit2._Stores(dd).noochie
    assert s2.phase == "free" and s2.state()["need"] == "meer content"
    # na twee vragen komt er een (fail-closed) concrete suggestie van Noochie
    assert s2.messages[-1]["who"] == "noochie" and s2.messages[-1]["text"]


def test_suggestie_via_voorstel_schrijven(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.noochie.set_field("spanning", "NL-corpus onbruikbaar")
    st.noochie.set_field("need", "betere bron")
    # testhook: de suggestie loopt via Noochie's voorstel_schrijven-tension
    seen = {}
    out = cockpit2._noochie_suggest(st, ask=lambda tension: (seen.__setitem__("t", tension), "ok")[1])
    assert out == "ok" and "NL-corpus onbruikbaar" in seen["t"] and "betere bron" in seen["t"]


def test_context_chip_human_gated(tmp_path):
    dd = _dd(tmp_path)
    # zonder committed context: aanbod om het scherm mee te nemen
    frag = cockpit2.render_noochie(cockpit2._Stores(dd), csrf="t", screen_ctx="Voorstel X")
    assert "neem dit scherm mee" in frag and "Voorstel X" in frag
    # human zet context aan -> chip 'leest: X'
    cockpit2.dispatch(dd, "noochie_ctx", {"ctx": ["Voorstel X"], "next": ["/"]})
    frag2 = cockpit2.render_noochie(cockpit2._Stores(dd), csrf="t")
    assert "leest: Voorstel X" in frag2
    # en weer weghalen
    cockpit2.dispatch(dd, "noochie_ctx", {"ctx": [""], "next": ["/"]})
    assert cockpit2._Stores(dd).noochie.ctx == ""


def test_reset(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "noochie_send", {"text": ["iets"], "next": ["/"]})
    cockpit2.dispatch(dd, "noochie_reset", {"next": ["/"]})
    s = cockpit2._Stores(dd).noochie
    assert s.phase == "ask_spanning" and s.messages == []
