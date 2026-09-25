"""Feiten en backlinks worden blokken — route B (24 september 2026).

DE LAATSTE STAP VAN DE BLOK-SPRINT, en de enige waar de inhoud NIET in de body woont. Feiten leven
in `meta["feiten"]`, backlinks worden bij het lezen afgeleid uit de bodies van andere pagina's.
Route A (ze als markdown in de body schrijven) zou van allebei een tweede waarheid maken; route B
zet er een MARKERING neer en laat de inhoud staan waar hij hoort.

WAT DE MARKERING OPLOST. Tot nu toe stonden beide secties vastgespijkerd ONDER de tekst. Je kon
een feit niet naast de alinea zetten die hij grondt, en in een pagina die met een tabel eindigt
hing er ineens een kopje "Facts" achteraan. Met `{{facts}}` bepaalt de schrijver de plek — en zet
hij hem nergens neer, dan blijft alles precies zoals het was.

GEMETEN VOORDAT IK IETS BOUWDE, op de 122 artefacten van prod:

  - nul feiten, nul `[[links]]` en dus nul backlinks;
  - nul keer `{{` in een body.

Dat is waarom deze syntax veilig is en waarom de val-terug-vorm belangrijker is dan de nieuwe: er
is vandaag geen enkele pagina die hier iets van merkt.

DRIE REGELS DIE JE NIET MAG OMDRAAIEN
  1. De inhoud blijft waar hij woont. Het blok TOONT feiten, het bewaart er geen.
  2. De markering is de bron, het scherm is uitvoer. Wat er tussen de `<div>` staat is chrome; de
     rondgang levert weer `{{facts}}` op, nooit de gerenderde kaartjes.
  3. Alleen een blok dat NIETS ANDERS is dan de markering telt. Dezelfde grens als bij de embed
     en de tool-kaart: anders verandert één woord in een alinea de vorm van de hele pagina.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki
from nooch_village.cockpit2_util import _md, _md_naar_bron
from nooch_village.views.wiki import _body_html, render_pagina


def _rondgang(bron: str) -> bool:
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


def _dorp(tmp_path, can_edit=True):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    mens = st.people.add("Beheerder", "b@t.nl")
    if can_edit:
        st.assign.assign(rol, "person", mens.id)
    return dd, st, rol


def _pagina(st, a, can_edit=True):
    return render_pagina(st, a.id, csrf_token="TOK",
                         username="b@t.nl" if can_edit else "")


# ── 1. Welke markeringen bestaan er ──────────────────────────────────────────
def test_de_markeringen_staan_op_een_plek():
    """Twee, en ze heten zoals de kopjes die ze vervangen."""
    assert set(wiki.AFGELEID) == {"facts", "backlinks"}


def test_markers_leest_de_bron_en_niet_het_scherm():
    """`render_pagina` moet WETEN welke markering gebruikt is, want de sectie die in de tekst
    landt mag er onderaan niet nog een keer bij staan. Dat lees je uit de bron."""
    assert wiki.markers("tekst\n\n{{facts}}\n\nmeer") == {"facts"}
    assert wiki.markers("{{facts}}\n\n{{backlinks}}") == {"facts", "backlinks"}
    assert wiki.markers("niets bijzonders") == set()


def test_een_onbekende_markering_telt_niet():
    """Fail-closed: `{{kpi}}` is geen afgeleid blok, dus het blijft gewoon tekst."""
    assert wiki.markers("{{kpi}}") == set()


def test_een_markering_middenin_een_zin_telt_niet():
    """DE GRENS, dezelfde als bij de embed en de tool-kaart."""
    assert wiki.markers("zie {{facts}} hierboven") == set()


# ── 2. Het blok op het scherm ────────────────────────────────────────────────
def test_de_markering_wordt_het_blok_met_de_sectie_erin():
    html = _body_html("{{facts}}", [], blokken=True,
                      secties={"facts": "<div class='c2-sec'>FEITEN-HIER</div>"})
    assert "data-blok='facts'" in html
    assert "FEITEN-HIER" in html
    assert "{{facts}}" not in html.replace("data-blok-bron='{{facts}}'", "")


def test_een_markering_middenin_een_alinea_blijft_tekst():
    html = _body_html("zie {{facts}} hierboven", [], blokken=True,
                      secties={"facts": "<div>FEITEN-HIER</div>"})
    assert "FEITEN-HIER" not in html
    assert "{{facts}}" in html


def test_zonder_sectie_komt_er_een_label_en_geen_haakjes():
    """Op de Notes-tab van `/node` is er geen `st` om feiten mee op te halen. Rauwe accolades op
    het scherm zijn dan het slechtste van twee werelden."""
    html = _body_html("{{facts}}", [], blokken=True)
    assert "{{facts}}" not in html.replace("data-blok-bron='{{facts}}'", "")
    assert "Facts" in html


def test_het_blok_is_niet_bewerkbaar():
    """De inhoud is uitvoer, geen tekst. Zonder `contenteditable='false'` zet de browser de caret
    ertussen en typt de lezer in iets dat bij het opslaan verdampt."""
    html = _body_html("{{facts}}", [], blokken=True, secties={"facts": "<div>X</div>"})
    assert "contenteditable='false'" in html


def test_zonder_de_blokstand_wordt_het_een_label(tmp_path):
    """De Notes-tab van `/node` rendert plat, en daar staat geen sectie maar de NAAM. Rauwe
    accolades op het scherm zijn het slechtste van twee werelden: het ziet eruit als een fout en
    het zegt niets."""
    assert _body_html("{{facts}}", []) == "<span class='chip muted'>Facts</span>"
    assert _body_html("Ervoor.\n\n{{facts}}\n\nErna.", []) == (
        "Ervoor.<br><br><span class='chip muted'>Facts</span><br><br>Erna.")


def test_het_label_kent_dezelfde_grens(tmp_path):
    """Middenin een zin, en een markering die niet bestaat: allebei gewoon tekst."""
    assert _body_html("zie {{facts}} hier", []) == "zie {{facts}} hier"
    assert _body_html("{{kpi}}", []) == "{{kpi}}"


def test_zonder_de_blokstand_verandert_er_niets_aan_de_tekst():
    """De Notes-tab rendert plat; daar bestaan geen blokken om iets aan op te hangen.

    WAT HIER WERKELIJK BESCHERMT, en dat is iets anders dan waar de code het vandaan haalt. De
    substitutie staat in `_body_html` binnen `if blokken:`, maar een mutatie die hem daarbuiten
    zet blijft GROEN — `_MARKER_BLOK_RE` eist het blok-omhulsel, en in de platte stand maakt `_md`
    dat omhulsel niet. De regex is dus de poort; de plek in de code is alleen gezelschap voor de
    tool-kaart die er al stond. Ik laat hem daar staan omdat het scheelt dat elk chatbericht en
    elke reactie er niet langs hoeft, maar noem het hier zodat niemand denkt dat die `if` iets
    tegenhoudt."""
    html = _body_html("{{facts}}", [], secties={"facts": "<div>FEITEN-HIER</div>"})
    assert "FEITEN-HIER" not in html


# ── 3. De rondgang ───────────────────────────────────────────────────────────
def test_de_rondgang_levert_de_markering_terug():
    """DE HARDE EIS. Kwam de gerenderde sectie terug in de bron, dan stonden de feiten na één
    bewerkronde als platte tekst in de pagina — twee waarheden, en de tweede veroudert."""
    html = _body_html("{{facts}}", [], blokken=True,
                      secties={"facts": "<div class='c2-sec'><h3>Facts</h3>kaartje</div>"})
    assert _md_naar_bron(html).strip() == "{{facts}}"


def test_de_rondgang_houdt_de_tekst_eromheen_heel():
    html = _body_html("Ervoor.\n\n{{facts}}\n\nErna.", [], blokken=True,
                      secties={"facts": "<div>X</div>"})
    assert _md_naar_bron(html).strip() == "Ervoor.\n\n{{facts}}\n\nErna."


def test_een_formulier_in_het_blok_eet_de_tekst_erna_niet_op():
    """DE BUG DIE IK HIERONDER MOEST FIXEN. Een `<input>` heeft geen eindtag, dus de chrome-teller
    liep op en kwam nooit terug: alles tot de volgende eindtag verdween uit de bron. Het
    feiten-blok draagt formulieren, dus zonder die fix at dit blok de rest van zijn alinea op."""
    sectie = ("<div class='c2-sec'><form method='post'>"
              "<input type='hidden' name='csrf' value='X'><br><hr>"
              "<button>Add</button></form></div>")
    html = _body_html("Ervoor.\n\n{{facts}}\n\nErna.", [], blokken=True,
                      secties={"facts": sectie})
    assert _md_naar_bron(html).strip() == "Ervoor.\n\n{{facts}}\n\nErna."


def test_een_void_tag_in_chrome_slikt_niets_meer_in():
    """Dezelfde fix, los van de wiki gemeten — want `data-chrome` wordt overal gebruikt."""
    h = ("<div class='wb' data-blok='p'><span data-chrome><input type='hidden'></span>"
         "Zichtbaar</div>")
    assert _md_naar_bron(h).strip() == "Zichtbaar"


# ── 4. Op de echte pagina ────────────────────────────────────────────────────
def test_zonder_markering_staan_de_secties_waar_ze_stonden(tmp_path):
    """DE VAL-TERUG-VORM, en die telt het zwaarst: 122 pagina's op prod hebben geen markering."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="Gewone tekst.")
    html = _pagina(st, a)
    assert html.count(">Facts</h3>") == 1
    assert html.count(">Links here</h3>") == 1
    assert html.index("id='wiki-body'") < html.index(">Facts</h3>")


