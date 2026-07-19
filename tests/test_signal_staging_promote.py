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

from nooch_village import cockpit2
from nooch_village.insight import Insight
from nooch_village.kennisbank_intake import stable_id
from nooch_village.kennisbank_staging import commit_batch
from nooch_village.radar_promote import stage_signal

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
