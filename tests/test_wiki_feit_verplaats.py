"""`pagina_feit_verplaats`: een feit naar een ander kopje of binnen een kopje (5 oktober 2026)."""
from __future__ import annotations

from nooch_village import cockpit2, wiki

ROL = "mother_earth__nooch__creator_of_shoes"
IK, ANDER = "b@t.nl", "x@t.nl"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Tess Beheerder", IK).id)
    st.people.add("Iemand Anders", ANDER)
    fs = [wiki.maak_feit("a", sectie="Kop"), wiki.maak_feit("b", sectie="Kop"),
          wiki.maak_feit("c")]
    fs[0]["grond"] = {"soort": "bron", "ref": "", "citaat": "een citaat", "url": "https://x",
                      "check": {"op": "2026-10-01", "gevonden": True}}
    a = st.att.add(ROL, "note", title="P", body="## Kop\n## Ander", domain="Materials",
                   meta={"feiten": fs})
    return dd, a.id, fs


def _doe(dd, wie=IK, **v):
    return cockpit2.dispatch(dd, "pagina_feit_verplaats",
                             {**{k: [x] for k, x in v.items()}, "next": ["/"]}, username=wie)[1]


def _lijst(dd, aid):
    return [(f["tekst"], f.get("sectie", "")) for f in wiki.feiten(cockpit2._Stores(dd).att.get(aid))]


def test_naar_een_ander_kopje(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    assert not cockpit2.is_weigering(_doe(dd, aid=aid, fid=fs[0]["id"], sectie="Ander", voor_fid=""))
    assert ("a", "Ander") in _lijst(dd, aid)


def test_binnen_een_kopje_van_plek_wisselen(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    _doe(dd, aid=aid, fid=fs[1]["id"], sectie="Kop", voor_fid=fs[0]["id"])
    assert [t for t, s in _lijst(dd, aid) if s == "Kop"] == ["b", "a"]


def test_naar_other_facts_is_een_lege_sectie(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    _doe(dd, aid=aid, fid=fs[0]["id"], sectie="", voor_fid="")
    assert ("a", "") in _lijst(dd, aid)


def test_achteraan_in_de_sectie_zonder_voor(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    _doe(dd, aid=aid, fid=fs[2]["id"], sectie="Kop", voor_fid="")
    assert [t for t, s in _lijst(dd, aid) if s == "Kop"] == ["a", "b", "c"]


def test_id_grond_en_check_blijven(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    _doe(dd, aid=aid, fid=fs[0]["id"], sectie="Ander", voor_fid="")
    a = next(f for f in wiki.feiten(cockpit2._Stores(dd).att.get(aid)) if f["tekst"] == "a")
    assert a["id"] == fs[0]["id"] and a["grond"]["check"]["gevonden"] is True


def test_zonder_bewerkrecht_weigert_de_server(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    try:
        _doe(dd, wie=ANDER, aid=aid, fid=fs[0]["id"], sectie="Ander", voor_fid="")
    except cockpit2.Forbidden:
        pass
    assert ("a", "Kop") in _lijst(dd, aid)


def test_de_versleping_is_een_paginaversie(tmp_path):
    dd, aid, fs = _dorp(tmp_path)
    _doe(dd, aid=aid, fid=fs[0]["id"], sectie="Ander", voor_fid="")
    v = cockpit2._Stores(dd).att.get(aid).versions[-1]
    assert v["change_note"].startswith("fact moved: a")
