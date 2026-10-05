"""Feit als blok in de tekst + het eenvoudige bewijsmodel (besluit Stefan, 5 oktober 2026).

Twee dingen:
1. De PLEK van een feit staat in de tekst, als één regel `{{fact:<id>}}`. Er is één ding: de pagina.
2. Bewijs is: waar komt het vandaan (link / bestand / zelf weten) + "I checked this" met naam en
   datum. Dat vinkje vervalt als tekst of bron verandert; een optionele "check again by"-datum maakt
   het feit rood zodra hij voorbij is. De automatische citaatcheck is een bonus, geen poort.
"""
from __future__ import annotations

import json

from nooch_village import artefacts, cockpit2, wiki, wiki_seed
from nooch_village.views.wiki import render_pagina

ROL = "mother_earth__nooch__creator_of_shoes"
IK = "b@t.nl"
ANDER = "x@t.nl"
BODY = "Intro.\n\n## Company certification\nCertificates.\n\n## Open items\n- Price"


def _dorp(tmp_path, feiten, body=BODY):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Tess Beheerder", IK).id)
    st.people.add("Iemand Anders", ANDER)
    a = st.att.add(ROL, "note", title="NFW", body=body, domain="Materials", meta={"feiten": feiten})
    return dd, a.id


def _doe(dd, actie, wie=IK, **v):
    return cockpit2.dispatch(dd, actie, {**{k: [x] for k, x in v.items()}, "next": ["/"]}, username=wie)[1]


def _pagina(dd, aid):
    return cockpit2._Stores(dd).att.get(aid)


def _link(tekst="USDA lists Pliant PCS"):
    return wiki.maak_feit(tekst, soort="bron", url="https://www.biopreferred.gov/x")


# ── de markering ───────────────────────────────────────────────────────────────────────────────

def test_een_markering_staat_op_een_eigen_regel():
    assert wiki.feit_marker("ab12") == "{{fact:ab12}}"
    body = "a\n{{fact:ab12}}\nb {{fact:zz}} midden\n{{fact:cd34}}  \n{{fact:ab12}}"
    assert wiki.geplaatste_feiten(body) == ["ab12", "cd34"]       # volgorde, uniek, alleen hele regels


def test_plaatsen_aan_het_eind_van_een_sectie_en_van_de_tekst():
    b, ok = wiki.plaats_feit_marker(BODY, "f1", "Company certification")
    assert ok and b.index("Certificates.") < b.index("{{fact:f1}}") < b.index("## Open items")
    b2, ok2 = wiki.plaats_feit_marker(b, "f2")
    assert ok2 and b2.rstrip().endswith("{{fact:f2}}")
    assert wiki.plaats_feit_marker(b2, "f1", "Open items") == (b2, False)   # staat er al


def test_een_kop_in_een_codeblok_telt_niet():
    body = "```\n## Company certification\n```\n\n## Company certification\nx"
    b, ok = wiki.plaats_feit_marker(body, "f1", "Company certification")
    assert ok and b.rstrip().endswith("x\n{{fact:f1}}")


def test_markeringen_weghalen():
    b = wiki.plaats_feit_marker(wiki.plaats_feit_marker(BODY, "f1")[0], "f2", "Open items")[0]
    assert "{{fact:f1}}" not in wiki.zonder_feit_marker(b, "f1") and "{{fact:f2}}" in b
    assert "{{fact" not in wiki.zonder_feitmarkeringen(b)


# ── weergave ───────────────────────────────────────────────────────────────────────────────────

def test_een_onbekend_en_een_dubbel_feit_breken_de_pagina_niet(tmp_path):
    f = _link()
    body = BODY + "\n{{fact:bestaatniet}}\n{{fact:%s}}\n\n{{fact:%s}}" % (f["id"], f["id"])
    dd, aid = _dorp(tmp_path, [f], body=body)
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="T", username=IK)
    assert "Fact not found" in h
    assert "This fact is already shown above." in h
    assert h.count("<div class='ptitle'>USDA lists Pliant PCS") == 1


