"""Het domein Materials op de materiaal- en leverancierpagina's van /bom (10 oktober 2026)."""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, wiki_seed

OWNER = "mother_earth__nooch__creator_of_shoes"          # houdt `Materials` in het testdorp


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mat = st.att.add(OWNER, "note", title="Pliant", body="x")
    lev = st.att.add(OWNER, "note", title="NFW", body="x")
    al = st.att.add(OWNER, "note", title="HyphaLite", body="x", domain="Andere zaak")
    los = st.att.add(OWNER, "note", title="Iets anders", body="x")
    st.bom_materialen.zet("Outsole", "Pliant")
    st.bom_materialen.zet("Vamp", "HyphaLite")
    st.bom_leveranciers.zet("Pliant", "NFW")
    st.people.add("Buiten", "buiten@t.nl")
    return dd, mat.id, lev.id, al.id, los.id


def _run(dd, **kw):
    st = cockpit2._Stores(dd)
    return wiki_seed.domein_zetten(st.att, st.records, st.bom_materialen, st.bom_varianten,
                                   st.bom_leveranciers, **kw)


def test_dry_run_dan_apply_en_bestaand_domein_blijft(tmp_path):
    dd, mat, lev, al, los = _dorp(tmp_path)
    r = _run(dd)
    assert r["domein_bestaat"] and {i for i, _t in r["zetten"]} == {mat, lev}
    assert [i for i, _t, _d in r["al_domein"]] == [al]
    assert cockpit2._Stores(dd).att.get(mat).domain == ""                  # dry-run schrijft niets
    _run(dd, apply=True)
    st = cockpit2._Stores(dd)
    assert st.att.get(mat).domain == "Materials" and st.att.get(lev).domain == "Materials"
    assert st.att.get(al).domain == "Andere zaak" and st.att.get(los).domain == ""
    assert _run(dd)["zetten"] == []                                          # idempotent


def test_een_onbekend_domein_doet_niets(tmp_path):
    dd, mat, *_ = _dorp(tmp_path)
    r = _run(dd, domein="Bestaat niet", apply=True)
    assert not r["domein_bestaat"] and r["zetten"] == []
    assert cockpit2._Stores(dd).att.get(mat).domain == ""
    assert "governance decision" in wiki_seed.domein_zetten_tekst(r)


def test_na_het_domein_mag_alleen_de_houder_uitstellen(tmp_path):
    dd, mat, *_ = _dorp(tmp_path)
    form = {"aid": [mat], "soort": ["materiaal"], "k": ["chem"], "tot": ["2026-12-31"], "next": ["/"]}
    assert "✓" in cockpit2.dispatch(dd, "vraag_uitstel", form, username="buiten@t.nl")[1]   # nog geen domein
    _run(dd, apply=True)
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "vraag_uitstel", dict(form, k=["plastic"]), username="buiten@t.nl")
