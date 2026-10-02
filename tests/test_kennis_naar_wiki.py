"""Kennis van een project naar de wiki, in twee losse stappen (29 september 2026).

DE SPLITSING IS HET ONTWERP, en niet een implementatiedetail:

  1. EEN PROJECT LEVERT EEN FEIT. Eén regel, herleidbaar, met een klikbare bron — en zonder model.
     Er valt niets te formuleren wat het rapport niet al zegt.
  2. EEN PAGINA KRIJGT EEN ALINEA, uit AL haar feiten samen, en alleen als een mens erom vraagt.
     Dat is de enige plek in deze scope waar een model schrijft, en hij slaat niets op: het
     voorstel landt in het gewone bewerkveld en wacht daar op Save.

Zou stap 1 al een alinea schrijven, dan staat er proza op een pagina dat niemand heeft nagelezen en
dat niet meer te herleiden is tot waar het vandaan komt. Zou stap 2 automatisch opslaan, dan
schrijft een model over iemands pagina heen.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, wiki
from nooch_village.views.rapport import render_projectrapport
from nooch_village.views.wiki import bijna_gelijke_paginas, dubbele_namen_hint, render_pagina

IK = "b@t.nl"
ROL = "mother_earth__nooch__website_developer"

RAPPORT = """# Barefoot-zolen

## Result
**Achieved.** The supplier confirmed a natural-rubber outsole at 4mm.