def test_de_rolcontext_leest_geen_markeringen():
    """Een AI-vervuller krijgt de body als tekst; een id tussen accolades zegt hem niets. De feiten
    zelf volgen eronder, mét hun grond."""
    note = {"id": "NOTE-X", "kind": "note", "title": "NFW", "body": "Intro\n{{fact:ab12}}\nslot",
            "feiten": [{"tekst": "USDA lists Pliant PCS", "grond": "gegrond"}]}
    regels = artefacts._md_section({"own": [note], "inherited": []})
    tekst = "\n".join(regels)
    assert "{{fact:" not in tekst and "> Intro" in tekst and "> slot" in tekst
    assert "USDA lists Pliant PCS" in tekst


# ── bewijs: nagekeken en hercontrole ───────────────────────────────────────────────────────────

def test_nagekeken_maakt_een_feit_met_bron_gegrond():
    f = dict(_link(), gezien={"door": "Tess", "op": "2026-10-05"})
    s = wiki.grond_status(f)
    assert s["status"] == wiki.GEGROND and s["label"] == "checked by Tess, 5 Oct 2026"


def test_een_verstreken_hercontrole_maakt_het_feit_rood():
    f = dict(_link(), gezien={"door": "Tess", "op": "2025-01-01"}, hercheck="2025-06-01")
    assert wiki.grond_status(f)["status"] == wiki.VERVALLEN
    toekomst = dict(f, hercheck="2999-01-01")
    assert wiki.grond_status(toekomst)["status"] == wiki.GEGROND


def test_nagekeken_redt_geen_feit_zonder_bron():
    f = dict(wiki.maak_feit("x"), gezien={"door": "Tess", "op": "2026-10-05"})
    assert wiki.grond_status(f)["status"] == wiki.ONGEGROND


def test_een_rare_datum_telt_niet():
    assert wiki.nagekeken({"gezien": {"door": "T", "op": "gisteren"}}) == {}
    assert wiki.hercheck_datum({"hercheck": "volgend jaar"}) == ""


# ── acties ─────────────────────────────────────────────────────────────────────────────────────

def test_ik_heb_dit_nagekeken_zet_mijn_naam_uit_de_sessie(tmp_path):
    f = _link()
    dd, aid = _dorp(tmp_path, [f])
    msg = _doe(dd, "pagina_feit_gezien", aid=aid, fid=f["id"], door="Iemand Anders")
    assert not cockpit2.is_weigering(msg), msg
    [nu] = wiki.feiten(_pagina(dd, aid))
    assert nu["gezien"]["door"] == "Tess Beheerder" and wiki.nagekeken(nu)
    _doe(dd, "pagina_feit_gezien", aid=aid, fid=f["id"], uit="1")
    assert "gezien" not in wiki.feiten(_pagina(dd, aid))[0]


def test_zonder_bron_valt_er_niets_na_te_kijken(tmp_path):
    f = wiki.maak_feit("geen bron")
    dd, aid = _dorp(tmp_path, [f])
    assert cockpit2.is_weigering(_doe(dd, "pagina_feit_gezien", aid=aid, fid=f["id"]))
    assert "gezien" not in wiki.feiten(_pagina(dd, aid))[0]


def test_nakijken_ruimt_een_verlopen_hercontrole_op(tmp_path):
    f = dict(_link(), hercheck="2020-01-01")
    dd, aid = _dorp(tmp_path, [f])
    _doe(dd, "pagina_feit_gezien", aid=aid, fid=f["id"])
    [nu] = wiki.feiten(_pagina(dd, aid))
    assert "hercheck" not in nu and wiki.grond_status(nu)["status"] == wiki.GEGROND


def test_wie_niet_mag_bewerken_kan_ook_niet_nakijken(tmp_path):
    f = _link()
    dd, aid = _dorp(tmp_path, [f])
    try:
        _doe(dd, "pagina_feit_gezien", wie=ANDER, aid=aid, fid=f["id"])
    except cockpit2.Forbidden:
        pass
    assert "gezien" not in wiki.feiten(_pagina(dd, aid))[0]


