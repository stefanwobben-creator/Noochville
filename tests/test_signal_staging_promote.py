"""Signaal-promotie via de staging-tussenstap ("Even nakijken").

Dekt: stage_signal zet een goedgekeurd signaal klaar in een staging-batch (kind='signaal')
met herkomst (bron/link/datum) en radar_rids; meerdere signalen landen in dezelfde open
batch (samen te mergen); idempotent bij dubbelklik; commit maakt het kaartje via het
promote-pad (dedupe op content+bron én reference, herkomst stapelen, promoted-marker);
mergen in staging markeert álle betrokken signalen; weggooien in staging promoveert niet;
en de cockpit-actie stuurt door naar de staging-pagina.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from nooch_village import cockpit2
from nooch_village import radar_promote as rp
from nooch_village.insight import Insight
from nooch_village.kennisbank_intake import stable_id
from nooch_village.kennisbank_staging import commit_batch
from nooch_village.radar_promote import stage_signal

_ROLE = "concurrent_scout"


@pytest.fixture(autouse=True)
def _geen_bron_lezen(monkeypatch):
    """Standaard geen echte fetch/LLM in tests: stage_signal valt terug op de signaaltekst.
    De bron-lees-tests overschrijven deze patch met hun eigen atomen."""
    monkeypatch.setattr(rp, "_atomen_uit_bron", lambda it: None)
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


# ── klaarzetten ──────────────────────────────────────────────────────────────

def test_stage_zet_signaal_klaar_met_herkomst(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    bid, msg = stage_signal(st, rid)
    assert bid and "Even nakijken" in msg
    b = st.staging.get(bid)
    assert b["kind"] == "signaal"
    (a,) = b["atoms"]
    assert a["content"] == _CONTENT
    assert a["source"] == "vivobarefoot.com"
    assert a["reference"] == _LINK
    assert a["source_date"] == "2026-05-11"
    assert a["radar_rids"] == [rid]
    # nog GEEN kaartje en nog geen marker: de mens heeft nog niet bevestigd
    assert st.notes.get(stable_id(_CONTENT, "vivobarefoot.com")) is None
    assert not st.radar.get(rid).get("promoted_atom_id")


def test_stage_idempotent_en_zelfde_batch_voor_tweede_signaal(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    r1 = _approved(st)
    r2 = _approved(st, content="Ander signaal over zolen", link="https://x.nl/a")
    b1, _ = stage_signal(st, r1)
    nogmaals, msg = stage_signal(st, r1)                 # dubbelklik
    assert nogmaals == b1 and "al klaar" in msg
    b2, _ = stage_signal(st, r2)                          # tweede signaal → zelfde set
    assert b2 == b1
    assert len(st.staging.get(b1)["atoms"]) == 2


def test_stage_guards(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    assert stage_signal(st, "bestaat_niet")[0] is None
    rid = st.radar.add(role=_ROLE, feed="f", kind="k", content="nog niet goedgekeurd",
                       rationale="", source="s", link="", published_at="")
    bid, msg = stage_signal(st, rid)
    assert bid is None and "goedgekeurde" in msg


# ── commit: het kaartje ontstaat pas bij bevestigen ──────────────────────────

def test_commit_maakt_kaartje_en_markeert_signaal(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    res = commit_batch(st.staging, bid, dd, radar=st.radar)
    assert res == (1, 0, 0)
    aid = stable_id(_CONTENT, "vivobarefoot.com")
    kaart = cockpit2._Stores(dd).notes.get(aid)              # her-lezen: commit schrijft via een eigen store
    assert kaart is not None and "signal" in kaart.tags
    assert kaart.reference == _LINK and kaart.source_date == "2026-05-11"
    assert cockpit2._Stores(dd).radar.get(rid)["promoted_atom_id"] == aid
    assert st.staging.get(bid) is None                    # batch opgeruimd


def test_commit_bewerkte_tekst_wordt_de_claim(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    sid = st.staging.get(bid)["atoms"][0]["sid"]
    st.staging.edit_atom(bid, sid, content="Strakker geformuleerd signaal")
    commit_batch(st.staging, bid, dd, radar=st.radar)
    aid = stable_id("Strakker geformuleerd signaal", "vivobarefoot.com")
    assert cockpit2._Stores(dd).notes.get(aid) is not None


def test_commit_dedupe_stapelt_op_bestaand_kaartje(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # bestaand kaartje met dezelfde artikel-URL (met andere querystaart)
    st.notes.add(Insight(id="bestaand1", claim="Eerder kaartje over de sneaker",
                         source="elders", reference="http://vivobarefoot.com/nieuws/plant/"))
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    res = commit_batch(st.staging, bid, dd, radar=st.radar)
    assert res == (0, 0, 1)                               # gekoppeld, geen duplicaat
    kaart = cockpit2._Stores(dd).notes.get("bestaand1")
    assert "signal" in kaart.tags
    assert "vivobarefoot.com" in (kaart.source or "")
    assert cockpit2._Stores(dd).radar.get(rid)["promoted_atom_id"] == "bestaand1"


def test_merge_in_staging_markeert_beide_signalen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    r1 = _approved(st)
    r2 = _approved(st, content="Tweede signaal over hetzelfde", link="https://x.nl/b")
    bid, _ = stage_signal(st, r1)
    stage_signal(st, r2)
    sids = [a["sid"] for a in st.staging.get(bid)["atoms"]]
    assert st.staging.merge_atoms(bid, sids, "Samengesteld signaal")
    (samengesteld,) = st.staging.get(bid)["atoms"]
    assert set(samengesteld["radar_rids"]) == {r1, r2}
    res = commit_batch(st.staging, bid, dd, radar=st.radar)
    assert res == (1, 0, 0)
    radar = cockpit2._Stores(dd).radar
    aid = stable_id("Samengesteld signaal", "vivobarefoot.com")
    assert radar.get(r1)["promoted_atom_id"] == aid
    assert radar.get(r2)["promoted_atom_id"] == aid


def test_weggooien_in_staging_promoveert_niet(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    sid = st.staging.get(bid)["atoms"][0]["sid"]
    st.staging.remove_atom(bid, sid)
    commit_batch(st.staging, bid, dd, radar=st.radar)
    assert not cockpit2._Stores(dd).radar.get(rid).get("promoted_atom_id")
    assert st.notes.get(stable_id(_CONTENT, "vivobarefoot.com")) is None


# ── cockpit-actie: doorsturen naar Even nakijken ─────────────────────────────

def test_actie_stuurt_door_naar_staging(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    c = SimpleNamespace(nxt="/signals", st=st, data_dir=dd, username="guest",
                        g=lambda k, _rid=rid: {"rid": _rid}.get(k, ""))
    nxt, msg = cockpit2._act_radar_promote(c)
    assert nxt.startswith("/kennisbank/staging?batch=")
    assert "Even nakijken" in msg
    # het kaartje bestaat nog NIET — pas na commit
    assert st.notes.get(stable_id(_CONTENT, "vivobarefoot.com")) is None


# ── bron lezen: de gelinkte pagina wordt geatomiseerd ────────────────────────

def test_stage_leest_bron_en_zet_atomen_klaar(tmp_path, monkeypatch):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    monkeypatch.setattr(rp, "_atomen_uit_bron", lambda it: [
        {"content": "Eerste atomic insight uit het artikel", "subject": "", "provenance": "media"},
        {"content": "Tweede atomic insight uit het artikel", "reference": "10.1234/doi.5",
         "source_date": "2026-06-01"},
    ])
    bid, msg = rp.stage_signal(st, rid)
    assert bid and "bron gelezen" in msg and "2 voorstellen" in msg
    a1, a2 = st.staging.get(bid)["atoms"]
    assert a1["content"] == "Eerste atomic insight uit het artikel"
    assert a1["reference"] == _LINK                      # vangnet: artikel-link van het signaal
    assert a1["source_date"] == "2026-05-11"             # vangnet: publicatiedatum signaal
    assert a1["radar_rids"] == [rid] and a2["radar_rids"] == [rid]
    assert a2["reference"] == "10.1234/doi.5"            # eigen citaat van het atoom wint
    assert a2["source_date"] == "2026-06-01"


def test_commit_meerdere_atomen_markeert_signaal_eenmaal(tmp_path, monkeypatch):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    monkeypatch.setattr(rp, "_atomen_uit_bron", lambda it: [
        {"content": "Insight A uit de bron"}, {"content": "Insight B uit de bron"}])
    bid, _ = rp.stage_signal(st, rid)
    res = commit_batch(st.staging, bid, dd, radar=st.radar)
    assert res == (2, 0, 0)
    marker = cockpit2._Stores(dd).radar.get(rid)["promoted_atom_id"]
    assert marker == stable_id("Insight A uit de bron", "vivobarefoot.com")   # eerste = anker


# ── MECE: zelfde inzicht, andere bron → stapelen, nooit een tweede kaartje ───

def test_commit_zelfde_claim_andere_bron_stapelt(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.notes.add(Insight(id="atom_meceA", claim=_CONTENT, source="een-heel-andere-bron"))
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    res = commit_batch(st.staging, bid, dd, radar=st.radar)
    assert res == (0, 0, 1)                              # gekoppeld, geen duplicaat
    kaart = cockpit2._Stores(dd).notes.get("atom_meceA")
    assert kaart.grounding_count == 2                    # +1: er is een herkomst bij
    assert "vivobarefoot.com" in kaart.source
    assert len([x for x in cockpit2._Stores(dd).notes.all() if not x.archived]) == 1


def test_mece_hint_en_koppel_actie(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.notes.add(Insight(id="atom_meceB",
                         claim="Vivobarefoot lanceert een plantaardige sneaker in Europa",
                         source="elders"))
    rid = _approved(st)                                  # claim lijkt sterk, is niet exact gelijk
    bid, _ = stage_signal(st, rid)
    from nooch_village.views.kennisbank_staging import render_kennisbank_staging
    html = render_kennisbank_staging(st, bid, csrf_token="tok")
    assert "lijkt op bestaand kaartje" in html and "kb_stage_koppel" in html
    sid = st.staging.get(bid)["atoms"][0]["sid"]
    c = SimpleNamespace(nxt=f"/kennisbank/staging?batch={bid}", st=st, data_dir=dd,
                        username="guest",
                        g=lambda k, _m={"bid": bid, "sid": sid, "doel": "atom_meceB"}: _m.get(k, ""))
    nxt, msg = cockpit2._act_kb_stage_koppel(c)
    assert "extra bron" in msg
    kaart = st.notes.get("atom_meceB")
    assert kaart.grounding_count == 2 and "vivobarefoot.com" in kaart.source
    assert st.radar.get(rid)["promoted_atom_id"] == "atom_meceB"
    assert st.staging.get(bid)["atoms"] == []            # voorstel is uit de set


def test_multi_select_actie_zet_selectie_in_een_set(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    r1 = _approved(st)
    r2 = _approved(st, content="Tweede geselecteerde signaal", link="https://x.nl/q")
    c = SimpleNamespace(nxt="/signals", st=st, data_dir=dd, username="guest",
                        g=lambda k: "", form={"rid": [r1, r2]})
    nxt, msg = cockpit2._act_radar_promote_multi(c)
    assert nxt.startswith("/kennisbank/staging?batch=")
    assert "2 signaal" in msg
    bid = nxt.split("batch=")[1]
    rids = [a["radar_rids"][0] for a in st.staging.get(bid)["atoms"]]
    assert set(rids) == {r1, r2}


def test_staging_heeft_sleep_merge_interactie(tmp_path):
    """De staging-review gebruikt dezelfde merge-interactie als de statements-lijst:
    ⠿-handle, kaart-op-kaart slepen, modal met hoofdtekst-keuze (geen kop-formulier meer)."""
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    from nooch_village.views.kennisbank_staging import render_kennisbank_staging
    html = render_kennisbank_staging(st, bid, csrf_token="tok")
    assert "kn-handle" in html and "draggable='true'" in html
    assert "kb_stage_merge" in html and "kn-modal" in html
    assert "vink eerst" not in html                      # oude checkbox-interactie is weg
    assert "style=" not in html                          # ratchet
    # read-only (geen csrf): geen handle, geen modal
    kaal = render_kennisbank_staging(st, bid)
    assert "kn-handle" not in kaal and "kn-modal" not in kaal


# ── herkomst-verantwoording: LLM classificeert, mens kiest niet meer ─────────

def test_parse_intake_herkomst_veld():
    from nooch_village.kennisbank_intake import parse_intake
    rows = ('[{"content": "Externe survey toont X", "subject": "markt", '
            '"provenance": "survey", "herkomst": "extern, N=1.200", "source": "Bureau Y", '
            '"reference": "", "flags": [], "link_hints": []}]')
    (a,) = parse_intake(rows)
    assert a["provenance_note"] == "extern, N=1.200"
    # leeg of afwezig → None, nooit een gok
    rows2 = '[{"content": "Claim zonder verantwoording", "provenance": "media"}]'
    (b,) = parse_intake(rows2)
    assert b["provenance_note"] is None


def test_staging_kaart_zonder_pulldowns_met_provchip(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    rid = _approved(st)
    bid, _ = stage_signal(st, rid)
    from nooch_village.views.kennisbank_staging import render_kennisbank_staging
    html = render_kennisbank_staging(st, bid, csrf_token="tok")
    assert "<select name='subject'" not in html          # pulldown weg (slimme tags later)
    assert "<select name='provenance'" not in html       # LLM classificeert
    assert "kn-provchip" in html and "media" in html     # chip toont de LLM-keuze


def test_bewaar_wist_subject_en_provenance_niet(tmp_path):
    """Het formulier stuurt subject/provenance niet meer mee — een gewone tekst-bewaar mag
    de LLM-classificatie dan niet stilletjes wissen."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    bid = st.staging.create("website", "test", [
        {"content": "Voorstel met onderwerp", "subject": "markt", "provenance": "survey",
         "provenance_note": "extern, N=500"}])
    sid = st.staging.get(bid)["atoms"][0]["sid"]
    c = SimpleNamespace(nxt="x", st=st, data_dir=dd, username="guest",
                        form={"content": ["Aangepaste tekst"]},
                        g=lambda k, _m={"bid": bid, "sid": sid,
                                        "content": "Aangepaste tekst"}: _m.get(k, ""))
    cockpit2._act_kb_stage_edit(c)
    a = st.staging.get(bid)["atoms"][0]
    assert a["content"] == "Aangepaste tekst"
    assert a["subject"] == "markt" and a["provenance"] == "survey"
    assert a["provenance_note"] == "extern, N=500"


