"""Het werkoverleg-scherm na de feedbackronde van 22 september 2026.

DE GEDEELDE OORZAAK STOND IN ÉÉN CSS-BLOK. Elf klassen kregen daar hetzelfde volle 2px-kader:
een kaart-behandeling voor dingen die geen kaart zijn. Een deelnemersrij stond in een hok, een
formulierrij stond in een hok, en het veld dáárin had zijn eigen onderlijn — twee lijnen om
hetzelfde ding. De regel die dat verbiedt stond al twintig regels hoger in hetzelfde bestand
("een besturingselement draagt een ONDERLIJN, een kaart draagt een kader"); dit blok hield zich
er niet aan.

EN ÉÉN DING DAT NIEMAND ZAG: `input` ZONDER `type` kreeg helemaal niets. `input[type=text]`
matcht een `<input name=...>` niet — het attribuut moet er staan. In de views staan er 47 zonder,
waaronder het agendaveld van het overleg. Die velden hadden dus nooit een onderlijn en nooit een
groene focus, en dat was precies waar het kader omheen viel op te vallen.

De rest van dit bestand toetst de losse punten: de schil met linkernavigatie, de uitleg eruit,
het stappenmenu op nav-maat, de checklist zonder geel, de kolomtinten uit één bron, de twee
knoppen die niet meer op elkaar lijken, en de confetti.
"""
from __future__ import annotations

import os
import re

from nooch_village import cockpit2

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
NU = open(os.path.join(BASIS, "nooch_village", "static", "nooch-ui.css"), encoding="utf-8").read()
JS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.js"), encoding="utf-8").read()
WEB = open(os.path.join(BASIS, "nooch_village", "web_base.py"), encoding="utf-8").read()
WO = open(os.path.join(BASIS, "nooch_village", "views", "werkoverleg.py"), encoding="utf-8").read()