def test_het_vinkje_vervalt_als_tekst_of_bron_verandert(tmp_path):
    f = dict(_link(), gezien={"door": "Tess", "op": "2026-10-05"})
    dd, aid = _dorp(tmp_path, [f])
    # alleen een hercontroledatum erbij: het vinkje blijft
    _doe(dd, "pagina_feit_edit", aid=aid, fid=f["id"], tekst=f["tekst"], soort="bron",
         url=f["grond"]["url"], hercheck="2027-04-05")
    [nu] = wiki.feiten(_pagina(dd, aid))
    assert wiki.nagekeken(nu) and wiki.hercheck_datum(nu) == "2027-04-05"
    # andere link: het vinkje gaat eraf
    _doe(dd, "pagina_feit_edit", aid=aid, fid=f["id"], tekst=f["tekst"], soort="bron",
         url="https://elders.org", hercheck="2027-04-05")
    assert not wiki.nagekeken(wiki.feiten(_pagina(dd, aid))[0])


def test_plaatsen_zet_de_regel_aan_het_eind_en_maar_een_keer(tmp_path):
    f = _link()
    dd, aid = _dorp(tmp_path, [f])
    _doe(dd, "pagina_feit_plaats", aid=aid, fid=f["id"])
    body = _pagina(dd, aid).body
    assert body.rstrip().endswith(wiki.feit_marker(f["id"]))
    assert not cockpit2.is_weigering(_doe(dd, "pagina_feit_plaats", aid=aid, fid=f["id"]))
    assert _pagina(dd, aid).body.count("{{fact:") == 1


def test_verwijderen_haalt_ook_de_regel_uit_de_tekst(tmp_path):
    f = _link()
    dd, aid = _dorp(tmp_path, [f], body=BODY + "\n" + wiki.feit_marker(f["id"]))
    _doe(dd, "pagina_feit_del", aid=aid, fid=f["id"])
    a = _pagina(dd, aid)
    assert not wiki.feiten(a) and "{{fact:" not in a.body


def test_bulk_import_zet_een_for_regel_als_plek_in_de_tekst(tmp_path):
    dd, aid = _dorp(tmp_path, [])
    feiten = [{"Text": "Certified by USDA", "Type": "bron", "URL": "https://e.org",
               "For": "Company certification"},
              {"Text": "Zonder plek", "Type": "bron", "URL": "https://e.org"}]
    cockpit2.dispatch(dd, "pagina_bulk_import_facts",
                      {"aid": [aid], "facts_json": [json.dumps(feiten)], "next": ["/"]}, username=IK)
    a = _pagina(dd, aid)
    geplaatst = wiki.geplaatste_feiten(a.body)
    assert len(geplaatst) == 1 and len(wiki.feiten(a)) == 2
    assert a.body.index("Certificates.") < a.body.index("{{fact:") < a.body.index("## Open items")


# ── migratie ───────────────────────────────────────────────────────────────────────────────────

def test_de_migratie_is_eerst_een_droogloop_en_daarna_idempotent(tmp_path):
    met = wiki.maak_feit("Onder een kop", sectie="Company certification")
    zonder = wiki.maak_feit("Nergens", sectie="Kop die niet bestaat")
    dd, aid = _dorp(tmp_path, [met, zonder])
    st = cockpit2._Stores(dd)
    rapport = wiki_seed.feiten_plaatsen(st.att)
    assert rapport and "{{fact:" not in _pagina(dd, aid).body               # droogloop schrijft niets
    assert "Nothing to place" not in wiki_seed.feiten_plaatsen_tekst(rapport)
    wiki_seed.feiten_plaatsen(st.att, apply=True)
    a = _pagina(dd, aid)
    assert wiki.geplaatste_feiten(a.body) == [wiki.feit_id(wiki.feiten(a)[0])]
    voor = a.body
    wiki_seed.feiten_plaatsen(cockpit2._Stores(dd).att, apply=True)
    assert _pagina(dd, aid).body == voor


