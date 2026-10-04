"""Item 9 en 10 van de layout-instructie (4 oktober 2026).

9.  Een materiaal-/leverancierpagina onthoudt haar /bom-naam (`wiki.BOM_NAMEN`): een hernoeming
    breekt de koppeling niet meer.
10. "on file, not public": een feit dat naar een document op déze pagina wijst.
"""
from __future__ import annotations

import json
import os

from nooch_village import cockpit2, wiki, wiki_seed
from nooch_village.views.wiki import render_pagina

ROL = "mother_earth__nooch__website_developer"
IK = "b@t.nl"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Beheerder", IK).id)
    return dd, st


# ══ 9 ═══════════════════════════════════════════════════════════════════════
def test_een_hernoemde_leverancier_blijft_gekoppeld(tmp_path):
    dd, st = _dorp(tmp_path)
    mat = st.att.add(ROL, "note", title="Pliant PCS", body="x")
    lev = st.att.add(ROL, "note", title="NFW", body="x")
    st.bom_materialen.zet("Outsole", "Pliant PCS")
    st.bom_leveranciers.zet("Pliant PCS", "NFW")
    rapport = wiki_seed.bom_sleutels(st.att, st.bom_materialen, st.bom_varianten, st.bom_leveranciers,
                                     apply=True)
    assert {r["titel"] for r in rapport if r["actie"] == "set"} == {"Pliant PCS", "NFW"}
    st = cockpit2._Stores(dd)
    st.att.update(lev.id, title="Natural Fiber Welding (NFW)")          # de hernoeming
    st = cockpit2._Stores(dd)
    h = render_pagina(st, mat.id, csrf_token="t", username=IK)
    blok = h[h.index("From the BOM"):]
    assert f"/pagina?id={lev.id}" in blok and "Natural Fiber Welding (NFW)" in blok
    # en de leverancierpagina vindt zijn materiaal nog
    h2 = render_pagina(st, lev.id, csrf_token="t", username=IK)
    assert f"/pagina?id={mat.id}" in h2[h2.index("From the BOM"):]


def test_bom_sleutels_meldt_een_naam_zonder_pagina_en_schrijft_alleen_met_apply(tmp_path):
    dd, st = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="NFW", body="x")
    st.bom_leveranciers.zet("Pliant", "NFW")
    rapport = wiki_seed.bom_sleutels(st.att, st.bom_materialen, st.bom_varianten, st.bom_leveranciers)
    assert any(r["actie"] == "no page" and r["naam"] == "Pliant" for r in rapport)
    assert wiki.bom_namen(cockpit2._Stores(dd).att.get(a.id)) == []           # dry-run


def test_de_zaaier_geeft_een_nieuwe_pagina_haar_bom_naam(tmp_path):
    dd, st = _dorp(tmp_path)
    wiki_seed.zaai(st.att, st.records, paginas=[{"titel": "HyphaLite", "body": "x"}],
                   eigenaar=ROL, soort="materiaal", apply=True)
    a = next(p for p in cockpit2._Stores(dd).att.by_kind("note") if p.title == "HyphaLite")
    assert wiki.bom_namen(a) == ["HyphaLite"]


# ══ 10 ══════════════════════════════════════════════════════════════════════
def _upload(dd, aid, naam):
    map_ = os.path.join(dd, "attachments", "wiki", aid)
    os.makedirs(map_, exist_ok=True)
    opgeslagen = "ab12cd34_" + naam.replace(" ", "_")
    open(os.path.join(map_, opgeslagen), "wb").write(b"%PDF")
    return opgeslagen


def _importeer(dd, aid, url):
    feit = {"Text": "Lab measured 100% biobased carbon.", "Type": "source",
            "Ref": "UGA CAIS report 2023", "Quote": "", "URL": url}
    return cockpit2.dispatch(dd, "pagina_bulk_import_facts",
                             {"aid": [aid], "facts_json": [json.dumps([feit])], "next": ["/"]},
                             username=IK)[1]


def test_on_file_wijst_naar_het_document_op_deze_pagina(tmp_path):
    dd, st = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="NFW", body="x")
    opgeslagen = _upload(dd, a.id, "NFW D6866.pdf")
    msg = _importeer(dd, a.id, "on file: NFW D6866.pdf")
    assert "warning" not in msg, msg
    f = wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]
    assert f["grond"]["soort"] == "document" and f["grond"]["ref"] == opgeslagen
    assert f["grond"]["url"] == f"/wiki-bestand/{a.id}/{opgeslagen}"
    h = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username=IK)
    assert "on file, not public" in h
    assert not [i for i in __import__("nooch_village.wiki_bronnen", fromlist=["x"]).te_checken(
        cockpit2._Stores(dd).att.get(a.id))]                         # de bron-check slaat hem over


def test_on_file_zonder_upload_zegt_wat_er_moet_gebeuren(tmp_path):
    dd, st = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="NFW", body="x")
    msg = _importeer(dd, a.id, "on file: niet geupload.pdf")
    assert "not uploaded on this page" in msg, msg
    f = wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]
    assert f["grond"]["soort"] == "bron" and f["grond"]["url"] == ""


def test_een_verdwenen_bestand_wordt_no_source(tmp_path):
    dd, st = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="NFW", body="x")
    opgeslagen = _upload(dd, a.id, "rapport.pdf")
    _importeer(dd, a.id, "on file: rapport.pdf")
    os.remove(os.path.join(dd, "attachments", "wiki", a.id, opgeslagen))
    h = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username=IK)
    # Op de CHIP (niet in de keuzelijst van het bewerkformulier, waar de soort ook zo heet).
    assert "no source</span>" in h or "no source<" in h
    assert "on file, not public</a>" not in h
