"""Radar → kennisbank: een goedgekeurd signaal promoveren tot kenniskaartje (atoom).

Dekt: promotie maakt één atoom met bron/link/datum via de store-paden; duplicaat (zelfde
stable_id-basis of zelfde genormaliseerde reference) → herkomst stapelt op het bestaande
kaartje i.p.v. een tweede kaartje; promoted_atom_id-marker + idempotentie (twee keer →
nette banner, geen duplicaat); config-vlag radar_auto_promote laat radar_approve meteen
doorpromoveren (default uit); fail-soft-gevallen; en de knop/chip-markup op /signals en
het archief-blok van de rol-Tools-tab."""
from __future__ import annotations

import os
from types import SimpleNamespace

from nooch_village import cockpit2
from nooch_village.insight import Insight
from nooch_village.kennisbank_intake import stable_id
from nooch_village.radar_promote import (auto_promote_enabled, norm_ref,
                                         parse_source_date, promote_signal)
from nooch_village.views.overview import _radar_item
from nooch_village.views.signals import render_signals

_ROLE = "concurrent_scout"
_CONTENT = "Vivobarefoot lanceert een plantaardige sneaker"
_LINK = "https://www.vivobarefoot.com/nieuws/plant?utm_source=x"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _approved(st, **kw):
    d = dict(role=_ROLE, feed="Competitor Watch", kind="concurrent", content=_CONTENT,
             rationale="concurrent-zet", source="vivobarefoot.com", link=_LINK,
             published_at="2026-05-11T00:00:00Z")
    d.update(kw)
    rid = st.radar.add(**d)
    st.radar.set_status(rid, "goedgekeurd")
    return rid


# ── helpers ──────────────────────────────────────────────────────────────────

def test_norm_ref_en_source_date():
    assert norm_ref(_LINK) == "vivobarefoot.com/nieuws/plant"
    assert norm_ref("http://vivobarefoot.com/nieuws/plant/") == "vivobarefoot.com/nieuws/plant"
    assert norm_ref("") == ""
    assert parse_source_date("2026-05-11T00:00:00Z") == "2026-05-11"
    assert parse_source_date("gisteren ofzo") == ""                # onparsebaar → leeg
    assert parse_source_date("") == ""


# ── promotie maakt een atoom ─────────────────────────────────────────────────

