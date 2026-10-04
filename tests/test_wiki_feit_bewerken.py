"""Een feit bewerken op zijn plek, bewijs koppelen, en `attested` (besluit Stefan, 4 oktober 2026)."""
from __future__ import annotations

import json
import os

from nooch_village import cockpit2, wiki
from nooch_village.views.wiki import render_pagina

ROL = "mother_earth__nooch__creator_of_shoes"          # houdt het domein Materials
IK = "b@t.nl"
ANDER = "x@t.nl"


def _dorp(tmp_path, feiten):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Tess Beheerder", IK).id)
    st.people.add("Iemand Anders", ANDER)
    # MET DOMEIN: een pagina zonder domein mag elke herkende persoon bewerken (sinds 26 september);
    # alleen een domein schermt hem af, en dat is wat de weiger-toets hieronder nodig heeft.
    a = st.att.add(ROL, "note", title="NFW", body="## Company certification\nx", domain="Materials",
                   meta={"feiten": feiten})
    return dd, a.id


def _doe(dd, actie, wie=IK, **v):
    return cockpit2.dispatch(dd, actie, {**{k: [x] for k, x in v.items()}, "next": ["/"]}, username=wie)[1]


def _feiten(dd, aid):
    return wiki.feiten(cockpit2._Stores(dd).att.get(aid))


USDA = wiki.maak_feit("USDA lists Pliant PCS as 100% biobased.", soort="bron",
                      url="https://www.biopreferred.gov/x")


def test_een_citaat_toevoegen_houdt_het_id_en_reset_de_check(tmp_path):
    f = dict(USDA, grond={**USDA["grond"], "check": {"op": "2026-10-01", "gevonden": None}})
    dd, aid = _dorp(tmp_path, [f])
    msg = _doe(dd, "pagina_feit_edit", aid=aid, fid=f["id"], tekst=f["tekst"], soort="bron",
               url=f["grond"]["url"], citaat="Biobased Content: 100%", ref="")
    assert not cockpit2.is_weigering(msg), msg
    [nu] = _feiten(dd, aid)
    assert nu["id"] == f["id"] and nu["grond"]["citaat"] == "Biobased Content: 100%"
    assert "check" not in nu["grond"]                     # nieuw citaat → opnieuw te checken
    assert wiki.grond_status(nu)["label"] == "not yet checked"


def test_ongewijzigde_bron_houdt_zijn_check(tmp_path):
    f = wiki.maak_feit("x", soort="bron", url="https://e.org", citaat="een citaat van lengte")
    f["grond"]["check"] = {"op": "2026-10-01", "gevonden": True}
    dd, aid = _dorp(tmp_path, [f])
    _doe(dd, "pagina_feit_edit", aid=aid, fid=f["id"], tekst="x, scherper geformuleerd", soort="bron",
         url="https://e.org", citaat="een citaat van lengte", ref="")
    assert _feiten(dd, aid)[0]["grond"]["check"]["gevonden"] is True


def test_bewerken_raakt_het_goede_feit_ook_als_er_intussen_een_weg_is(tmp_path):
    a1, a2 = wiki.maak_feit("eerste"), wiki.maak_feit("tweede")
    dd, aid = _dorp(tmp_path, [a1, a2])
    _doe(dd, "pagina_feit_del", aid=aid, fid=a1["id"])
    _doe(dd, "pagina_feit_edit", aid=aid, fid=a2["id"], tekst="tweede, bewerkt", soort="")
    assert [f["tekst"] for f in _feiten(dd, aid)] == ["tweede, bewerkt"]


def test_een_oud_feit_zonder_id_is_ook_te_bewerken(tmp_path):
    oud = {"tekst": "oud feit", "grond": {}}                          # van vóór 4 oktober
    dd, aid = _dorp(tmp_path, [oud])
    _doe(dd, "pagina_feit_edit", aid=aid, fid=wiki.feit_id(oud), tekst="oud feit, bewerkt", soort="")
    assert _feiten(dd, aid)[0]["tekst"] == "oud feit, bewerkt"


def test_een_onbekend_feit_wordt_niet_geraden(tmp_path):
    dd, aid = _dorp(tmp_path, [wiki.maak_feit("a")])
    msg = _doe(dd, "pagina_feit_edit", aid=aid, fid="bestaat-niet", tekst="b", soort="")
    assert cockpit2.is_weigering(msg) and _feiten(dd, aid)[0]["tekst"] == "a"


