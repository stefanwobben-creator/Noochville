"""W1 (11 oktober 2026): bij "I checked this" zegt de mens welke vraag een feit beantwoordt en met
welke waarde. Het antwoord staat IN `gezien`: wie de tekst of bron verandert verliest het, een
antwoord wijzigen is opnieuw nakijken, en 'not applicable' vraagt altijd een reden. Een bevestigd
antwoord koppelt het feit aan zijn vraag waar het ook staat; yes tegen no is een conflict."""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, wiki, wiki_dekking as wd

from tests.test_cn3_substantiated import OWNER, _dd

BRON = {"soort": "bron", "url": "https://example.org/tds", "citaat": "", "ref": ""}


def _pagina(tmp_path, feiten, body="## Conclusion\n\nSome text."):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="Full Green", body=body, meta={"feiten": feiten})
    st.bom_materialen.zet("Insole", "Full Green")
    return dd, a.id


def _feit(fid, tekst, **kw):
    return {"id": fid, "tekst": tekst, "grond": dict(BRON), **kw}


def _cel(dd, k):
    st = cockpit2._Stores(dd)
    d, _ctx = wd.uit_stores(st.att, st.bom_leveranciers, st.bom_materialen)
    rij = next(r for r in d["materialen"] if r.get("pagina") is not None and r["pagina"].title == "Full Green")
    return rij["cellen"][k]


def _check(dd, aid, fid, **antwoorden):
    form = {"aid": [aid], "fid": [fid], "next": ["/"]}
    for k, w in antwoorden.items():
        if k.startswith("reden_"):
            form[k] = [w]
        else:
            form[f"antwoord_{k}"] = [w]
    return cockpit2.dispatch(dd, "pagina_feit_gezien", form, username="guest")[1]


# ── het model ───────────────────────────────────────────────────────────────

def test_not_applicable_zonder_reden_wordt_geweigerd():
    assert wiki.maak_antwoord("animal", "na")[0] is None
    assert wiki.maak_antwoord("animal", "na", "the material is a mineral")[0] == {
        "vraag": "animal", "waarde": "na", "reden": "the material is a mineral"}
    assert wiki.maak_antwoord("animal", "maybe")[0] is None


def test_antwoorden_staan_in_gezien_en_bestaan_niet_zonder():
    f = wiki.maak_feit("x", soort="bron", url="https://a",
                       gezien={"door": "S", "op": "2026-10-11", "antwoorden": [{"vraag": "plastic", "waarde": "yes"}]})
    assert wiki.antwoorden(f) == [{"vraag": "plastic", "waarde": "yes"}]
    zonder = dict(f)
    zonder.pop("gezien")
    assert wiki.antwoorden(zonder) == []


# ── de actie ────────────────────────────────────────────────────────────────

def test_nakijken_met_antwoord_slaat_het_op(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains plastic: yes, 30% PLA")])
    assert "✓ checked — 1 answer(s)" in _check(dd, aid, "F1", plastic="yes")
    f = wiki.feiten(cockpit2._Stores(dd).att.get(aid))[0]
    assert wiki.antwoorden(f) == [{"vraag": "plastic", "waarde": "yes"}] and f["gezien"]["door"]


def test_ongeldig_antwoord_slaat_niets_op(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "x")])
    assert "'not applicable' needs a reason" in _check(dd, aid, "F1", animal="na")
    assert "is not an answer" in _check(dd, aid, "F1", plastic="value")
    assert "no number for that question" in _check(dd, aid, "F1", co2="value")
    assert "gezien" not in wiki.feiten(cockpit2._Stores(dd).att.get(aid))[0]


def test_antwoord_wijzigen_is_opnieuw_nakijken(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "x")])
    _check(dd, aid, "F1", plastic="yes")
    _check(dd, aid, "F1", plastic="no", animal="na", reden_animal="mineral")
    f = wiki.feiten(cockpit2._Stores(dd).att.get(aid))[0]
    assert wiki.antwoorden(f) == [{"vraag": "animal", "waarde": "na", "reden": "mineral"},
                                  {"vraag": "plastic", "waarde": "no"}]