def _zonder_commentaar(css: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def _regels(css: str):
    """(selector-lijst, declaraties) per regel, commentaar eruit."""
    return re.findall(r"([^{}]+)\{([^{}]*)\}", _zonder_commentaar(css))


def _body_van(css: str, selector: str) -> str:
    """De declaraties van de regel waarvan `selector` een van de selectors is."""
    for sel, body in _regels(css):
        if selector in [s.strip() for s in sel.split(",")]:
            return body
    return ""


# ── 0. De gedeelde oorzaak ──────────────────────────────────────────────────────────────────
def test_een_rij_en_een_veldwrapper_krijgen_geen_kaartrand():
    """De vijf die eruit moesten: twee formulierrijen, een raster en twee veld-wrappers, plus
    de deelnemersrij. Wat blijft zijn de knopjes en badges — die zijn wél een omhulsel."""
    for sel in (".nu .rov-add", ".nu .rov-addrow", ".nu .rov-addgrid",
                ".nu .rovm-field", ".nu .rov-editor", ".nu .wo-mem"):
        body = _body_van(NU, sel)
        assert "var(--nu-border)" not in body, f"{sel} draagt nog het volle kader"
    # ... en de tegenhanger: wie er wél in hoort, staat er nog in.
    blok = _body_van(NU, ".nu .cl-check")
    assert "var(--nu-border)" in blok
    assert ".nu .rovm-item" in NU               # houdt zijn rand: is-new/is-del variëren erop


def test_de_deelnemersrij_scheidt_met_een_lijn():
    body = _body_van(NU, ".nu .wo-mem")
    assert "border-bottom" in body and "--nu-border-subtle" in body
    assert "border: 0" in body


def test_een_input_zonder_type_krijgt_de_onderlijn_en_de_groene_focus():
    """DIT WAS HET STILLE DEEL VAN DE BUG. `<input name='naam'>` is een tekstveld, maar
    `input[type=text]` matcht hem niet. Het agendaveld van het overleg is er zo een."""
    # OP DE LOSSE SELECTOR, NIET OP EEN SUBSTRING. De eerste versie zocht
    # `"input:not([type])" in sel`, en dat matcht óók de focus-regel — die haalde de assert dus
    # in zijn eentje. Hem uit de onderlijn-regel slopen liet de test groen; een mutatie-controle
    # liet dat zien.
    def _selectors(rij_filter):
        uit = set()
        for sel, body in _regels(NU):
            if rij_filter(body):
                uit |= {re.sub(r"\s+", " ", s.strip()) for s in sel.split(",")}
        return uit

    onderlijn = _selectors(lambda b: "border-bottom: 1.5px solid var(--nu-text)" in b)
    focus = _selectors(lambda b: "border-bottom-color: var(--nu-accent)" in b)
    assert ".nu input:not([type])" in onderlijn, "geen onderlijn voor een input zonder type"
    assert ".nu input:not([type]):focus" in focus, "geen groene focus voor een input zonder type"
    # En het veld waar het om begon draagt inderdaad geen type.
    vangst = open(os.path.join(BASIS, "nooch_village", "views", "vangst.py"), encoding="utf-8").read()
    rij = vangst.split("class='rov-add'")[1][:400]
    assert "name='punt'" in rij and "type=" not in rij.split("name='punt'")[0][-60:]


# ── 1-2. De schil, en de handleiding eruit ──────────────────────────────────────────────────
def test_het_overleg_heeft_dezelfde_linkernavigatie_als_de_rest(tmp_path):
    """HET WERKOVERLEG WAS HET ENIGE VOLLEDIGE SCHERM ZONDER LINKERMENU — ook als het overleg
    gewoon liep. Niet alleen de nog-niet-geopende stand, de héle route.

    GERENDERD EN NIET GEGREPT. De eerste versie zocht `"_nav()" in WO`, en die string stond in
    de docstring van `_wo_schil` — de test las dus zijn eigen uitleg en bleef groen met de
    aanroep eruit gesloopt. Nu: de pagina opbouwen en kijken of de navigatie er echt in zit,
    in allebei de standen."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    C = "mother_earth__nooch"
    dicht = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, csrf_token="t")
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    open_ = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t")
    for naam, html in (("nog niet geopend", dicht), ("open", open_)):
        assert "c2-side" in html and "c2-subnav" in html, f"geen linkermenu in de stand '{naam}'"
    # De fragment-stand (in de modal) levert juist ALLEEN de inhoud: daar is de pagina er al.
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t",
                                       fragment=True)
    assert "c2-side" not in frag


def test_de_nog_niet_geopende_stand_is_hetzelfde_scherm(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    C = "mother_earth__nooch"
    frag = cockpit2.render_werkoverleg(st, C, csrf_token="t", fragment=True)
    assert "wo-grid" in frag and "wo-left" in frag and "wo-mid" in frag   # dezelfde indeling
    assert "wo-head" in frag                                             # en dezelfde kop
    assert "Fixed order:" not in frag                                    # de opsomming eruit
    assert "wo-timer" not in frag and "leave meeting" not in frag        # er loopt niets


def test_de_bedieningshandleidingen_zijn_weg():
    assert "Who is joining?" not in WO
    assert "Did this meeting give you what you needed?" not in WO


# ── 3. Het stappenmenu op nav-maat ──────────────────────────────────────────────────────────
def test_het_stappenmenu_staat_op_dezelfde_maat_als_de_navigatie():
    nav = _body_van(CSS, ".c2-subnav a")
    stap = _body_van(CSS, ".wo-step")
    for eig in ("font-size", "font-weight", "padding"):
        a = re.search(rf"{eig}:([^;]+)", nav)
        b = re.search(rf"{eig}:([^;]+)", stap)
        assert a and b and a.group(1).strip() == b.group(1).strip(), \
            f"{eig}: nav={a and a.group(1)} step={b and b.group(1)}"


def test_het_stappenmenu_doet_mee_in_de_nu_laag():
    """Gelijktrekken in nooch.css alleen sloot het gat niet: /werkoverleg is een nu-route, en
    daar wint deze laag. Stond `.wo-step` er niet in, dan bleef het menu kleine letters houden
    naast een navigatie in hoofdletters."""
    for sel, body in _regels(NU):
        if ".nu .wo-step" in sel and "text-transform" in body:
            assert ".nu .c2-subnav a" in sel, "wo-step hoort in DEZELFDE regel als de navigatie"
            return
    raise AssertionError(".nu .wo-step krijgt geen navigatie-behandeling")


# ── 4. De checklist zonder geel ─────────────────────────────────────────────────────────────
def test_de_te_doen_rij_is_niet_meer_geel():
    body = _body_van(CSS, ".cl-todo")
    assert "yellow" not in body
    assert "background" not in body                     # geen vulling meer
    assert "dashed" in body                             # de vorm blijft de drager


def test_elke_checklistrij_lijnt_links_gelijk_uit():
    """Zonder dit schoof de tekst van een rij MET status 3px op ten opzichte van de rij erboven:
    de markering stond alleen op de statusrijen."""
    rij = _body_van(CSS, ".cl-row")
    assert "border-left" in rij and "transparent" in rij
    assert "padding" in rij and re.search(r"padding:[^;]*\.5rem", rij)


# ── 5. De kolomtinten: één bron, en wacht is rood ───────────────────────────────────────────
def test_de_kolomtinten_staan_op_precies_een_plek():
    """De `.nu`-laag overschreef ze eerder met één vlakke achtergrond, dus de kleurcodering was
    op élk scherm weg waar iemand het bord bekijkt. Nu verwijzen beide lagen naar dezelfde vier
    namen — verandert een tint, dan verandert hij op één plek."""
    assert "--col-wacht:" in WEB, "de tokens horen bij de andere tokens in web_base"
    assert "--col-wacht:" not in CSS and "--col-wacht:" not in NU
    for laag, naam in ((CSS, "nooch.css"), (NU, "nooch-ui.css")):
        assert "var(--col-wacht)" in laag, f"{naam} verwijst niet naar de tint"


def test_wacht_is_rood_en_niet_meer_amber():
    """Founder-besluit 22 september 2026, expliciet over een eerdere bewuste keuze heen."""
    tok = re.search(r"--col-wacht:([^;]+)", WEB).group(1).strip()
    rand = re.search(r"--colb-wacht:([^;]+)", WEB).group(1).strip()
    assert tok.upper() == "#FDEAEA"                     # dezelfde tint als --error-tint
    assert rand.upper() == "#FF6B5B"                    # dezelfde als --coral
    assert "#fdf3e4" not in CSS.lower(), "de amber-tint staat er nog"


def test_de_kolommen_dragen_naast_de_tint_nog_steeds_een_vorm():
    """De tint komt terug, de regel niet weg: status mag nooit alleen kleur zijn. Het merkteken
    vóór de kop blijft dus staan, voor alle vier."""
    # Op de GEPARSEERDE selectors, niet op de ruwe tekst: die laatste zou omvallen op een
    # spatie meer of minder, en dat zegt niets over wat er op het scherm staat.
    merken = {re.sub(r"\s+", " ", s.strip()) for sel, _b in _regels(NU) for s in sel.split(",")}
    for sleutel in ("actief", "wacht", "done", "toekomst"):
        assert any(f"data-to='{sleutel}'" in m and "::before" in m for m in merken), sleutel


# ── 7. Opslaan en Afgetikt lijken niet meer op elkaar ───────────────────────────────────────
def test_opslaan_is_groen_en_afgetikt_niet(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    C = "mother_earth__nooch"
    st = cockpit2._Stores(dd)
    st.people.add("Tester", "t@nooch.earth")
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "vangst_add", {"circle": [C], "punt": ["Een punt"], "next": ["/"]},
                      username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t",
                                       fragment=True)
    opslaan = frag.split("value='vangst_uitkomst'")[0][-120:]
    aftik = frag.split("value='vangst_klaar'")[0][-160:]
    assert "btn ok sm" in opslaan, "Opslaan hoort de primaire groene knop te blijven"
    assert "wo-aftik" in aftik and "ok" not in aftik.split("class='")[-1].split("'")[0]
    assert "wo-afronden" in frag                         # en hij staat achter een scheidingslijn


def test_de_afsluitknop_staat_buiten_het_formulier(tmp_path):
    """"Buiten de formulier-kaart geplaatst" is de eis; hier gemeten op de structuur en niet op
    de klassenaam."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    C = "mother_earth__nooch"
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "vangst_add", {"circle": [C], "punt": ["Een punt"], "next": ["/"]},
                      username="guest")
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t",
                                       fragment=True)
    formulier = frag.split("class='wo-oc'")[1].split("</form>")[0]
    assert "vangst_klaar" not in formulier


