"""Een gearchiveerd artefact terughalen (1 oktober 2026): de tegenhanger van `artefact_archive`.

Aanleiding: drie materiaalpagina's waren gearchiveerd en het BOM-scherm kon er dus niet naar
linken. Terughalen kon alleen nog met een directe JSON-edit — zonder historie, zonder wie of waarom.
"""
from __future__ import annotations

import json
import os

import pytest

from nooch_village import cockpit2, wiki

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _changelog(dd):
    pad = os.path.join(dd, "artefact_changelog.jsonl")
    return [json.loads(r) for r in open(pad, encoding="utf-8") if r.strip()] if os.path.exists(pad) else []


def test_de_store_haalt_terug_met_een_versie_entry(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    a = st.att.add(OWNER, "note", title="Pliant", body="tekst")
    st.att.archive(a.id)
    terug = st.att.unarchive(a.id, change_note="uit het archief gehaald: test")
    assert terug.status == "active"
    assert terug.versions[-1]["change_note"] == "uit het archief gehaald: test"
    assert terug.body == "tekst"                                   # inhoud onaangeroerd
    assert a.id in {p.id for p in wiki.paginas(st.att)}            # weer een gewone pagina


def test_een_actief_artefact_blijft_ongemoeid(tmp_path):
    """Geen lege versie-entry voor een niet-gebeurtenis."""
    st = cockpit2._Stores(_dd(tmp_path))
    a = st.att.add(OWNER, "note", title="Pliant")
    voor = len(st.att.get(a.id).versions)
    assert st.att.unarchive(a.id) is None
    assert len(st.att.get(a.id).versions) == voor
    assert st.att.unarchive("NOTE-BESTAAT-NIET") is None


def test_de_route_logt_wie_en_waarom(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="HyphaLite")
    cockpit2.dispatch(dd, "artefact_archive", {"aid": [a.id], "next": ["/"]}, username="guest")
    _nxt, msg = cockpit2.dispatch(dd, "artefact_unarchive",
                                  {"aid": [a.id], "reden": ["voor de BOM-koppeling"], "next": ["/"]},
                                  username="guest")
    assert "restored" in msg
    terug = cockpit2._Stores(dd).att.get(a.id)
    assert terug.status == "active"
    assert terug.versions[-1]["change_note"] == "uit het archief gehaald: voor de BOM-koppeling"
    assert [e["action"] for e in _changelog(dd)][-2:] == ["archive", "unarchive"]


def test_niet_gearchiveerd_zegt_dat_en_doet_niets(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p")
    _nxt, msg = cockpit2.dispatch(dd, "artefact_unarchive", {"aid": [a.id], "next": ["/"]},
                                  username="guest")
    assert "not archived" in msg
    assert _changelog(dd) == [] or _changelog(dd)[-1]["action"] != "unarchive"


def test_dezelfde_poort_als_archiveren(tmp_path):
    """Wie niet mag archiveren, mag ook niet terughalen: `Materials` hoort bij `creator_of_shoes`."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="p", domain="Materials")
    st.att.archive(a.id)
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "artefact_unarchive", {"aid": [a.id], "next": ["/"]},
                          username="bob@nooch.earth")
    assert cockpit2._Stores(dd).att.get(a.id).status == "archived"
