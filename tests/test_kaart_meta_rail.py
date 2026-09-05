"""De kaart: alle meta rechts in één sticky rail, links een wall die gewoon doorscrollt.

De pillenrij bovenin duwde de inhoud omlaag, en status — het veld dat je het vaakst verandert —
verdween uit beeld zodra je naar de conversatie scrollde. Deze tests bevriezen de drie eisen die
daaruit volgden, want alle drie sluipen terug bij de eerstvolgende "even hier bijzetten".

OPVOLGER VAN `test_projectkaart_een_huis.py`. Dat bestand bewaakte dezelfde regel — één huis per
eigenschap — voor de chips-indeling, en die zones bestaan niet meer. De regel is niet vervallen
maar strenger geworden: hij geldt nu over drie zones (kop, wall, rail) in plaats van twee, en de
kop hoort er helemaal geen meer te dragen.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2
from nooch_village.views import projects as P

ROLE = "mother_earth__nooch__website_developer"
_CSS = pathlib.Path("nooch_village/static/nooch.css")

# Elke meta-control hoort in de RAIL. Geen enkele hoort meer boven de content.
_META = ("proj_status", "proj_done", "proj_setimpact", "proj_seteffort", "proj_settrekker",
         "proj_setdue", "proj_setprivate", "proj_setowner")
# Deze horen juist in de WALL: ze werken op de inhoud die daar staat.
_WALL = ("checklist_add", "check_add", "proj_feed", "attach_add")


def _kaart(tmp_path, **kw):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    f = st.assign.fillers_of(ROLE, record=st.records.get(ROLE))[0]
    pid = st.projects.create(ROLE, "Meta-rail", "human", status="queued", done_when="af")
    st.projects.start(pid)
    st.projects.set_due(pid, "2026-10-01")
    cockpit2.dispatch(dd, "proj_settrekker", {"pid": [pid], "trekker": [f"person:{f.id}"],
                                              "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "checklist_add", {"pid": [pid], "title": ["tasks"], "next": ["/"]},
                      username="guest")
    html = P.render_project(cockpit2._Stores(dd), pid, csrf_token=kw.get("csrf", "TOK"))
    kop = html[html.index("pkaart-head"):html.index("pkaart-body")]
    main = html[html.index("pkaart-main"):html.index("pkaart-rail")]
    rail = html[html.index("pkaart-rail"):]
    return dd, pid, html, kop, main, rail


# ── één huis per control ─────────────────────────────────────────────────────
def test_geen_meta_control_meer_boven_de_content(tmp_path):
    """De pillenrij is weg. Een control die hier terugkomt duwt de inhoud weer omlaag."""
    _, _, _, kop, _, _ = _kaart(tmp_path)
    terug = [a for a in _META if f"value='{a}'" in kop]
    assert not terug, f"meta-control terug in de kop: {terug}"
    assert "pchips" not in kop and "pchip-k" not in kop


def test_elke_meta_control_staat_in_de_rail(tmp_path):
    _, _, _, _, main, rail = _kaart(tmp_path)
    ontbreekt = [a for a in _META if f"value='{a}'" not in rail]
    assert not ontbreekt, f"meta-control niet in de rail: {ontbreekt}"
    dubbel = [a for a in _META if f"value='{a}'" in main]
    assert not dubbel, f"meta-control óók in de wall: {dubbel}"


def test_inhoud_controls_staan_juist_in_de_wall(tmp_path):
    """"+ new checklist" stond in de rail onder "Add". Hij hoort bij de checklist waar hij iets
    aan toevoegt — anders zoek je de knop op de plek waar het resultaat níet verschijnt."""
    _, _, _, _, main, rail = _kaart(tmp_path)
    ontbreekt = [a for a in _WALL if f"value='{a}'" not in main]
    assert not ontbreekt, f"inhoud-control niet in de wall: {ontbreekt}"
    dubbel = [a for a in _WALL if f"value='{a}'" in rail]
    assert not dubbel, f"inhoud-control óók in de rail: {dubbel}"


def test_archiveren_en_verwijderen_hebben_een_vaste_plek_in_de_rail(tmp_path):
    """Ze stonden onder een wall die met elk gesprek langer wordt. Een actie die verder wegzakt
    naarmate een project meer leeft, is geen bereikbare actie."""
    _, _, _, _, main, rail = _kaart(tmp_path)
    assert "proj_archive" in rail and "proj_delete" in rail
    assert "proj_archive" not in main and "proj_delete" not in main


# ── de wall scrollt door tot de onderste knop ────────────────────────────────
def test_de_wall_zit_niet_in_een_eigen_scrollbak(tmp_path):
    """GEEN GENESTE SCROLL-VAL. `.einddoc-body` had `max-height:70vh;overflow-y:auto` uit de tijd
    dat het rapport inline op de kaart stond. Zo'n bak slokt het muiswiel op, en dan is de knop
    eronder niet te bereiken. Getoetst op de STIJL, niet op een klassenaam."""
    css = _CSS.read_text(encoding="utf-8")
    for sel in (".pkaart-main{", ".einddoc-body{", ".psec-b{"):
        regel = [r for r in css.splitlines() if r.startswith(sel)]
        if regel:
            assert "max-height" not in regel[0], f"{sel} heeft een hoogte-cap: {regel[0]}"
            assert "overflow-y:auto" not in regel[0], f"{sel} scrollt zelf: {regel[0]}"


def test_de_onderste_knop_van_de_wall_staat_er_gewoon(tmp_path):
    """De bijlage-knop en alles eronder horen bereikbaar te zijn — dat was de klacht."""
    _, _, _, _, main, _ = _kaart(tmp_path)
    assert "attach_file" in main and "attach_add" in main
    assert "proj_feed" in main
    assert main.index("attach_add") > main.index("checklist_add")   # écht onderaan de wall


def test_de_rail_is_sticky(tmp_path):
    """Status moet in beeld blijven terwijl je door de conversatie scrollt. `align-self:start` is
    de voorwaarde: in een grid rekt een item anders tot volle hoogte en heeft sticky niets om aan
    te plakken."""
    css = _CSS.read_text(encoding="utf-8")
    regel = next(r for r in css.splitlines() if r.startswith(".pkaart-rail{"))
    blok = css[css.index(regel):css.index(regel) + 400]
    assert "position:sticky" in blok and "align-self:start" in blok


def test_geen_voorouder_breekt_de_sticky():
    """DE REGEL STOND ER, EN DEED NIETS. `.pkaart` had `overflow:hidden` (om de gekleurde rail
    binnen de afgeronde hoek te houden), en dat breekt `position:sticky` in élke afstammeling.
    Gemeten op het gerenderde element: de rail-top ging van 264 naar -182 bij 600px scroll — hij
    scrollde gewoon mee. Na het weghalen: 16 bij 700px en 5 bij 1400px.

    Deze test kijkt daarom niet of de sticky-regel bestaat, maar of niets hem ontkracht."""
    css = _CSS.read_text(encoding="utf-8")
    for sel in (".pkaart{", ".pkaart-body{"):
        regel = [r for r in css.splitlines() if r.startswith(sel)]
        assert regel, sel
        assert "overflow:hidden" not in regel[0], (
            f"{sel} heeft overflow:hidden — dat breekt de sticky rail: {regel[0]}")


# ── de papercuts ─────────────────────────────────────────────────────────────
def test_nieuwe_checklist_heeft_geen_naamveld_en_heet_tasks(tmp_path):
    """Vrijwel elke lijst heette "Acties uit overleg" of "Stappen" — een naam die niemand leest en
    die je wel moet verzinnen vóór je je eerste taak kwijt kunt."""
    dd, pid, _, _, main, _ = _kaart(tmp_path)
    assert "placeholder='Checklist name'" not in main
    assert "value='tasks'" in main
    cockpit2.dispatch(dd, "checklist_add", {"pid": [pid], "title": ["tasks"], "next": ["/"]},
                      username="guest")
    titels = [c["title"] for c in cockpit2._Stores(dd).projects.get(pid)["checklists"]]
    assert "tasks" in titels


def test_visible_is_een_toggle_en_geen_vinkje(tmp_path):
    """Zichtbaar is de normale toestand; de actie die je soms wilt is verbergen. Het vinkje vroeg
    je een negatieve eigenschap aan te zetten — een omweg om "hou dit binnen" te zeggen."""
    dd, pid, _, _, _, rail = _kaart(tmp_path)
    assert "only for this circle</label>" not in rail
    assert "type='checkbox'" not in rail
    assert "Whole circle tree" in rail and "proj_setprivate" in rail
    cockpit2.dispatch(dd, "proj_setprivate", {"pid": [pid], "private": ["1"], "next": ["/"]},
                      username="guest")
    html = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    rail2 = html[html.index("pkaart-rail"):]
    assert "Only this circle" in rail2                     # en terug te draaien met dezelfde knop
    assert "value=''" in rail2 or 'value=""' in rail2


def test_de_skip_knop_is_weg_maar_de_staat_blijft_werken(tmp_path):
    """Twee knoppen voor één gedachte ('dit hoeft niet meer') maakt de keuze zwaarder dan de
    handeling. De `skipped`-STAAT blijft: oude items dragen hem, en `checklist_progress` telt hem
    nog steeds correct niet mee."""
    from nooch_village.projects import checklist_progress
    _, _, _, _, main, _ = _kaart(tmp_path)
    assert "check_skip" not in main and "skip (n/a)" not in main
    cl = {"items": [{"text": "a", "done": True}, {"text": "b", "skipped": True},
                    {"text": "c", "done": False}]}
    done, telbaar = checklist_progress(cl)
    assert (done, telbaar) == (1, 2), "een overgeslagen item hoort niet mee te tellen"


def test_read_only_toont_de_meta_maar_geen_bewerkacties(tmp_path):
    _, _, _, _, _, rail = _kaart(tmp_path, csrf="")
    assert "Status" in rail and "Assignee" in rail        # lezen mag
    for a in _META:
        assert f"value='{a}'" not in rail, a


# ── een default-titel is geen naam ───────────────────────────────────────────
def test_default_checklisttitels_worden_niet_getoond():
    """Op productie heet 236 van de 273 checklists "Uitvoerplan", "tasks" of "Checklist" — de naam
    die de wizard of de puls zette, niet iets wat iemand bedacht. Een kop die op 86% van de kaarten
    hetzelfde zegt is ruis met de vorm van informatie.

    DE IDENTIFIER BLIJFT. `Uitvoerplan` gate't de Done-uitkomst, het aanbod-mechanisme, de wizard en
    de puls (`projects.PREP_CHECKLIST_TITLE`); alleen de WEERGAVE vervalt. Identifier is mechaniek,
    label is content — dezelfde scheiding als bij de verslag-voorzet."""
    from nooch_village.projects import PREP_CHECKLIST_TITLE
    from nooch_village.views.checklists import toon_titel
    for default in (PREP_CHECKLIST_TITLE, "tasks", "Checklist", "uitvoerplan", "", "   "):
        assert toon_titel(default) == "", default
    for eigen in ("Uit dialoog", "Road to Harvest Party", "Stappenplan"):
        assert toon_titel(eigen) == eigen


def test_de_identifier_zelf_blijft_ongemoeid():
    """Zou iemand `PREP_CHECKLIST_TITLE` veranderen om "de titel weg te krijgen", dan breekt de
    koppeling met de puls en de Done-uitkomst. Deze test zegt dat de weergave-regel daar niet
    voor bedoeld is."""
    from nooch_village.projects import PREP_CHECKLIST_TITLE
    assert PREP_CHECKLIST_TITLE == "Uitvoerplan"


def test_de_kaart_toont_geen_default_titel_maar_wel_een_eigen(tmp_path):
    dd, pid, _, _, main, _ = _kaart(tmp_path)
    assert "cl-title" not in main                     # "tasks" is een default
    cockpit2.dispatch(dd, "checklist_add", {"pid": [pid], "title": ["Road to Harvest Party"],
                                            "next": ["/"]}, username="guest")
    html = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "Road to Harvest Party" in html and "cl-title" in html
