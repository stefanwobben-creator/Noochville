"""Een keuzelijst slaat op bij het kiezen — niet na een knop ernaast (27 september 2026).

WAT ER MISGING. Op `/acties` stond achter "+ link to a project" een select met een `Link`-knop
ernaast. Twee handelingen voor één beslissing, en de tweede is precies de vergetelbare: je kiest het
project, je ziet het in de lijst staan, en er is niets gekoppeld. Het formulier zei "gekozen" en de
opslag zei niets.

Het antwoord bestond al: `_AUTOSAVE` hangt op negen keuzelijsten in `views/projects.py` (impact,
effort, eigenaar, trekker, doel, afhankelijkheid). Het comment boven de knop op `/acties` beweerde
"GEEN JAVASCRIPT" als architectuurkeuze van dat scherm — maar dat gold nooit voor dit cockpit, en
niet eens voor de buurpagina.

DEZELFDE KLASSE FOUT als `_NU_ROUTES`, `Cache-Control` en het Nederlandse zinnetje: een bestaand
patroon dat je moet KENNEN om toe te passen, en dus een keer niet toepast. Deze ratchet sluit hem:
elk formulier waarvan een keuzelijst de enige invoer is, gebruikt `onchange` óf staat hieronder met
een reden. Een nieuwe select-plus-knop komt in geen van beide en maakt dit rood.

WAT DEZE TOETS NIET IS. Hij zegt niet dat een knop fout is. Hij zegt dat de keuze bewust moet zijn,
en op één plek te lezen — precies wat `BUITEN` hieronder doet.
"""
from __future__ import annotations

import pathlib
import re

WORTEL = pathlib.Path(__file__).resolve().parents[1]
VIEWS = WORTEL / "nooch_village" / "views"

#: BEWUST MET EEN KNOP, met de reden erbij. Twee soorten, en het verschil doet ertoe:
#:
#:   * NIET HET PATROON — er is meer dan de select te vullen (tekstvelden, vinkjes), dus "kiezen is
#:     opslaan" zou halverwege het invullen versturen. De scanner ziet dat niet altijd zelf: velden
#:     die via een `{variabele}` in het formulier komen zijn vanuit de bron niet te lezen.
#:   * SCHULD — het IS een losse select met een knop. Wie er toch aan werkt, neemt hem mee.
#:
#: Deze lijst mag alleen KORTER worden.
BUITEN = {
    # ── NIET HET PATROON ──────────────────────────────────────────────────────
    "catalog_koppelen.py:_activate_section:indicator_activate":
        "vinkjes via {checks}: je kiest eerst dashboards aan, de select is de laatste stap",
    # ── SCHULD ────────────────────────────────────────────────────────────────
    "claims.py:_tab_werklijst:claims_work_status":
        "schuld — een statuscel in een tabel; zelfde omzetting als /acties, andere beurt",
    "feed.py:_keep_in_wiki_form:keep_in_wiki":
        "schuld — 'Keep' schrijft een feit op een wikipagina; de knop is nu de bevestiging",
    "overview.py:_middel_picker:skilllink_add":
        "schuld — koppelt een dorpsmiddel aan een accountability",
    "overview.py:render_rolefillers:role_assign":
        "iemand toewijzen is een besluit, geen veldwijziging: de knop is de bevestiging "
        "(en 'wijs niemand toe zonder te vragen' is hier een staande afspraak)",
    "projects.py:_orphans_html:proj_setowner":
        "schuld — herstelscherm voor wezen, naast een archiveer- en een verwijderknop",
    "wiki.py:_sectie_form:pagina_sectie":
        "schuld — verplaatst een pagina in de navigatie",
}


# ══ De scanner ═══════════════════════════════════════════════════════════════
def _zonder_commentaar(src: str) -> str:
    """Regels die alleen commentaar zijn eruit, met behoud van de regelnummering.

    NODIG, niet netjes: de invoerbalk in `messages.py` LEGT UIT dat een `<form>` in een `<form>`
    geen HTML is. Zonder deze stap leest de scanner die uitleg als een formulier — zelfde les als
    bij `test_de_oude_stylesheet_is_niet_aangeraakt`, dat zijn eigen documentatie verbood.
    """
    return "\n".join("" if r.lstrip().startswith("#") else r for r in src.splitlines())