def test_met_markering_staat_de_sectie_in_de_tekst_en_niet_meer_eronder(tmp_path):
    """Twee keer dezelfde feiten op één scherm is precies de verwarring die dit moest opruimen."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="Tekst.\n\n{{facts}}")
    html = _pagina(st, a)
    assert html.count(">Facts</h3>") == 1
    assert "data-blok='facts'" in html
    body = html.split("id='wiki-body'")[1].split("<form")[0]
    assert ">Facts</h3>" in body, "de sectie staat niet in de tekst"


def test_de_backlink_markering_werkt_hetzelfde(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="Tekst.\n\n{{backlinks}}")
    html = _pagina(st, a)
    assert html.count(">Links here</h3>") == 1
    assert "data-blok='backlinks'" in html
    assert html.count(">Facts</h3>") == 1, "de feiten horen onderaan te blijven staan"


def test_de_feiten_zelf_staan_in_het_blok(tmp_path):
    """Niet een kopje met een belofte: de echte kaartjes uit `meta["feiten"]`."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="{{facts}}")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Schoenen wegen 300 gram")]})
    body = _pagina(st, st.att.get(a.id)).split("id='wiki-body'")[1].split("<form")[0]
    assert "Schoenen wegen 300 gram" in body


def test_het_blok_bewaart_geen_feiten(tmp_path):
    """Regel 1: het blok TOONT, het bewaart niet. De body houdt de markering, meer niet."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="{{facts}}")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Een feit dat blijft")]})
    assert "Een feit dat blijft" not in st.att.get(a.id).body


def test_wie_niet_mag_bewerken_krijgt_geen_formulier_in_het_blok(tmp_path):
    """De poort staat vóór de belofte, ook binnen een blok."""
    dd, st, rol = _dorp(tmp_path, can_edit=False)
    a = st.att.add(rol, "note", title="Een pagina", body="{{facts}}")
    html = _pagina(st, a, can_edit=False)
    assert "pagina_feit_add" not in html


# ── 5. Het blokmodel kent de nieuwe soorten ──────────────────────────────────
def test_de_soort_staat_op_het_blok_zodat_de_greep_hem_ziet():
    for naam in ("facts", "backlinks"):
        html = _body_html("{{" + naam + "}}", [], blokken=True, secties={naam: "<div>X</div>"})
        assert f"data-blok='{naam}'" in html
        # ÉÉN blok, niet een blok in een blok. Geteld op het attribuut en niet op `class='wb'`:
        # het afgeleide blok draagt een tweede klasse, en die letterlijke telling mat de vorm van
        # het `class`-attribuut in plaats van het aantal blokken.
        assert html.count("data-blok=") == 1


def test_een_gewone_pagina_verandert_niet_van_vorm():
    """De ratchet van deze hele sprint: wie geen markering typt, merkt hier niets van."""
    bron = "### Kop\n\n- een\n- twee\n\nEen alinea."
    assert _body_html(bron, [], blokken=True) == _md(bron, blokken=True)
    assert _rondgang(bron)


# ── 6. De normaliseerpas in de browser ───────────────────────────────────────
def test_de_pas_laat_een_blok_met_een_eigen_bron_met_rust():
    """GEVONDEN IN DE BROWSER, NIET HIER. `blokNormaliseer` zet `data-blok` terug op wat de TAG
    zegt, en de tag van een afgeleid blok is een `div` — dus werd `facts` weer `p` en was het blok
    zijn soort kwijt zodra de pagina laadde. De bestaande uitzondering keek met `querySelector`
    alleen naar AFSTAMMELINGEN (het bewerkvlak van een tabel zit ín het blok); hier staat het
    attribuut op het omhulsel zelf.

    Deze toets leest de JS-bron, want pytest draait geen browser. Dat is zwak bewijs en daarom
    staat de echte meting in `claude/blok_browsercheck.js` — deze regel is er zodat de uitzondering
    niet stilletjes verdwijnt bij een volgende opruiming."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    assert 'hasAttribute("data-blok-bron")' in js


def test_de_volgorde_onderaan_blijft_zoals_hij_was(tmp_path):
    """Feiten, besluiten, backlinks. De drie secties in één klap achteraan plakken scheelt twee
    regels en verschuift "Decisions logged" naar boven de feiten — een wijziging die niemand
    vroeg, op een scherm dat verder niets van deze stap hoort te merken."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina",
                   body="Kijk op /decision-coach voor de sessies.")
    html = _pagina(st, a)
    assert (html.index(">Facts</h3>") < html.index(">Decisions logged</h3>")
            < html.index(">Links here</h3>"))
