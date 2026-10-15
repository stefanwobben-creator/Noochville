"""De antwoordregel per vraag (besluit Stefan, 15 oktober 2026).

BESTAAN (plastic, animal, cert bij materiaal en leverancier): één gecheckte yes is genoeg; een
gecheckte no ernaast is een zichtbare notitie, geen conflict. "No" alleen uit een door een mens
gecheckt feit met antwoord no, zonder enige yes. EENDUIDIG (biobased, loc, own, chem, labor): yes
tegen no blijft een conflict. Getalvragen ongewijzigd. Ongecheckt of zonder antwoord telt nooit.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, wiki_dekking as wd

from tests.test_w1_antwoorden import _cel, _check, _feit, _pagina


def test_de_regels_staan_in_de_vragenconstante():
    regels = {(s, v["k"]): v["regel"] for s in wd.VRAGEN for v in wd.vragen(s)}
    for k in (("materiaal", "plastic"), ("materiaal", "animal"), ("materiaal", "cert"),
              ("leverancier", "cert")):
        assert regels[k] == wd.BESTAAN, k
    for k in (("materiaal", "biobased"), ("materiaal", "chem"), ("leverancier", "loc"),
              ("leverancier", "own"), ("leverancier", "labor")):
        assert regels[k] == wd.EENDUIDIG, k
    for k in (("materiaal", "co2"), ("materiaal", "water"), ("leverancier", "price")):
        assert regels[k] == "", k


def test_bestaan_een_yes_is_genoeg_en_de_no_wordt_een_notitie(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "FSC yes"), _feit("F2", "ISO yes"), _feit("F3", "GRS expired")])
    _check(dd, aid, "F1", cert="yes")
    _check(dd, aid, "F2", cert="yes")
    _check(dd, aid, "F3", cert="no")
    c = _cel(dd, "cert")
    assert c["status"] == wd.GECHECKT and c["antwoord"] == "yes" and c["nee_notitie"] == 1
    from nooch_village.views.wiki import _vragen_sectie
    st = cockpit2._Stores(dd)
    blok = _vragen_sectie(st, st.att.get(aid), "", False).split("id='vraag-cert'", 1)[1]
    assert "1 checked fact says no — for this question one checked yes is enough." in blok
    from nooch_village.views.bom import render_bom
    assert "1 says no" in render_bom(st, username="guest")


def test_bestaan_no_alleen_uit_een_gecheckte_no_zonder_yes(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "No plastic"), _feit("F2", "Unclear")])
    _check(dd, aid, "F1", plastic="no")                     # F2 blijft ongecheckt
    c = _cel(dd, "plastic")
    assert c["status"] == wd.GECHECKT and c["antwoord"] == "no" and "nee_notitie" not in c


def test_onbekend_is_nooit_nee(tmp_path):
    """Ongecheckt, of gecheckt zonder antwoord op deze vraag: de cel blijft open of ongecheckt."""
    dd, aid = _pagina(tmp_path, [_feit("F1", "Says nothing about plastic")])
    _check(dd, aid, "F1", biobased="yes")                   # antwoord op een ándere vraag
    c = _cel(dd, "plastic")
    assert c["status"] != wd.GECHECKT and c.get("antwoord") != "no"


@pytest.mark.parametrize("k", ["biobased", "chem"])
def test_eenduidig_blijft_een_conflict(tmp_path, k):
    dd, aid = _pagina(tmp_path, [_feit("F1", "a"), _feit("F2", "b")])
    _check(dd, aid, "F1", **{k: "yes"})
    _check(dd, aid, "F2", **{k: "no"})
    assert _cel(dd, k)["status"] == wd.CONFLICT