# ── 8. De viering ───────────────────────────────────────────────────────────────────────────
def test_sluiten_zet_een_vlaggetje_in_de_url(tmp_path):
    """EEN PARAMETER, GEEN TEKSTVERGELIJKING. Matchen op de melding zou betekenen dat het feest
    uitgaat zodra iemand die zin vertaalt."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    C = "mother_earth__nooch"
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    nxt, msg = cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": [f"/node?id={C}"]},
                                 username="guest")
    assert "feest=wo" in nxt and nxt.startswith("/node?id=")
    assert msg.startswith("✓")


def test_de_viering_ruimt_zichzelf_op_en_respecteert_reduced_motion():
    blok = JS.split("function feest")[1].split("\n  }")[0]
    assert "history.replaceState" in blok, "een refresh zou dan opnieuw vieren"
    assert "prefers-reduced-motion" in blok
    assert "setTimeout" in blok and "remove()" in blok
    assert "pointer-events" in _body_van(CSS, ".feest")
    # en hij staat óók in het reduced-motion-blok van de stylesheet
    rm = CSS.split("@media (prefers-reduced-motion: reduce)")[1].split("\n}")[0]
    assert ".feest{display:none}" in rm.replace(" ", "")


def test_de_viering_is_bedraad():
    wire = JS.split("NV.wire = function")[1].split("};")[0]
    assert "feest(root)" in wire