def _defs(src: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(1)) for m in re.finditer(r"^(?:async )?def (\w+)", src, re.M)]


def _omvattende_def(defs: list[tuple[int, str]], pos: int) -> str:
    naam = "<module>"
    for start, n in defs:
        if start > pos:
            break
        naam = n
    return naam


def _keuzelijst_formulieren() -> dict[str, dict]:
    """Elk formulier waarvan een keuzelijst de enige invoer is, als `bestand:def:actie`.

    ZICHTBARE INVOER is een letterlijke `<input>` zonder `hidden`, een `<textarea>`, of een
    `_field(...)`-aanroep (die helper rendert er altijd één). Verborgen velden tellen niet mee: die
    dragen csrf, id en next, en daar kiest niemand iets.
    """
    gevonden: dict[str, dict] = {}
    for pad in sorted(VIEWS.glob("*.py")):
        src = _zonder_commentaar(pad.read_text(encoding="utf-8"))
        defs = _defs(src)
        for m in re.finditer(r"<form\b", src):
            eind = src.find("</form>", m.start())
            if eind < 0:
                continue
            blok = src[m.start():eind]
            if len(re.findall(r"<select\b", blok)) != 1:
                continue
            zichtbaar = [x for x in re.findall(r"<input\b[^>]*>", blok) if "hidden" not in x]
            if zichtbaar or "<textarea" in blok or "_field(" in blok:
                continue
            actie = re.search(r"name='action'[^>]*?value='([a-z0-9_]+)'", blok)
            sleutel = (f"{pad.name}:{_omvattende_def(defs, m.start())}:"
                       f"{actie.group(1) if actie else '?'}")
            gevonden[sleutel] = {"onchange": "onchange" in blok,
                                 "regel": src[:m.start()].count("\n") + 1,
                                 "blok": blok}
    return gevonden


# ══ De ratchet ═══════════════════════════════════════════════════════════════
def test_elke_losse_keuzelijst_heeft_een_keuze():
    """DE HELE POINTE. Een select als enige invoer slaat op bij het kiezen, of staat in `BUITEN`
    met een reden — niet in geen van beide, want dat is precies hoe `/acties` zijn knop kreeg."""
    zwevend = {s: v["regel"] for s, v in _keuzelijst_formulieren().items()
               if not v["onchange"] and s not in BUITEN}
    assert not zwevend, (
        f"keuzelijst met een knop en zonder besluit: {zwevend}. Zet `onchange='{{_AUTOSAVE}}'` op de "
        f"select en laat de knop weg, of zet hem in `BUITEN` in deze toets, met een reden.")


def test_de_uitzonderingen_bestaan_nog():
    """Een formulier dat verdwijnt of omgezet wordt hoort ook hier weg; anders dekt de lijst iets
    af wat er niet meer is en verbergt hij de volgende vergissing."""
    gevonden = _keuzelijst_formulieren()
    weg = [s for s in BUITEN if s not in gevonden]
    om = [s for s in BUITEN if s in gevonden and gevonden[s]["onchange"]]
    assert not weg, f"staat in BUITEN maar bestaat niet meer: {sorted(weg)}"
    assert not om, f"gebruikt nu autosave — haal hem uit BUITEN: {sorted(om)}"


def test_de_lijst_mag_alleen_korter():
    """Monotone daling, zoals de inline-style- en de `_NU_ROUTES`-ratchet."""
    assert len(BUITEN) <= 7, f"{len(BUITEN)} uitzonderingen — de lijst is gegroeid"


def test_de_scanner_vindt_de_bekende_gevallen():
    """Een scanner die niets vindt is altijd groen. Deze telling is zijn ondergrens: de negen
    keuzelijsten in `views/projects.py` die het patroon al volgden."""
    gevonden = _keuzelijst_formulieren()
    met_autosave = [s for s, v in gevonden.items() if v["onchange"]]
    assert len(gevonden) >= 15, f"de scanner vindt er nog maar {len(gevonden)}"
    assert len([s for s in met_autosave if s.startswith("projects.py:")]) >= 7


