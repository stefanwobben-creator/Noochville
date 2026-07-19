"""Wekelijkse tag-onderhoudslus: LLM-voorstellen, mens keurt, kaartjes worden bijgewerkt.

Dekt: telling (zonder hint:* en verwijderde kaartjes); prompt/parser fail-closed met
beschermde tags; store-dedupe (ook tegen afgewezen); week-marker; doorvoeren werkt alle
kaartjes bij (retag: merge/weg/abstractie, dedupe binnen een kaartje); de review-route en
de besluit-actie; Oracle-verwijzing bij open voorstellen.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import cockpit2
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore
from nooch_village.tag_onderhoud import (TagVoorstellenStore, build_tag_prompt,
                                         draai_onderhoud, parse_tag_voorstellen,
                                         tag_telling, voer_voorstel_uit)


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _vul(notes: NotesStore) -> None:
    notes.add(Insight(id="t1", claim="A", source="s", tags=["mycelium-leer", "signal"]))
    notes.add(Insight(id="t2", claim="B", source="s", tags=["myceliumleer", "hint:leer-x"]))
    notes.add(Insight(id="t3", claim="C", source="s", tags=["eenmalig-dingetje"]))
    notes.add(Insight(id="t4", claim="D", source="s", tags=["mycelium-leer", "myceliumleer"]))


def test_telling_en_prompt(tmp_path):
    notes = NotesStore(f"{tmp_path}/notes.json")
    _vul(notes)
    notes.archive("t3")
    tel = tag_telling(notes)
    assert tel == {"mycelium-leer": 2, "signal": 1, "myceliumleer": 2}   # hint:* en verwijderd niet
    p = build_tag_prompt(tel)
    assert "mycelium-leer (2)" in p and "signal" in p                  # beschermd genoemd
    assert "hint:" not in p


def test_parser_valideert_beschermd_en_vormen():
    tel = {"mycelium-leer": 2, "myceliumleer": 2, "signal": 5, "x": 1}
    raw = json.dumps([
        {"actie": "merge", "van": ["myceliumleer"], "naar": "mycelium-leer", "waarom": "spelling"},
        {"actie": "weg", "van": ["signal"], "naar": ""},                 # beschermd → weg
        {"actie": "weg", "van": ["x"], "naar": "genegeerd"},             # weg: naar leeg
        {"actie": "merge", "van": ["x"], "naar": "x"},                   # naar in van → weg
        {"actie": "raar", "van": ["x"], "naar": "y"},                    # onbekende actie
        {"actie": "abstractie", "van": ["bestaat-niet"], "naar": "y"},   # onbekende tag
    ])
    uit = parse_tag_voorstellen(raw, tel)
    assert [v["actie"] for v in uit] == ["merge", "weg"]
    assert uit[1]["naar"] == ""
    assert parse_tag_voorstellen(None, tel) == []
    assert parse_tag_voorstellen("geen json", tel) == []


def test_store_dedupe_ook_tegen_afgewezen(tmp_path):
    store = TagVoorstellenStore(f"{tmp_path}/tv.json")
    v = {"actie": "merge", "van": ["a"], "naar": "b", "waarom": ""}
    assert store.voeg_toe([v]) == 1
    (open_v,) = store.open_voorstellen()
    store.besluit(open_v["id"], "afgewezen")
    assert store.voeg_toe([v]) == 0                       # afgewezen komt niet terug
    assert store.open_voorstellen() == []


def test_week_marker(tmp_path):
    dd = str(tmp_path)
    NotesStore(f"{dd}/notes.json").add(Insight(id="t1", claim="A", source="s", tags=["x"]))
    fake = lambda p: json.dumps([{"actie": "weg", "van": ["x"], "naar": ""}])
    r1 = draai_onderhoud(dd, reason_fn=fake, force=True)
    assert r1["gedraaid"] and r1["nieuw"] == 1
    r2 = draai_onderhoud(dd, reason_fn=fake)              # zelfde week → niet draaien
    assert r2["gedraaid"] is False


def test_doorvoeren_werkt_alle_kaartjes_bij(tmp_path):
    notes = NotesStore(f"{tmp_path}/notes.json")
    _vul(notes)
    v = {"actie": "merge", "van": ["myceliumleer"], "naar": "mycelium-leer"}
    n = voer_voorstel_uit(notes, v)
    assert n == 2
    vers = NotesStore(f"{tmp_path}/notes.json")
    assert vers.get("t2").tags == ["mycelium-leer", "hint:leer-x"]
    assert vers.get("t4").tags == ["mycelium-leer"]          # dedupe binnen het kaartje
    assert voer_voorstel_uit(notes, {"actie": "weg", "van": ["eenmalig-dingetje"],
                                     "naar": ""}) == 1
    assert NotesStore(f"{tmp_path}/notes.json").get("t3").tags == []


def test_besluit_actie_en_route(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _vul(st.notes)
    store = TagVoorstellenStore(f"{dd}/tag_voorstellen.json")
    store.voeg_toe([{"actie": "merge", "van": ["myceliumleer"], "naar": "mycelium-leer",
                     "waarom": "spelling"}])
    (v,) = store.open_voorstellen()
    from nooch_village.views.tag_onderhoud import render_tag_onderhoud
    html = render_tag_onderhoud(st, csrf_token="tok")
    assert "myceliumleer" in html and "tag_voorstel_besluit" in html and "spelling" in html
    assert "style=" not in html                           # ratchet
    c = SimpleNamespace(nxt="/kennisbank/tags", st=st, data_dir=dd, username="guest",
                        g=lambda k, _m={"vid": v["id"], "keuze": "doorvoeren"}: _m.get(k, ""))
    nxt, msg = cockpit2._act_tag_voorstel_besluit(c)
    assert "doorgevoerd op 2" in msg
    assert TagVoorstellenStore(f"{dd}/tag_voorstellen.json").open_voorstellen() == []
    assert "mycelium-leer" in cockpit2._Stores(dd).notes.get("t2").tags


def test_oracle_toont_verwijzing_bij_open_voorstellen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _vul(st.notes)
    TagVoorstellenStore(f"{dd}/tag_voorstellen.json").voeg_toe(
        [{"actie": "weg", "van": ["eenmalig-dingetje"], "naar": ""}])
    from nooch_village.views.kennisbank import render_kennisbank
    html = render_kennisbank(st, csrf_token="tok")
    assert "/kennisbank/tags" in html and "tag-voorstel" in html
