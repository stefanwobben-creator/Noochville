"""De wikipagina volgens prototype v2 (besluit Stefan, 4 oktober 2026).

Feiten staan onder HUN kopje (de `For:`-regel), de rest onder "Other facts"; de administratie
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


def test_een_feit_staat_onder_zijn_kopje_en_niet_nog_eens_onderaan(tmp_path):
    st, a = _pagina(tmp_path, [_f("USDA lists Pliant PCS", "Company certification"),
                               _f("Molded in Vietnam", "Where the work is done"),
                               _f("Zonder sectie")])
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    body = h[h.index("id='wiki-body'"):h.index("</div></div><aside") if "<aside" in h else None]
    # onder zijn kopje, vóór het volgende kopje van hetzelfde niveau
    # Op de KOPPEN zelf (`<h4>`/`<h5>`): dezelfde woorden staan ook in de sectie-keuzelijst van het
    # bewerkformulier van een feit.
    import re as _re
    k = lambda tekst: _re.search(rf"<h[345]>{_re.escape(tekst)}", body).start()
    assert k("Company certification") < body.index("USDA lists Pliant PCS") < k("Labor &amp; compliance")
    assert k("Where the work is done") < body.index("Molded in Vietnam") < k("Open items")
    # niet dubbel: de lijst onderaan heet nu "Other facts" en draagt alleen de rest
    assert h.count("<div class='ptitle'>USDA lists Pliant PCS") == 1   # (het bewerkveld telt niet)
    rest = h[h.index(">Other facts<"):]
    assert "Zonder sectie" in rest and "USDA lists" not in rest


def test_het_feitblok_hoort_niet_bij_de_opgeslagen_tekst(tmp_path):
    """`data-chrome`: de editor haalt het weg vóór het opslaan, de server negeert het."""
    from nooch_village.cockpit2_util import _md_naar_bron
    st, a = _pagina(tmp_path, [_f("USDA lists Pliant PCS", "Company certification")])
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    body = h[h.index("id='wiki-body'"):]
    body = body[body.index(">") + 1:body.index("<form")]
    assert "data-chrome contenteditable='false'>" in body and "1 fact<" in body
    terug = _md_naar_bron(body) if callable(_md_naar_bron) else ""
    assert "USDA lists" not in terug and "1 fact" not in terug


def test_een_sectie_die_niet_bestaat_valt_in_other_facts(tmp_path):
    st, a = _pagina(tmp_path, [_f("Verweesd", "Kopje dat er niet is")])
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    assert "Verweesd" in h[h.index(">Facts<"):]          # alles onderaan → gewoon "Facts"


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


def test_de_telling_laat_geen_spatie_achter_in_de_kop(tmp_path):
    """Een echte opslag in de browser schreef "## Company certification " (met spatie): de spatie
    vóór het chipje stond buiten de chrome. Alles wat erbij komt, moet IN de chrome zitten."""
    from nooch_village.cockpit2_util import _md_naar_bron
    st, a = _pagina(tmp_path, [_f("USDA lists Pliant PCS", "Company certification")])
    h = render_pagina(st, a.id, csrf_token="TOK", username=IK)
    body = h[h.index("id='wiki-body'"):]
    body = body[body.index(">") + 1:body.index("<form")]
    terug = _md_naar_bron(body)
    assert "## Company certification\n" in terug and "## Company certification \n" not in terug