def test_bewijs_koppelen_aan_een_bestaand_feit(tmp_path):
    """Het pakbon-geval: het feit bestaat al ("no source"), het bestand komt erbij."""
    pakbon = wiki.maak_feit("Pliant outsole weighs 48 g", soort="bron")
    dd, aid = _dorp(tmp_path, [pakbon])
    map_ = os.path.join(dd, "attachments", "wiki", aid)
    os.makedirs(map_)
    open(os.path.join(map_, "ab12cd34_pakbon.pdf"), "wb").write(b"%PDF")
    _doe(dd, "pagina_feit_edit", aid=aid, fid=pakbon["id"], tekst=pakbon["tekst"], soort="bron",
         url="on file: ab12cd34_pakbon.pdf")
    g = _feiten(dd, aid)[0]["grond"]
    assert g["soort"] == "document" and g["url"] == f"/wiki-bestand/{aid}/ab12cd34_pakbon.pdf"


def test_attested_neemt_de_naam_van_wie_ingelogd_is_niet_uit_het_formulier(tmp_path):
    f = wiki.maak_feit("Pliant is made in Vietnam")
    dd, aid = _dorp(tmp_path, [f])
    _doe(dd, "pagina_feit_edit", aid=aid, fid=f["id"], tekst=f["tekst"], soort="attested",
         ref="Iemand Anders")                                # een andere naam typen helpt niet
    g = _feiten(dd, aid)[0]["grond"]
    assert g["soort"] == "attested" and g["ref"] == "Tess Beheerder" and g["op"]
    label = wiki.grond_status(_feiten(dd, aid)[0])["label"]
    assert label.startswith("attested by Tess Beheerder, ")


def test_attested_in_bulk_import_is_van_wie_importeert(tmp_path):
    dd, aid = _dorp(tmp_path, [])
    feit = {"Text": "Made in Vietnam", "Type": "attested", "Ref": "iemand anders"}
    cockpit2.dispatch(dd, "pagina_bulk_import_facts",
                      {"aid": [aid], "facts_json": [json.dumps([feit])], "next": ["/"]}, username=IK)
    assert _feiten(dd, aid)[0]["grond"]["ref"] == "Tess Beheerder"


def test_wie_niet_mag_bewerken_kan_dat_ook_niet_via_de_actie(tmp_path):
    f = wiki.maak_feit("a")
    dd, aid = _dorp(tmp_path, [f])
    try:
        _doe(dd, "pagina_feit_edit", wie=ANDER, aid=aid, fid=f["id"], tekst="b", soort="")
    except cockpit2.Forbidden:
        pass
    assert _feiten(dd, aid)[0]["tekst"] == "a"


def test_het_feit_is_klikbaar_met_een_upload_formulier_voor_de_eigenaar(tmp_path):
    f = wiki.maak_feit("Pliant outsole weighs 48 g", sectie="Company certification")
    dd, aid = _dorp(tmp_path, [f])
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="TOK", username=IK)
    assert "enctype='multipart/form-data'" in h and "value='pagina_feit_edit'" in h
    assert "name='file'" in h and "at least 12 characters" in h
    h2 = render_pagina(cockpit2._Stores(dd), aid, csrf_token="TOK", username=ANDER)
    assert "value='pagina_feit_edit'" not in h2


def test_een_herimport_met_sectie_is_een_ander_feit_dan_het_oude(tmp_path):
    """Prod, 4 oktober 2026: vijf feiten stonden twee keer — oud zonder sectie, herimport mét. Het
    afgeleide id keek niet naar de sectie, dus bewerken van het nieuwe exemplaar raakte het oude."""
    oud = {"tekst": "RISK: wind-down", "grond": {"soort": "bron", "ref": "", "citaat": "", "url": "https://t"}}
    nieuw = dict(oud, sectie="Risk signal")
    assert wiki.feit_id(oud) != wiki.feit_id(nieuw)
    dd, aid = _dorp(tmp_path, [oud, nieuw])
    _doe(dd, "pagina_feit_edit", aid=aid, fid=wiki.feit_id(nieuw), tekst="RISK: wind-down, bewerkt",
         soort="bron", url="https://t", sectie="Risk signal")
    assert [f["tekst"] for f in _feiten(dd, aid)] == ["RISK: wind-down", "RISK: wind-down, bewerkt"]


def test_na_een_schrijfactie_heeft_elk_oud_feit_een_vast_id(tmp_path):
    oud = {"tekst": "oud", "grond": {}}
    afgeleid = wiki.feit_id(oud)
    dd, aid = _dorp(tmp_path, [oud, wiki.maak_feit("ander")])
    _doe(dd, "pagina_feit_del", aid=aid, fid=_feiten(dd, aid)[1]["id"])
    [blijft] = _feiten(dd, aid)
    assert blijft["id"] == afgeleid                     # vastgezet, zelfde id als op het scherm