def test_een_verborgen_veld_maakt_een_formulier_niet_ongeschikt():
    """De scanner-regel zelf, op een minivoorbeeld: csrf en next mogen erin staan zonder dat het
    formulier daarmee 'meer invoer dan de select' heeft."""
    assert "acties.py:_meta:actie_koppel" in _keuzelijst_formulieren()


# ══ Eén definitie van het snippet ════════════════════════════════════════════
def test_het_snippet_staat_op_precies_een_plek():
    """De reden dat hij verhuisde. Twee kopieën van dit stukje JS drijven uiteen zodra er één
    browser-eigenaardigheid bijkomt, en dan doet de ene helft van het cockpit iets anders dan de
    andere — `reference, don't copy`, harde regel."""
    snippet = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"
    bronnen = [p for p in (WORTEL / "nooch_village").rglob("*.py")
               if snippet in p.read_text(encoding="utf-8")]
    assert [p.name for p in bronnen] == ["cockpit2_util.py"], [str(p) for p in bronnen]


def test_de_views_lenen_hem_uit_de_gedeelde_laag():
    from nooch_village.cockpit2_util import _AUTOSAVE
    from nooch_village.views import acties as A
    from nooch_village.views import projects as P
    assert A._AUTOSAVE is _AUTOSAVE and P._AUTOSAVE is _AUTOSAVE


# ══ De koppel-select op /acties ══════════════════════════════════════════════
ROL = "mother_earth__nooch__compliance"


def _koppelformulier(tmp_path):
    """Het echte fragment uit de view: één actie, en één project dat deze mens mag zien."""
    from nooch_village import cockpit2
    from nooch_village.views.acties import _meta
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for f in list(st.assign.fillers_of(ROL, st.records.get(ROL))):
        st.assign.unassign(ROL, f.type, f.id)
    mens = st.people.add("Aap Een", "aap@test.nl")
    st.assign.assign(ROL, "person", mens.id)
    st.projects.create(ROL, "Mycelium-proef", "human", status="running")
    it = st.acties.add(mens.id, "Bel Selco terug")
    return _meta(st, it, mens.id, "TOK"), st, dd, mens, it


def test_de_koppelselect_heeft_geen_knop_meer(tmp_path):
    h, *_ = _koppelformulier(tmp_path)
    assert "<select" in h and "onchange=" in h
    assert "<button" not in h, "er staat nog een knop in het koppelformulier"
    assert ">Link<" not in h


def test_de_actie_verhuisde_naar_een_verborgen_veld(tmp_path):
    """Zonder knop is er niets meer dat `name='action'` kan dragen. Staat die naam nergens, dan
    komt het bericht bij de dispatch aan zonder te zeggen wat het wil."""
    h, *_ = _koppelformulier(tmp_path)
    assert "<input type='hidden' name='action' value='actie_koppel'>" in h


def test_wat_de_browser_verstuurt_koppelt_echt(tmp_path):
    """DE KETEN TOT HET EIND, niet de vorm. Alleen de velden die in dít formulier staan gaan naar
    de echte dispatch-tak — de actienaam inbegrepen, want die komt nu uit de HTML."""
    from nooch_village import cockpit2
    h, st, dd, mens, it = _koppelformulier(tmp_path)

    velden = {m.group(1): m.group(2)
              for m in re.finditer(r"<input type='hidden' name='(\w+)' value='([^']*)'>", h)}
    # Wat de browser meestuurt voor de select: zijn naam plus de gekozen optie.
    naam = re.search(r"<select[^>]*name='(\w+)'", h).group(1)
    pid = re.findall(r"<option value='([^']+)'", h)[0]
    velden[naam] = pid
    assert velden.get("action") == "actie_koppel" and velden["aid"] == it["id"]

    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt=velden["next"],
                        form=velden, username=mens.email, action=velden["action"],
                        data_dir=dd)
    pad, melding = cockpit2.ACTIONS[velden["action"]](ctx)
    assert pad == "/acties" and melding.startswith("🔗"), melding
    assert st.acties.get(it["id"])["project"] == pid
