"""Fase 11, laag 3 — het sleeppatroon op het bord, en de klik in de checklist.

GEDRAGSSPEC: het prototype-artboard `project/Main.dc.html`, sectie 2 ("Trello — sleep een kaart,
en de kolom reageert direct") en sectie 3 (klik een item aan, de balk schuift mee). Wat daar
gebeurt en hier ontbrak, in volgorde van hoe erg het was:

  1. **de doelkolom lichtte niet op.** De JS zette al een `.over`-klasse en er was geen enkele
     CSS-regel die daar iets mee deed — het bord gaf tijdens het slepen dus géén terugkoppeling.
  2. het oppakken had geen affordance: geen grab-cursor, geen lift, geen hintje.
  3. en tijdens het slepen viel de lift juist wég, want de native HTML5-sleepafbeelding is een
     platte momentopname die je niet kunt stylen. Stefans aanscherping ging hierover: het
     "optillen" stopte precies waar het hoorde te beginnen.

WAT DEZE TESTS WÉL EN NIET KUNNEN. Ze toetsen de bedrading en de stijlregels, niet het gevoel —
dat laatste is met de hand tegen het prototype gelopen. Wat ze bewaken is dat de drie bovenstaande
dingen niet stilletjes terugvallen: één gedeeld patroon in plaats van twee kopieën, een `.over` die
iets dóét, en een ghost die blijft bestaan.
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
CSS = (REPO / "nooch_village" / "static" / "nooch.css").read_text()
NU = (REPO / "nooch_village" / "static" / "nooch-ui.css").read_text()
JS = (REPO / "nooch_village" / "static" / "nooch.js").read_text()
VIEW = (REPO / "nooch_village" / "views" / "projects.py").read_text()


def _regels(css: str):
    """(selector, declaraties) per regel, commentaar eruit. Parsen in plaats van zoeken: `.pcard`
    en `.pcol` staan op twee plekken in het bestand en een van die twee wordt voorafgegaan door
    een comment in plaats van een `}` — een regex op de ruwe tekst vond er dan maar één."""
    ont = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", ont):
        yield " ".join(m.group(1).split()), " ".join(m.group(2).split())


def _body(css: str, selector: str) -> str:
    """Alle declaraties die deze selector krijgt, samen — de cascade is de som."""
    delen = [b for sel, b in _regels(css) if sel == selector]
    assert delen, f"{selector} bestaat niet"
    return " ".join(delen)


def _js_code() -> str:
    """De JS zonder commentaar. De kop van `NV.bord` legt uit waarom `setDragImage` niet deugt;
    een assertie over de hele bron zou die uitleg verbieden in plaats van het gedrag."""
    zonder_blok = re.sub(r"/\*.*?\*/", "", JS, flags=re.S)
    return "\n".join(r for r in zonder_blok.splitlines() if not r.strip().startswith("//"))


# ── 1. de kolom reageert ─────────────────────────────────────────────────────────────────────

def test_de_doelkolom_licht_op_met_twee_dragers():
    """DE KERN VAN SECTIE 2, en het enige dat volledig ontbrak: `.over` werd gezet en deed niets.
    Twee dragers, niet één — dezelfde regel als bij de statusindicatoren."""
    basis = _body(CSS, ".pcol.over,.pcol[data-to].over")
    assert "background" in basis and "border-color" in basis
    nu = _body(NU, ".nu .pcol.over, .nu .pcol[data-to].over")
    assert "var(--nu-bg-alt)" in nu and "var(--nu-accent)" in nu     # de tokens van het systeem
    assert "transition" in _body(CSS, ".pcol")                       # hij schuift, springt niet


# ── 2. het oppakken ──────────────────────────────────────────────────────────────────────────

def test_de_kaart_nodigt_uit_om_opgepakt_te_worden():
    assert "cursor:grab" in _body(CSS, ".pcard")
    assert "cursor:grabbing" in _body(CSS, ".pcard:active")
    assert "translateY(-3px)" in _body(CSS, ".pcard:hover")          # de lift uit het prototype


def test_het_hintje_verschijnt_bij_hover_en_verdwijnt_tijdens_het_slepen():
    """"sleep me" op een kaart die je vasthoudt is ruis: dan weet je het al."""
    assert "opacity:0" in _body(CSS, ".pcard-hint")
    assert "opacity:1" in _body(CSS, ".pcard:hover .pcard-hint")
    verborgen = _body(CSS, ".pcard.pdrag-bron .pcard-hint,.pdrag-ghost .pcard-hint")
    assert "opacity:0" in verborgen


def test_het_hintje_staat_alleen_op_een_kaart_die_je_kunt_slepen():
    """Zonder csrf is er geen sleep-JS; dan is de belofte vals."""
    from types import SimpleNamespace
    import tempfile
    from nooch_village import cockpit2
    from nooch_village.views.projects import _proj_card
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create("mother_earth__nooch__creator_of_shoes", "Sleeptest", "human",
                             status="running")
    p = st.projects.get(pid)
    assert "pcard-hint" in _proj_card(st, p, "TOK", "/projects")
    assert "pcard-hint" not in _proj_card(st, p, "", "/projects")


# ── 3. de affordance die tijdens het slepen ZICHTBAAR BLIJFT ─────────────────────────────────

def test_de_opgetilde_kaart_blijft_opgetild():
    """Stefans aanscherping. De native sleepafbeelding kan dit niet; daarom een eigen ghost."""
    ghost = _body(CSS, ".pdrag-ghost")
    assert "position:fixed" in ghost and "pointer-events:none" in ghost
    assert "box-shadow" in ghost                                     # hij zweeft …
    assert "scale(1.04)" in JS and "rotate(-2deg)" in JS             # … schaalt en kantelt
    assert "translate3d" in JS                                       # en volgt de pointer
    assert "opacity:.35" in _body(CSS, ".pcard.pdrag-bron")          # de plek van herkomst blijft


def test_de_native_sleep_is_vervangen_en_niet_aangevuld():
    """Twee implementaties naast elkaar is hoe ze uit elkaar gaan lopen — en dat wás de situatie:
    de volle pagina en de modal droegen elk hun eigen kopie, allebei zonder kolom-oplichting."""
    assert "dragstart" not in VIEW and "dataTransfer" not in VIEW
    assert VIEW.count("NV.bord(") == 2                               # beide schermen, één patroon
    assert "setDragImage" not in _js_code()                          # geen halve native-oplossing


def test_slepen_blijft_een_versnelling_en_geen_vervanging():
    """De toegankelijkheidsval uit de spec: op touch gebeurt er niets (anders blokkeer je scrollen
    op een telefoon), en de knop/dropdown op de kaart blijft de andere weg."""
    assert 'pointerType === "touch"' in JS
    assert 'closest("a,button,input,select,textarea,summary")' in JS  # knoppen blijven knoppen


def test_een_klik_is_geen_sleep():
    """Zonder drempel wordt elke klik op een kaart een minisleep, en dan opent het detail niet meer."""
    assert "DREMPEL" in JS and "var DREMPEL = 5" in JS
    assert "if (!bezig) return;" in JS                                # onder de drempel: gewoon een klik


# ── 4. sectie 3: de klik in de checklist ─────────────────────────────────────────────────────

def test_de_voortgangsbalk_schuift_mee_in_plaats_van_te_springen():
    """Prototype sectie 3: `transition:width .35s ease` op de vulling. Zonder dat springt de balk
    en zie je de verandering niet gebeuren — precies wat "direct zichtbaar effect" moet zijn."""
    assert "transition:width .35s ease" in CSS.replace("\n  ", "")
    assert "transition: width .35s ease" in NU


def test_de_checklist_klik_beweegt_de_balk_zonder_te_wachten():
    """De microinteractie zelf staat sinds laag 2 in `_CK_LIVE_JS`; deze test bindt hem aan de
    spec van sectie 3 zodat hij niet losraakt van waar hij vandaan komt."""
    assert "data-ck-bar" in JS and "bar.value" in JS
    assert "ck-done" in JS                                            # doorhaling van de tekst
    # EN HIJ MOET IN DE MODAL WERKEN. Als `<script>` in het fragment deed hij dat niet — innerHTML
    # voert scripts niet uit — en de kaart opent normaal juist in de modal. Eén gedelegeerde
    # listener op `document` bestaat al vóór het fragment er is.
    view = (REPO / "nooch_village" / "views" / "checklists.py").read_text()
    assert "_CK_LIVE_JS" not in view, "de microinteractie hoort in het gedeelde bestand"
    assert 'document.addEventListener("click"' in JS