def test_tekst_wijzigen_laat_nakijken_en_antwoorden_vervallen(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains plastic: yes")])
    _check(dd, aid, "F1", plastic="yes")
    form = {"aid": [aid], "fid": ["F1"], "next": ["/"], "tekst": ["Contains plastic: no"],
            "soort": ["bron"], "url": [BRON["url"]], "citaat": [""]}
    cockpit2.dispatch(dd, "pagina_feit_edit", form, username="guest")
    f = wiki.feiten(cockpit2._Stores(dd).att.get(aid))[0]
    assert "gezien" not in f and wiki.antwoorden(f) == []
    # dezelfde inhoud opnieuw opslaan (alleen een hercheck-datum): het antwoord blijft
    _check(dd, aid, "F1", plastic="no")
    form["hercheck"] = ["2027-01-01"]
    cockpit2.dispatch(dd, "pagina_feit_edit", form, username="guest")
    assert wiki.antwoorden(wiki.feiten(cockpit2._Stores(dd).att.get(aid))[0]) == [{"vraag": "plastic", "waarde": "no"}]


# ── de dekking ──────────────────────────────────────────────────────────────

def test_een_antwoord_koppelt_waar_het_feit_ook_staat(tmp_path):
    """Onder 'Environmental impact' telde het feit nergens; met een antwoord telt het."""
    body = "## Environmental impact\n\n{{fact:F1}}\n\n## Conclusion"
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains plastic: yes")], body=body)
    assert _cel(dd, "plastic")["status"] == wd.LEEG
    _check(dd, aid, "F1", plastic="yes")
    c = _cel(dd, "plastic")
    assert c["status"] == wd.GECHECKT and c["antwoord"] == "yes" and c["feiten"] == ["F1"]


def test_een_feit_beantwoordt_twee_vragen(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "70% TENCEL, 30% PLA from maize")])
    _check(dd, aid, "F1", plastic="yes", biobased="yes")
    assert (_cel(dd, "plastic")["antwoord"], _cel(dd, "biobased")["antwoord"]) == ("yes", "yes")


def test_yes_tegen_no_is_een_conflict_ook_op_verschillende_plekken(tmp_path):
    body = "## Environmental impact\n\n{{fact:F1}}\n\n## Composition\n\n{{fact:F2}}"
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains PLA"), _feit("F2", "No plastic at all")], body=body)
    _check(dd, aid, "F1", plastic="yes")
    _check(dd, aid, "F2", plastic="no")
    c = _cel(dd, "plastic")
    assert c["status"] == wd.CONFLICT and "disagree" in c["reden"] and "antwoord" not in c


def test_een_vervallen_check_draagt_het_antwoord_niet(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "x", hercheck="2020-01-01")])
    _check(dd, aid, "F1", plastic="yes")              # nakijken ruimt een verlopen datum op …
    st = cockpit2._Stores(dd)
    a = st.att.get(aid)
    f = dict(wiki.feiten(a)[0])
    f["hercheck"] = "2020-01-01"                      # … dus zetten we hem terug, alsof hij verliep
    st.att.update(aid, meta={**a.meta, "feiten": [f]}, actor_id="t", actor_type="person",
                  governance_ref=f"role:{OWNER}")
    c = _cel(dd, "plastic")
    assert c["status"] == wd.ONGECHECKT and "antwoord" not in c


def test_zonder_antwoord_blijft_het_oude_kopjes_pad_werken(tmp_path):
    body = "## Contains plastic\n\n{{fact:F1}}"
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains plastic: yes")], body=body)
    _check(dd, aid, "F1")
    c = _cel(dd, "plastic")
    assert c["status"] == wd.GECHECKT and "antwoord" not in c


def test_de_pagina_toont_het_formulier_en_de_antwoorden(tmp_path):
    from nooch_village.views.wiki import render_pagina
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains plastic: yes")])
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")
    assert "name='antwoord_plastic'" in h and "name='reden_animal'" in h
    _check(dd, aid, "F1", plastic="yes")
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")
    assert "Answers: Contains plastic?: <strong>yes</strong>" in h
