"""Het Docs/Notion-patroon voor links (26 september 2026).

Drie dingen die elkaar nodig hebben:

1. Een link-knop in het zwevende balkje — want `createLink` heeft een adres nodig en de browser
   levert daar niets voor.
2. Een klik op een link doet nu niets zichtbaars: `contenteditable` vangt hem af en zet de cursor
   erin. Je ziet een link, je klikt, er gebeurt niets — en het adres zelf zie je nergens.
3. Enter levert een kale tag op, geen `.wb`-blok: geen greep, niet sleepbaar, tot er toevallig
   iets anders normaliseert.
"""
from __future__ import annotations

import pathlib
import re

from conftest import js_zonder_uitleg
from nooch_village import cockpit2
from nooch_village.cockpit2_util import (_LINK_ACTIES, _OPMAAK_KNOPPEN, _md, _md_naar_bron,
                                         link_kaart, opmaak_werkbalk)
from nooch_village.views.wiki import render_pagina

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()




def _wikiedit() -> str:
    return js_zonder_uitleg(JS).split("function wikiEdit(")[1].split("\n  function ")[0]


def _dorp(tmp_path, body="Een zin met [Nooch](https://nooch.earth) erin."):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    mens = st.people.add("Beheerder", "b@t.nl")
    st.assign.assign(rol, "person", mens.id)
    a = st.att.add(rol, "note", title="Een pagina", body=body)
    return dd, st, st.att.get(a.id)


# ── 1. De link-knop ──────────────────────────────────────────────────────────
def test_de_werkbalk_heeft_een_link_knop():
    assert "nvLink" in [c for c, *_ in _OPMAAK_KNOPPEN]
    assert "data-wiki-cmd='nvLink'" in opmaak_werkbalk()


def test_link_is_een_eigen_functie_en_geen_execcommand_knop():
    """Zelfde soort uitzondering als `nvCode`: `createLink` bestaat wél, maar heeft een ADRES
    nodig en daar levert de browser niets voor. Het `nv`-voorvoegsel zegt dat wij het doen."""
    per_cmd = {c: (a, l, t) for c, a, l, t in _OPMAAK_KNOPPEN if c}
    assert per_cmd["nvLink"][0] == "", "een eigen functie heeft geen execCommand-argument"
    kaal = js_zonder_uitleg(JS)
    tak = kaal.split('=== "nvLink"')[1].split("} else {")[0]
    assert "toonKaart(" in tak, "de knop opent de kaart niet"


def test_een_selectie_in_een_bestaande_link_opent_hem_ter_bewerking():
    """"als de selectie al binnen een link zit, opent het de bestaande URL ter bewerking"."""
    tak = js_zonder_uitleg(JS).split('=== "nvLink"')[1].split("} else {")[0]
    assert "linkVan(" in tak, "er wordt niet gekeken of de selectie al in een link zit"
    assert "toonKaart(bestaand, true)" in tak, "de bestaande link gaat niet in bewerkstand open"


def test_een_nieuwe_link_loopt_langs_createlink():
    tak = js_zonder_uitleg(JS).split('=== "nvLink"')[1].split("} else {")[0]
    assert 'execCommand("createLink"' in tak


def test_een_lege_selectie_maakt_geen_link():
    """Een cursor zonder selectie heeft geen tekst om link van te maken; `createLink` zou dan een
    lege `<a>` achterlaten waar niemand meer bij kan."""
    tak = js_zonder_uitleg(JS).split('=== "nvLink"')[1].split("} else {")[0]
    assert "isCollapsed" in tak and "toString().trim()" in tak


def test_unlink_bestaat_en_werkt_op_de_hele_link():
    """Zonder unlink raak je een link nooit meer kwijt: de tekst blijft eruitzien als tekst en
    blijft toch een link.

    DE SELECTIE EERST OP DE LINK, want `unlink` werkt op wat er geselecteerd is — anders haalt hij
    de link weg waar de cursor toevallig stond, of geen enkele."""
    haak = _wikiedit()
    weg = haak.split("function haalLinkWeg()")[1].split("\n    }")[0]
    assert "selectNodeContents(huidigeLink)" in weg
    assert 'execCommand("unlink")' in weg