def test_promote_maakt_atoom_met_bron_link_datum(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    aid, msg = promote_signal(st, rid)
    assert aid and "kenniskaartje" in msg
    a = st.notes.get(aid)
    assert a is not None
    assert a.claim == _CONTENT                                     # letterlijk, geen LLM
    assert a.source == "vivobarefoot.com"
    assert a.reference == _LINK
    assert a.source_date == "2026-05-11"
    assert a.tags == ["signal"]
    assert a.evidence_type == "reported"
    assert a.version == 1
    assert aid == stable_id(_CONTENT, "vivobarefoot.com")          # stabiele id-basis
    # marker op het radar-item
    assert st.radar.get(rid)["promoted_atom_id"] == aid


def test_promote_bron_fallback_feed_en_radar(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    r1 = _approved(st, source="", content="Signaal zonder bron", link="https://a.example/1")
    aid1, _ = promote_signal(st, r1)
    assert st.notes.get(aid1).source == "Competitor Watch"         # fallback: feed-label
    r2 = _approved(st, source="", feed="", content="Signaal zonder bron en feed", link="")
    aid2, _ = promote_signal(st, r2)
    assert st.notes.get(aid2).source == "radar"                    # laatste fallback


def test_promote_onparsebare_datum_blijft_leeg(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st, published_at="ergens vorige week")
    aid, _ = promote_signal(st, rid)
    assert st.notes.get(aid).source_date is None


# ── duplicaat → merge, geen tweede kaartje ───────────────────────────────────

def test_duplicaat_zelfde_stable_id_merget_herkomst(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    bestaand = stable_id(_CONTENT, "vivobarefoot.com")
    st.notes.add(Insight(id=bestaand, claim=_CONTENT, source="vivobarefoot.com"))
    n_voor = len(st.notes.all())
    rid = _approved(st)
    aid, msg = promote_signal(st, rid)
    assert aid == bestaand and "samengevoegd" in msg
    assert len(st.notes.all()) == n_voor                           # geen tweede kaartje
    a = st.notes.get(bestaand)
    assert a.reference == _LINK                                    # herkomst gestapeld
    assert a.grounding_count == 2
    assert "signal" in a.tags
    assert st.radar.get(rid)["promoted_atom_id"] == bestaand       # marker wijst naar bestaand


def test_duplicaat_zelfde_genormaliseerde_reference_merget(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    st.notes.add(Insight(id="atom_bestaand1", claim="Andere formulering van hetzelfde nieuws",
                         source="andermans-nieuwsbrief",
                         reference="http://vivobarefoot.com/nieuws/plant/"))
    rid = _approved(st)                                            # zelfde artikel, utm + www
    aid, msg = promote_signal(st, rid)
    assert aid == "atom_bestaand1" and "samengevoegd" in msg
    a = st.notes.get("atom_bestaand1")
    assert "vivobarefoot.com" in a.source                          # bron "; "-gestapeld
    assert "andermans-nieuwsbrief" in a.source
    assert len([x for x in st.notes.all() if not x.archived]) == 1


def test_gearchiveerd_duplicaat_op_reference_telt_niet(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    st.notes.add(Insight(id="atom_oud1", claim="Oud kaartje", source="elders",
                         reference=_LINK))
    st.notes.archive("atom_oud1")
    rid = _approved(st)
    aid, msg = promote_signal(st, rid)
    assert aid != "atom_oud1" and "kenniskaartje" in msg           # archief blokkeert niet


# ── idempotentie ─────────────────────────────────────────────────────────────

def test_twee_keer_promoveren_geen_duplicaat(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    aid, _ = promote_signal(st, rid)
    n = len(st.notes.all())
    aid2, msg2 = promote_signal(st, rid)
    assert aid2 is None and "Al gepromoveerd" in msg2              # nette banner
    assert len(st.notes.all()) == n
    assert st.notes.get(aid).grounding_count == 1                  # ook niets gestapeld


# ── de actie (POST /action, radar_promote) ───────────────────────────────────

def test_dispatch_radar_promote(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    nxt, msg = cockpit2.dispatch(dd, "radar_promote",
                                 {"rid": [rid], "next": ["/signals"]}, username="guest")
    assert nxt == "/signals" and "kenniskaartje" in msg
    st2 = cockpit2._Stores(dd)
    assert st2.radar.get(rid)["promoted_atom_id"]
    assert st2.notes.get(st2.radar.get(rid)["promoted_atom_id"]).claim == _CONTENT


def test_dispatch_failsoft_onbekend_en_niet_goedgekeurd(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _, msg = cockpit2.dispatch(dd, "radar_promote",
                               {"rid": ["bestaat-niet"], "next": ["/"]}, username="guest")
    assert "onbekend" in msg
    rid = st.radar.add(role=_ROLE, feed="f", kind="kaart", content="Nog in de wachtrij")
    _, msg = cockpit2.dispatch(dd, "radar_promote",
                               {"rid": [rid], "next": ["/"]}, username="guest")
    assert "alleen goedgekeurde" in msg
    assert len(cockpit2._Stores(dd).notes.all()) == 0              # niets aangemaakt


def test_promote_leeg_signaal_failsoft():
    # Randgeval buiten de normale store-flow (add weigert lege content al): de guard zelf.
    fake = SimpleNamespace(radar=SimpleNamespace(
        get=lambda rid: {"status": "goedgekeurd", "content": "   "}))
    aid, msg = promote_signal(fake, "x")
    assert aid is None and "leeg" in msg


# ── config-vlag radar_auto_promote ───────────────────────────────────────────

def test_auto_promote_vlag_default_uit(tmp_path):
    dd = _dd(tmp_path)
    assert auto_promote_enabled(dd) is False                       # geen settings.ini → uit
    st = cockpit2._Stores(dd)
    rid = st.radar.add(role=_ROLE, feed="f", kind="kaart", content="Alleen goedkeuren")
    _, msg = cockpit2.dispatch(dd, "radar_approve",
                               {"rid": [rid], "next": ["/"]}, username="guest")
    assert "archief" in msg and "kenniskaartje" not in msg
    st2 = cockpit2._Stores(dd)
    assert st2.notes.all() == []                                   # default-gedrag onveranderd
    assert "promoted_atom_id" not in st2.radar.get(rid)


def test_auto_promote_vlag_aan_promoveert_bij_approve(tmp_path):
    dd = _dd(tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "settings.ini").write_text("[radar]\nradar_auto_promote = 1\n")
    assert auto_promote_enabled(dd) is True
    st = cockpit2._Stores(dd)
    rid = st.radar.add(role=_ROLE, feed="Competitor Watch", kind="kaart",
                       content=_CONTENT, source="vivobarefoot.com", link=_LINK,
                       published_at="2026-05-11T00:00:00Z")
    _, msg = cockpit2.dispatch(dd, "radar_approve",
                               {"rid": [rid], "next": ["/"]}, username="guest")
    assert "archief" in msg and "kenniskaartje" in msg             # zelfde codepad
    st2 = cockpit2._Stores(dd)
    aid = st2.radar.get(rid)["promoted_atom_id"]
    assert st2.notes.get(aid).reference == _LINK


# ── markup: knop op elk goedgekeurd item, chip na promotie ───────────────────

def test_signals_pagina_toont_knop_en_daarna_chip(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    html = render_signals(st, csrf_token="tok")
    assert "radar_promote" in html and "→ kenniskaartje" in html
    assert "style=" not in html                                    # geen inline styles (ratchet)
    promote_signal(st, rid)
    html2 = render_signals(st, csrf_token="tok")
    assert "radar_promote" not in html2                            # knop weg
    assert "→ in kennisbank" in html2 and "/kennisbank?q=signal" in html2
    # zonder csrf: geen knop, chip blijft (read-only weergave)
    assert "→ in kennisbank" in render_signals(st)


def test_rol_tools_archief_toont_knop_en_chip(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    it = st.radar.get(rid)
    row = _radar_item(it, "tok", _ROLE, archief=True)
    assert "radar_promote" in row and "→ kenniskaartje" in row
    promote_signal(st, rid)
    row2 = _radar_item(st.radar.get(rid), "tok", _ROLE, archief=True)
    assert "radar_promote" not in row2 and "→ in kennisbank" in row2
    # wachtrij-items houden alleen ✓/✗ — promoveren kan pas na goedkeuren
    wid = st.radar.add(role=_ROLE, feed="f", kind="kaart", content="Wachtrij-item")
    wrow = _radar_item(st.radar.get(wid), "tok", _ROLE, archief=False)
    assert "radar_promote" not in wrow and "radar_approve" in wrow