def test_provenance_note_reist_mee_naar_kaartje(tmp_path, monkeypatch):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid = _approved(st)
    monkeypatch.setattr(rp, "_atomen_uit_bron", lambda it: [
        {"content": "Expert zegt dat mycelium doorbreekt", "provenance": "expert_opinion",
         "provenance_note": "hoogleraar materiaalkunde, 40+ publicaties"}])
    bid, _ = rp.stage_signal(st, rid)
    commit_batch(st.staging, bid, dd, radar=st.radar)
    aid = stable_id("Expert zegt dat mycelium doorbreekt", "vivobarefoot.com")
    kaart = cockpit2._Stores(dd).notes.get(aid)
    assert kaart.provenance_note == "hoogleraar materiaalkunde, 40+ publicaties"


# ── mergen op /signals zelf: drag&drop, herkomst reist mee ───────────────────

def test_radar_merge_signalen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    r1 = _approved(st)
    r2 = _approved(st, content="Zelfde nieuws via ander kanaal",
                   source="ander-kanaal.nl", link="https://ander.nl/x")
    ok = st.radar.merge_signals(r1, r2, "De samengevoegde hoofdtekst")
    assert ok
    doel = st.radar.get(r1)
    assert doel["content"] == "De samengevoegde hoofdtekst"
    assert doel["merged_sources"][0]["source"] == "ander-kanaal.nl"
    assert st.radar.get(r2)["status"] == "samengevoegd"
    assert st.radar.get(r2)["merged_into"] == r1
    # het opgeslokte signaal is uit alle lijsten
    assert r2 not in [it["id"] for it in st.radar.all_approved()]
    # guards: nogmaals mergen met een al-samengevoegd signaal faalt netjes
    assert st.radar.merge_signals(r1, r2, "x") is False
    assert st.radar.merge_signals(r1, r1, "x") is False


def test_merged_sources_stapelen_op_kaartje(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    r1 = _approved(st)
    r2 = _approved(st, content="Zelfde nieuws elders", source="ander-kanaal.nl",
                   link="https://ander.nl/x")
    st.radar.merge_signals(r1, r2, "Samengevoegde tekst over de sneaker")
    bid, _ = stage_signal(st, r1)
    commit_batch(st.staging, bid, dd, radar=st.radar)
    aid = stable_id("Samengevoegde tekst over de sneaker", "vivobarefoot.com")
    kaart = cockpit2._Stores(dd).notes.get(aid)
    assert "ander-kanaal.nl" in kaart.source              # herkomst van allebei
    assert "ander.nl/x" in (kaart.reference or "")
    assert kaart.grounding_count >= 2


def test_signals_pagina_heeft_sleep_merge(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    _approved(st)
    _approved(st, content="Tweede", link="https://x.nl/2")
    from nooch_village.views.signals import render_signals
    html = render_signals(st, csrf_token="tok")
    assert "kn-handle" in html and "data-rid=" in html
    assert "radar_merge" in html and "kn-modal" in html
    kaal = render_signals(st)
    assert "kn-handle" not in kaal and "radar_merge" not in kaal