# ── Bulk Import: de plak is de pagina ──────────────────────────────────────────────────────────

def _plak(dd, aid, items):
    return cockpit2.dispatch(dd, "pagina_bulk_import_facts",
                             {"aid": [aid], "facts_json": [json.dumps(items)], "next": ["/"]},
                             username=IK)[1]


def test_feiten_en_tekst_komen_in_de_volgorde_van_de_plak(tmp_path):
    dd, aid = _dorp(tmp_path, [])
    msg = _plak(dd, aid, [
        {"Kind": "text", "Text": "Eerst een zin.", "For": "Company certification"},
        {"Text": "Daarna een feit", "Type": "source", "URL": "https://e.org", "For": "Company certification"},
        {"Kind": "text", "Text": "- Verify in FSC Search", "For": "Open items"},
    ])
    assert "1 facts imported, 2 text blocks" in msg, msg
    a = _pagina(dd, aid)
    fid = wiki.feit_id(wiki.feiten(a)[0])
    b = a.body
    assert b.index("Certificates.") < b.index("Eerst een zin.") < b.index("{{fact:%s}}" % fid) \
        < b.index("## Open items") < b.index("- Verify in FSC Search")


def test_een_kop_die_er_nog_niet_is_komt_erbij(tmp_path):
    """De plakker noemde hem zelf. Op een nieuwe pagina bouwt één plak zo de hele pagina."""
    dd, aid = _dorp(tmp_path, [], body="")
    _plak(dd, aid, [{"Text": "Molded in Vietnam", "Type": "source", "URL": "https://e.org",
                     "For": "Location & contact"},
                    {"Kind": "text", "Text": "not found", "For": "Labor & compliance"}])
    b = _pagina(dd, aid).body
    assert b.startswith("## Location & contact\n{{fact:")
    assert "## Labor & compliance\nnot found" in b


def test_alleen_tekst_plakken_kan_ook(tmp_path):
    dd, aid = _dorp(tmp_path, [])
    msg = _plak(dd, aid, [{"Kind": "text", "Text": "- Ask for SDS", "For": "Open items"}])
    assert not cockpit2.is_weigering(msg) and "0 facts imported, 1 text blocks" in msg, msg
    assert _pagina(dd, aid).body.rstrip().endswith("- Ask for SDS")


def test_check_again_by_wordt_de_hercontrole(tmp_path):
    dd, aid = _dorp(tmp_path, [])
    msg = _plak(dd, aid, [{"Text": "FSC CoC", "Type": "source", "URL": "https://e.org",
                           "CheckAgainBy": "2031-02-22"},
                          {"Text": "Rare datum", "Type": "source", "URL": "https://e.org",
                           "CheckAgainBy": "22 Feb 2031"}])
    f1, f2 = wiki.feiten(_pagina(dd, aid))
    assert wiki.hercheck_datum(f1) == "2031-02-22" and not wiki.hercheck_datum(f2)
    assert "not a date" in msg


def test_de_woorden_van_het_formulier_werken_als_type(tmp_path):
    dd, aid = _dorp(tmp_path, [])
    _plak(dd, aid, [{"Text": "a", "Type": "link", "URL": "https://e.org"},
                    {"Text": "b", "Type": "first-hand"}])
    f1, f2 = wiki.feiten(_pagina(dd, aid))
    assert f1["grond"]["soort"] == "bron"
    assert f2["grond"]["soort"] == "attested" and f2["grond"]["ref"] == "Tess Beheerder"


def test_de_parser_kent_kopjes_tekst_en_check_again_by():
    from pathlib import Path
    js = (Path(cockpit2.__file__).parent / "static" / "nooch.js").read_text(encoding="utf-8")
    p = js[js.index("function parseFacts("):js.index("// Open modal dialog")]
    assert 'Kind: "text"' in p and "fact.For = kop" in p
    assert "fact.CheckAgainBy = val" in p
    assert "parseMarkdown" not in js        # een sectie wordt nooit meer een feit zonder bron