def test_een_adres_zonder_schema_krijgt_er_een():
    """`_md` en de weg terug eisen allebei `http(s)://`. Wie "nooch.earth" typt krijgt van de
    browser een RELATIEVE href, en die valt er bij het opslaan stil uit: de tekst blijft staan, de
    link verdwijnt. Dat is precies het soort verlies dat je pas een week later merkt."""
    haak = _wikiedit()
    heel = haak.split("function heelAdres(")[1].split("\n    }")[0]
    assert '"https://" + a' in heel


def test_een_javascript_adres_komt_er_niet_in():
    """FAIL CLOSED, zoals `_md` en `_BronParser` dat allebei al doen. Een `javascript:`-url hoort
    niet eens in de opslag te belanden, klaar voor de dag waarop iemand een minder strenge
    renderer schrijft."""
    haak = _wikiedit()
    heel = haak.split("function heelAdres(")[1].split("\n    }")[0]
    assert 'return ""' in heel and "[a-z][a-z0-9+.-]*:" in heel


def test_een_link_overleeft_de_rondgang():
    """Wat de knop oplevert moet als markdown-link terugkomen; anders is hij na één bewerkronde
    platte tekst."""
    bron = "Een zin met [Nooch](https://nooch.earth) erin."
    assert _md_naar_bron(_md(bron, blokken=True)) == bron


# ── 2. De klik-op-link-kaart ─────────────────────────────────────────────────
def test_de_kaart_toont_drie_acties():
    assert [a for a, _l in _LINK_ACTIES] == ["open", "edit", "remove"]
    html = link_kaart()
    for actie, label in _LINK_ACTIES:
        assert f"data-link-actie='{actie}'" in html and f">{label}</button>" in html


def test_de_kaart_toont_het_adres():
    """Het adres zit in een attribuut, dus zonder dit zie je nergens waar de link heen gaat."""
    html = link_kaart()
    assert "class='wiki-linkurl'" in html
    assert "class='wiki-linkveld'" in html, "er is geen veld om het adres te wijzigen"


def test_de_kaart_komt_van_de_server(tmp_path):
    """Zoals het blokmenu en de werkbalk: de knoppen en hun namen wonen op één plek. Zou de
    browser ze bouwen, dan was dat de tweede plek — en de enige zonder toets."""
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    assert "id='wiki-linkkaart'" in html
    kaal = js_zonder_uitleg(JS)
    for verboden in (">Open<", ">Remove<", "createElement(\"button\")"):
        assert verboden not in _wikiedit(), f"de browser bouwt de kaart zelf ({verboden})"


def test_de_kaart_staat_naast_het_bewerkvlak_en_niet_erin(tmp_path):
    """Alles binnen `#wiki-body` gaat bij het opslaan mee als `body_html`."""
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    binnen = html.split("id='wiki-body'")[1].split("id='wb-menu-sjabloon'")[0]
    assert "wiki-linkkaart" not in binnen


def test_de_kaart_is_chrome():
    """Hij staat ernaast, maar een plakactie of een niet-opgeruimde kloon zou hem erin kunnen
    zetten — en dan hoort hij nog steeds geen tekst te worden."""
    assert "data-chrome" in link_kaart()


def test_een_gewone_klik_navigeert_niet():
    haak = _wikiedit()
    klik = haak.split('body.addEventListener("click"')[1].split("});")[0]
    assert "preventDefault()" in klik
    assert "toonKaart(a, false)" in klik


def test_cmd_en_ctrl_klik_navigeren_wel():
    """Zoals overal elders op het web. Wie die gewoonte heeft, hoort er niet op een kaartje te
    stuiten."""
    haak = _wikiedit()
    klik = haak.split('body.addEventListener("click"')[1].split("});")[0]
    assert "e.metaKey || e.ctrlKey" in klik
    assert klik.index("metaKey") < klik.index("preventDefault()"), \
        "de modifier-uitgang staat ná preventDefault en doet dus niets"


def test_de_middelste_muisknop_ook():
    """Die geeft geen `click`, alleen `auxclick` — zonder eigen tak mist die gewoonte hier."""
    haak = _wikiedit()
    assert 'body.addEventListener("auxclick"' in haak
    aux = haak.split('body.addEventListener("auxclick"')[1].split("});")[0]
    assert "e.button !== 1" in aux, "elke extra knop opent een venster"


def test_de_kaart_gaat_weg_bij_focus_verlies():
    haak = _wikiedit()
    uit = haak.split('body.addEventListener("focusout"')[1].split("});")[0]
    assert "kaartWeg()" in uit


