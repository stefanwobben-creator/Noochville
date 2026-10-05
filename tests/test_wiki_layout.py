"""De wikipagina volgens prototype v2 (besluit Stefan, 4 oktober 2026).

Feiten staan op hun plek in de TEKST (sinds 5 oktober 2026 een regel `{{fact:<id>}}`; de `For:`-regel
van Bulk Import zet die neer), de rest onderaan; de administratie
staat in een zijbalk; een kruimelpad leidt terug naar het overzicht; een succesmelding is klein.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki
from nooch_village.views.wiki import render_pagina, render_wiki_index

ROL = "mother_earth__nooch__website_developer"
IK = "b@t.nl"

BODY = """Supplier.

## Company certification
Certificates we know of.

## Labor & compliance
- No policy found.

### Where the work is done

## Open items
- Price: not yet provided"""


def _pagina(tmp_path, feiten):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Beheerder", IK).id)
    a = st.att.add(ROL, "note", title="NFW", body=BODY, meta={"feiten": feiten})
    return cockpit2._Stores(dd), a


def _f(tekst, sectie=""):
    return wiki.maak_feit(tekst, soort="bron", url="https://example.org", sectie=sectie)


def _met_plek(tmp_path, feiten, onder):
    """Een pagina waarin elk feit uit `onder` ({tekst: kopje}) zijn regel in de tekst heeft."""
    st, a = _pagina(tmp_path, feiten)
    body = a.body
    for f in feiten:
        if f["tekst"] in onder:
            body, gedaan = wiki.plaats_feit_marker(body, f["id"], onder[f["tekst"]])
            assert gedaan
    st.att.update(a.id, body=body)
    return cockpit2._Stores(st.dd), st.att.get(a.id)


def test_een_feit_staat_op_zijn_plek_in_de_tekst_en_niet_nog_eens_onderaan(tmp_path):
    """Sinds 5 oktober 2026 zegt de TEKST waar een feit staat (`{{fact:<id>}}`), niet de `sectie`."""
    feiten = [_f("USDA lists Pliant PCS"), _f("Molded in Vietnam"), _f("Zonder plek")]
    st, a = _met_plek(tmp_path, feiten, {"USDA lists Pliant PCS": "Company certification",
                                         "Molded in Vietnam": "Where the work is done"})
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    body = h[h.index("id='wiki-body'"):h.index("<form method='post' action='/action' class='wiki-form'")]
    import re as _re
    k = lambda tekst: _re.search(rf"<h[345]>{_re.escape(tekst)}", body).start()
    assert k("Company certification") < body.index("USDA lists Pliant PCS") < k("Labor &amp; compliance")
    assert k("Where the work is done") < body.index("Molded in Vietnam") < k("Open items")
    # niet dubbel: onderaan staat alleen wat geen plek heeft
    assert h.count("<div class='ptitle'>USDA lists Pliant PCS") == 1   # (het bewerkveld telt niet)
    rest = h[h.index(">Not placed yet<"):]
    assert "Zonder plek" in rest and "USDA lists" not in rest


def test_een_lezer_ziet_de_rest_als_other_facts(tmp_path):
    feiten = [_f("USDA lists Pliant PCS"), _f("Zonder plek")]
    st, a = _met_plek(tmp_path, feiten, {"USDA lists Pliant PCS": "Company certification"})
    h = render_pagina(st, a.id)                                   # geen sessie: alleen lezen
    assert ">Other facts<" in h and "Not placed yet" not in h
    assert "Zonder plek" in h[h.index(">Other facts<"):]


def test_het_feitblok_draagt_alleen_zijn_regel_naar_de_opslag(tmp_path):
    """`data-blok-bron` is de bron, de rest is `data-chrome`: de editor haalt het weg vóór het
    opslaan en de server negeert het."""
    from nooch_village.cockpit2_util import _md_naar_bron
    feiten = [_f("USDA lists Pliant PCS")]
    st, a = _met_plek(tmp_path, feiten, {"USDA lists Pliant PCS": "Company certification"})
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    body = h[h.index("id='wiki-body'"):]
    body = body[body.index(">") + 1:body.index("<form method='post' action='/action' class='wiki-form'")]
    regel = wiki.feit_marker(feiten[0]["id"])
    assert f"data-blok='fact' data-blok-bron='{regel}' contenteditable='false'>" in body
    assert "<div class='wiki-inline' data-chrome>" in body
    terug = _md_naar_bron(body)
    assert "USDA lists" not in terug and regel in terug
    assert terug.strip() == a.body.strip()


def test_een_sectie_die_niet_bestaat_blijft_ongeplaatst(tmp_path):
    st, a = _pagina(tmp_path, [_f("Verweesd", "Kopje dat er niet is")])
    assert wiki.plaats_feit_marker(a.body, "x1", "Kopje dat er niet is") == (a.body, False)
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    assert "Verweesd" in h[h.index(">Not placed yet<"):]


def test_administratie_in_de_zijbalk_en_een_kruimelpad(tmp_path):
    st, a = _pagina(tmp_path, [])
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    assert "<aside class='pkaart-rail'>" in h
    rail = h[h.index("<aside class='pkaart-rail'>"):]
    assert ">Owner</span>" in rail and ">Section</span>" in rail
    assert "<div class='pkaart-crumb'><a href='/wiki'>Wiki</a> ›" in h
    assert "/wiki?bak=" in h


def test_het_kruimelpad_opent_de_sectie_in_het_overzicht(tmp_path):
    from nooch_village import domeinen
    st, a = _pagina(tmp_path, [])
    bak = domeinen.bakje_van(a, list(st.records.all()))[0]
    h = render_wiki_index(st, csrf_token="TOK", username=IK, bak=bak)
    import html as _html
    label = _html.escape(domeinen.label(bak), quote=True)
    assert f"<details open><summary>{label} " in h


def test_een_succesmelding_is_klein_en_een_weigering_niet(tmp_path):
    st, a = _pagina(tmp_path, [])
    klein = render_pagina(st, a.id, csrf_token="TOK", username=IK, msg="🗑 draft synthesis discarded")
    assert "<span class='chip muted'>🗑 draft synthesis discarded" in klein
    groot = render_pagina(st, a.id, csrf_token="TOK", username=IK, msg="✗ page not found")
    assert "<span class='chip muted'>✗" not in groot and "page not found" in groot


def test_een_feit_onder_een_kop_laat_de_kop_zelf_met_rust(tmp_path):
    """Een echte opslag in de browser schreef ooit "## Company certification " (met spatie), door
    iets dat naast de kop buiten de chrome stond. Een feit staat nu in zijn EIGEN blok; de kop
    krijgt er niets bij."""
    from nooch_village.cockpit2_util import _md_naar_bron
    feiten = [_f("USDA lists Pliant PCS")]
    st, a = _met_plek(tmp_path, feiten, {"USDA lists Pliant PCS": "Company certification"})
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    body = h[h.index("id='wiki-body'"):]
    body = body[body.index(">") + 1:body.index("<form method='post' action='/action' class='wiki-form'")]
    terug = _md_naar_bron(body)
    assert "## Company certification\n" in terug and "## Company certification \n" not in terug
    assert "<h4>Company certification</h4>" in body