## Learnings
Ask for the datasheet earlier next time.
"""


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Beheerder", IK)
    st.assign.assign(ROL, "person", mens.id)
    pagina = st.att.add(ROL, "note", title="Outsole materials", body="Wat we weten.")
    pid = st.projects.create(ROL, "Outsole-onderzoek", "human", status="running")
    st.projects.complete(pid, "behaald", door=mens.id)
    st.project_docs.write(pid, RAPPORT)
    return dd, cockpit2._Stores(dd), pagina.id, pid


def _doe(dd, actie, **velden):
    velden = {"csrf": "T", "next": "/", **velden}
    return cockpit2.dispatch(dd, actie, {k: [v] for k, v in velden.items()}, username=IK)


def _feiten(dd, aid):
    return wiki.feiten(cockpit2._Stores(dd).att.get(aid))


# ══ 1. Het rapport levert één FEIT ═══════════════════════════════════════════
def test_de_knop_staat_op_een_bevestigd_rapport(tmp_path):
    dd, st, aid, pid = _dorp(tmp_path)
    h = render_projectrapport(st, pid, csrf_token="TOK", username=IK)
    assert "Keep as a fact" in h and "value='rapport_naar_wiki'" in h
    # DE VOORZET STAAT ERIN, en het is de KORTE zin — niet de rapporttekst.
    assert 'name="tekst" value="Achieved"' in h, h[h.index("Keep as a fact"):][:600]
    assert "Ask for the datasheet" not in h.split("Keep as a fact")[1].split("</form>")[0]


def test_zonder_rapport_geen_knop(tmp_path):
    """Een project zonder document heeft niets vast te leggen; een seed-document is de OPDRACHT."""
    dd, st, aid, pid = _dorp(tmp_path)
    st.project_docs.write(pid, "")
    h = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK", username=IK)
    assert "Keep as a fact" not in h


def test_het_feit_is_kort_en_draagt_zijn_bron(tmp_path):
    dd, st, aid, pid = _dorp(tmp_path)
    _n, msg = _doe(dd, "rapport_naar_wiki", aid=aid, pid=pid, tekst="Achieved")
    assert not cockpit2.is_weigering(msg), msg
    fs = _feiten(dd, aid)
    assert len(fs) == 1
    feit = fs[0]
    # KORT: één regel, niet het rapport. De lengte van `modeloordeel_kort` is de maat (≤60+1).
    assert feit["tekst"] == "Achieved" and len(feit["tekst"]) <= 61
    assert "Learnings" not in feit["tekst"]
    g = feit["grond"]
    assert g["soort"] == "bron" and g["ref"] == pid
    assert g["url"] == f"/rapport?pid={pid}"
    assert "confirmed" in g["citaat"] and "Outsole-onderzoek" in g["citaat"]


def test_de_chip_op_de_pagina_is_klikbaar(tmp_path):
    """De url is het hele verschil met de oude keep-in-wiki: herkomst die je kunt VOLGEN, niet
    alleen lezen. `_grond_chip` maakt een bron-feit klikbaar zodra er een url bij staat."""
    dd, st, aid, pid = _dorp(tmp_path)
    _doe(dd, "rapport_naar_wiki", aid=aid, pid=pid, tekst="Achieved")
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="TOK", username=IK)
    assert f"<a href='/rapport?pid={pid}'" in h


def test_een_leeg_feit_wordt_geweigerd(tmp_path):
    dd, st, aid, pid = _dorp(tmp_path)
    _n, msg = _doe(dd, "rapport_naar_wiki", aid=aid, pid=pid, tekst="   ")
    assert cockpit2.is_weigering(msg), msg
    assert _feiten(dd, aid) == []


# ══ 2. De pagina krijgt een ALINEA, en alleen op verzoek ═════════════════════
def _met_feiten(dd, aid, n=2):
    st = cockpit2._Stores(dd)
    a = st.att.get(aid)
    meta = dict(a.meta or {})
    meta["feiten"] = [wiki.maak_feit(f"Feit {i}", soort="bron", ref="p", citaat="uit een test")
                      for i in range(n)]
    st.att.update(aid, meta=meta)
    return cockpit2._Stores(dd)


def test_de_knop_verschijnt_pas_bij_feiten(tmp_path):
    dd, st, aid, pid = _dorp(tmp_path)
    assert "pagina_synthese" not in render_pagina(st, aid, csrf_token="TOK", username=IK)
    st = _met_feiten(dd, aid)
    assert "Draft conclusion from facts" in render_pagina(st, aid, csrf_token="TOK", username=IK)


def test_zonder_model_een_nette_melding_en_geen_halve_tekst(tmp_path, monkeypatch):
    """FAIL-CLOSED. Een mislukte oproep die niets teruggeeft leest als "er viel niets te zeggen",
    en dat is een ander antwoord dan "ik kon het niet vragen"."""
    from nooch_village import llm
    dd, st, aid, pid = _dorp(tmp_path)
    _met_feiten(dd, aid)
    monkeypatch.setattr(llm, "reason", lambda *a, **k: None)
    _n, msg = _doe(dd, "pagina_synthese", aid=aid)
    assert cockpit2.is_weigering(msg) and "could not draft" in msg
    a = cockpit2._Stores(dd).att.get(aid)
    assert wiki.synthese_concept(a) == {}, "er staat toch een leeg voorstel klaar"
    assert a.body == "Wat we weten.", "de pagina is aangeraakt"


def test_een_lege_modelreactie_telt_als_mislukt(tmp_path, monkeypatch):
    """Witruimte is geen alinea. Zonder deze regel zou een model dat "  " teruggeeft een leeg
    voorstel in het bewerkveld zetten dat er als een echte synthese uitziet."""
    from nooch_village import llm
    dd, st, aid, pid = _dorp(tmp_path)
    _met_feiten(dd, aid)
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "   \n  ")
    _n, msg = _doe(dd, "pagina_synthese", aid=aid)
    assert cockpit2.is_weigering(msg)
    assert wiki.synthese_concept(cockpit2._Stores(dd).att.get(aid)) == {}


def test_de_synthese_wordt_een_ALINEA_en_geen_feit(tmp_path, monkeypatch):
    """HET ONDERSCHEID VAN DEZE HELE SCOPE. Stap 1 maakt feiten; stap 2 maakt lopende tekst. Zou
    de synthese er als feit bij komen, dan staat een modeluitspraak tussen de nagekeken feiten en
    voedt hij zichzelf bij de volgende ronde."""
    from nooch_village import llm
    dd, st, aid, pid = _dorp(tmp_path)
    _met_feiten(dd, aid)
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "Samen wijzen deze feiten op één ding.")
    _n, msg = _doe(dd, "pagina_synthese", aid=aid)
    assert not cockpit2.is_weigering(msg), msg
    a = cockpit2._Stores(dd).att.get(aid)
    assert len(wiki.feiten(a)) == 2, "de synthese is er als feit bij gekomen"
    assert "Samen wijzen" not in (a.body or ""), "hij is meteen opgeslagen"
    # …maar hij staat wél in het bewerkveld, met de melding dat er nog niets vaststaat.
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="TOK", username=IK)
    assert "Samen wijzen deze feiten op één ding." in h
    assert "draft conclusion" in h and "Nothing is saved until you press Save" in h
    assert "pagina_synthese_verwerp" in h


def test_opslaan_maakt_er_tekst_van_en_ruimt_het_voorstel_op(tmp_path, monkeypatch):
    """De mens drukt op Save; wat hij liet staan is nu gewoon de tekst van de pagina. Bleef het
    voorstel bestaan, dan plakte de volgende pageload hem er nog een keer onder."""
    from nooch_village import llm
    dd, st, aid, pid = _dorp(tmp_path)
    _met_feiten(dd, aid)
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "Samen wijzen deze feiten op één ding.")
    _doe(dd, "pagina_synthese", aid=aid)
    _doe(dd, "artefact_edit", aid=aid,
         body_html="<p>Wat we weten.</p><p>Samen wijzen deze feiten op één ding.</p>")
    a = cockpit2._Stores(dd).att.get(aid)
    assert "Samen wijzen deze feiten op één ding." in a.body
    assert wiki.synthese_concept(a) == {}, "het voorstel staat nog klaar na opslaan"


def test_verwerpen_laat_de_pagina_ongemoeid(tmp_path, monkeypatch):
    from nooch_village import llm
    dd, st, aid, pid = _dorp(tmp_path)
    _met_feiten(dd, aid)
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "Een voorstel.")
    _doe(dd, "pagina_synthese", aid=aid)
    _doe(dd, "pagina_synthese_verwerp", aid=aid)
    a = cockpit2._Stores(dd).att.get(aid)
    assert wiki.synthese_concept(a) == {} and a.body == "Wat we weten."


def test_zonder_feiten_geen_synthese(tmp_path, monkeypatch):
    """Een model dat uit niets een conclusie trekt, verzint er een."""
    from nooch_village import llm
    dd, st, aid, pid = _dorp(tmp_path)
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "Iets.")
    _n, msg = _doe(dd, "pagina_synthese", aid=aid)
    assert cockpit2.is_weigering(msg) and "no facts" in msg


# ══ 3. Bijna-gelijke paginanamen ═════════════════════════════════════════════
def test_twee_bijna_gelijke_namen_worden_allebei_getoond(tmp_path):
    dd, st, aid, pid = _dorp(tmp_path)
    st.att.add(ROL, "note", title="Outsole materials 2026")
    st.att.add(ROL, "note", title="Iets heel anders")
    st = cockpit2._Stores(dd)
    groepen = bijna_gelijke_paginas(st)
    assert len(groepen) == 1
    assert set(groepen[0]) == {"Outsole materials", "Outsole materials 2026"}
    hint = dubbele_namen_hint(st)
    assert "Outsole materials" in hint and "Outsole materials 2026" in hint
    assert "Iets heel anders" not in hint


def test_zonder_verwarring_geen_waarschuwing(tmp_path):
    """Een waarschuwing die er altijd staat, leest niemand meer."""
    dd, st, aid, pid = _dorp(tmp_path)
    st.att.add(ROL, "note", title="Iets heel anders")
    assert dubbele_namen_hint(cockpit2._Stores(dd)) == ""


def test_de_hint_staat_onder_de_keuzelijst_van_het_rapport(tmp_path):
    dd, st, aid, pid = _dorp(tmp_path)
    st.att.add(ROL, "note", title="Outsole materials 2026")
    st = cockpit2._Stores(dd)
    rap = render_projectrapport(st, pid, csrf_token="TOK", username=IK)
    assert "nearly the same name" in rap


# ══ 4. Het archief wijst naar zijn rapport ═══════════════════════════════════
def test_een_archiefregel_heeft_een_weg_naar_het_rapport(tmp_path):
    """Een gearchiveerd project bestaat alleen nog als rapport; zonder link is dat niet te vinden."""
    from nooch_village.views.projects import _archived_html
    dd, st, aid, pid = _dorp(tmp_path)
    st.projects.archive(pid)
    p = cockpit2._Stores(dd).projects.get(pid)
    h = _archived_html(cockpit2._Stores(dd), [p], "TOK", "/projects")
    assert f"/rapport?pid={pid}" in h and "report" in h