def test_een_klik_op_de_kaart_sluit_hem_niet():
    """Hij staat buiten het bewerkvlak, dus een klik erop is een `focusout`. Zonder deze
    uitzondering sluit hij op het moment dat je hem gebruikt — dezelfde val als bij de werkbalk."""
    haak = _wikiedit()
    uit = haak.split('body.addEventListener("focusout"')[1].split("});")[0]
    assert "kaart.contains(e.relatedTarget)" in uit


def test_de_kaart_schuift_mee_en_verdwijnt_buiten_beeld():
    """De positie staat in venstercoördinaten. Zonder dit blijft hij staan waar hij stond terwijl
    de tekst eronder wegschuift."""
    haak = _wikiedit()
    assert "function kaartBijScroll()" in haak
    sc = haak.split("function kaartBijScroll()")[1].split("\n    }")[0]
    assert "window.innerHeight" in sc and "kaartWeg()" in sc
    assert 'window.addEventListener("scroll", kaartBijScroll, true)' in haak


def test_de_kaart_hergebruikt_de_zweeflogica():
    """"hergebruik die positioneringslogica in plaats van een tweede mechaniek te bouwen"."""
    haak = _wikiedit()
    toon = haak.split("function toonKaart(")[1].split("\n    }")[0]
    assert "zweefBij(kaart," in toon
    assert "function zweefBij(" not in haak, "de kaart heeft zijn eigen positionering"


def test_de_kaart_leent_de_vorm_van_de_werkbalk():
    """Hetzelfde soort ding — een klein vlak dat boven de tekst hangt en weer verdwijnt — hoort er
    hetzelfde uit te zien. Geen nieuwe knoppentaal voor dezelfde handeling."""
    html = link_kaart()
    assert "class='editor-tb wiki-tb wiki-linkkaart'" in html
    assert html.count("class='tb-b'") == len(_LINK_ACTIES)


def test_een_lang_adres_rekt_de_kaart_niet_uit():
    m = re.search(r"(?:^|[};])\s*\.wiki-linkurl\{([^}]*)\}", CSS, re.M)
    assert m and "text-overflow:ellipsis" in m.group(1)
    assert ".nu .wiki-linkveld" in NU, "de huisstijl kent het adresveld niet"


# ── 3. Enter levert meteen een volwaardig blok ───────────────────────────────
def test_enter_normaliseert_meteen():
    """De browser splitst netjes, maar laat een KALE tag achter: geen `.wb`, geen `data-blok`, dus
    geen greep en niet sleepbaar — tot er toevallig iets anders normaliseerde."""
    haak = _wikiedit()
    assert 'body.addEventListener("keydown"' in haak
    enter = haak.split('body.addEventListener("keydown"')[1].split("});")[0]
    assert 'e.key !== "Enter"' in enter
    assert "NV.blokNormaliseer(body)" in enter and "grepen(body, true)" in enter


def test_de_pas_draait_na_de_splitsing_en_niet_ervoor():
    """Op `keydown` bestaat de nieuwe regel nog niet; de pas zou dan het blok normaliseren dat er
    al stond. Vandaar de uitgestelde aanroep."""
    haak = _wikiedit()
    enter = haak.split('body.addEventListener("keydown"')[1].split("});")[0]
    assert "setTimeout(" in enter
    assert enter.index("setTimeout(") < enter.index("NV.blokNormaliseer")


def test_shift_enter_is_een_regelafbreking_en_geen_blok():
    haak = _wikiedit()
    enter = haak.split('body.addEventListener("keydown"')[1].split("});")[0]
    assert "e.shiftKey" in enter


def test_enter_in_een_bronveld_laat_de_tekst_met_rust():
    """In een tabel of codeblok bewerk je RUWE markdown; daar is Enter gewoon een nieuwe regel en
    heeft het blokmodel er niets te zoeken."""
    haak = _wikiedit()
    enter = haak.split('body.addEventListener("keydown"')[1].split("});")[0]
    assert "data-blok-bron" in enter


def test_het_is_hetzelfde_paar_als_overal():
    """GEEN NIEUW MECHANISME: `blokNormaliseer` + `grepen` is exact het paar dat elke andere
    DOM-wijziging hier al afsluit (de werkbalk, het blokmenu, slepen, een upload)."""
    kaal = js_zonder_uitleg(JS)
    assert kaal.count("NV.blokNormaliseer(body);") >= 5
    assert kaal.count("grepen(body, true);") >= 5
