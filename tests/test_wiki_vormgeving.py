"""De drie vormgevingspunten uit het ontwerp (24 september 2026).

1. DE BEWERKRAND WAS FELGROEN. `.wiki-aan` zette een accentlijn van 3px in `--green`, en dat is de
   kleur die dit dorp voor ACTIE gebruikt (opslaan, een live overleg, een goedgekeurde stand).
   Voor "je staat nu in de tekst" is dat te luid: het signaal hoort te zeggen waar je cursor is,
   niet dat er iets gebeurd is. De lijn blijft — hij is de enige drager naast de cursor — maar in
   een rustige tint.

2. DE KOPBALK HAD DRIE LOSSE DINGEN. De regel met de eigenaar, het domein-formulier en de
   bewerkknop stonden als drie flex-kinderen in een `space-between`, dus het domein zweefde
   ergens in het midden. Nu twee zones: HERKOMST links, ACTIES rechts. Dat is dezelfde indeling
   als elke andere kopbalk in het dorp.

3. ONDERSCHEID PER DATASOORT was het derde punt, en dat is grotendeels al geleverd door de
   blokken zelf: een codeblok, een tabel, een taak en een embed hebben elk hun eigen vorm. Wat
   deze toetsen bewaken is dat die vormen ook ECHT verschillen — niet dat er nog een laag kleur
   overheen komt. Kleur bovenop vorm is een tweede systeem, en dat was juist het probleem.
"""
from __future__ import annotations

import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()


def _regel(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", CSS)
    assert m, f"{selector} bestaat niet meer"
    return m.group(1)


# ── 1. De bewerkrand ─────────────────────────────────────────────────────────
def test_de_bewerkrand_is_niet_meer_de_actiekleur():
    """`--green` is in dit dorp de kleur van ACTIE — opslaan, een live overleg, een goedgekeurde
    stand. "Je staat in de tekst" is geen actie."""
    body = _regel(".wiki-aan")
    assert "var(--green)" not in body, "de bewerkrand is nog steeds de actiekleur"


def test_de_bewerkrand_bestaat_nog_wel():
    """Hij is de enige zichtbare drager naast de cursor; weghalen zou betekenen dat je niet meer
    ziet dát je in de tekst staat."""
    body = _regel(".wiki-aan")
    assert "box-shadow" in body and "cursor:text" in body


def test_er_komt_geen_kader_omheen():
    """Vastgelegd in fase 12: een kader is container-taal, en dit is een veld. Dat besluit staat
    nog, dus de rustiger tint mag geen `border` worden."""
    body = _regel(".wiki-aan")
    assert "border:" not in body


# ── 2. De kopbalk ────────────────────────────────────────────────────────────
def test_de_kopbalk_heeft_twee_zones(tmp_path):
    """Herkomst links, acties rechts — in plaats van drie losse dingen in een space-between."""
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    rec = st.records.get(rol)
    rec.definition.domains = ["Materials", "Decision Making"]
    st.records.put(rec)
    mens = st.people.add("B", "b@t.nl")
    st.assign.assign(rol, "person", mens.id)
    a = st.att.add(rol, "note", title="X", body="tekst", domain="Materials")
    from nooch_village.views.wiki import render_pagina
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")

    balk = html.split("wiki-kopbalk'>")[1].split("</div></div>")[0]
    assert "wiki-kopacties" in balk, "er is geen actie-zone"
    # DE ZONE DRAAGT DE HOOFDACTIE. Hier stond ook dat het domein-formulier er in zat, en dat
    # klopte niet meer sinds #602 het veld naar het metadata-blok verplaatste — de toets slaagde
    # alleen nog omdat dat blok toevallig direct achter de kop stond en binnen de 900 tekens viel.
    # Met het blok onderaan (26 september) valt die toevalligheid weg. Wat de zone bewijst is dat
    # de acties bij elkaar staan, en dat is er precies één: bewerken.
    acties = html.split("wiki-kopacties'>")[1]
    assert "data-wiki-start" in acties.split("</div>")[0]


def test_de_actie_zone_staat_rechts():
    body = _regel(".wiki-kopacties")
    assert "display:flex" in body.replace(" ", "")


# ── 3. Onderscheid per datasoort ─────────────────────────────────────────────
def test_elke_datasoort_heeft_een_eigen_vorm():
    """Niet kleur bovenop vorm — dat zou een tweede systeem zijn. Elk bloktype heeft zijn eigen
    vormgeving, en die zijn hier alle vier aanwezig."""
    # `.att-body` EN NIET `.wb`: een policy of tool rendert sinds #574 op een leespagina zonder
    # blok-wrappers, en juist daar staan de tabellen en het codeblok. Zie
    # tests/test_wiki_leespagina_stijl.py.
    for selector in (".att-body pre", ".att-body table", ".wb-taak input", ".wb-emb"):
        assert re.search(re.escape(selector) + r"\{", CSS), f"{selector} heeft geen eigen vorm"


def test_de_soorten_leunen_op_vorm_en_niet_op_kleur_alleen():
    """Elk van de vier onderscheidt zich met iets structureels (rand, achtergrond, layout), niet
    met alleen een tekstkleur — dezelfde regel als "twee dragers" bij de statusvormen."""
    for selector in (".att-body pre", ".att-body table", ".wb-emb"):
        body = _regel(selector)
        assert any(k in body for k in ("border", "background", "display:flex")), selector


# ── 4. Chrome verdwijnt niet bij het bewerken ────────────────────────────────
def test_bewerken_haalt_alleen_de_grepen_weg_en_niet_alle_chrome():
    """GEZIEN IN DE BROWSER, niet in een toets. `grepen()` verwijderde álle `[data-chrome]` en
    haalde daarmee ook het icoon en het herkomst-label van een embed-kaart weg: zodra je "Edit
    page" klikte stond die kaart er kaal bij. Geen dataverlies — de server rendert ze bij het
    herladen weer — maar wel een kaart die er tijdens het bewerken anders uitziet dan erna.

    De verdediging die chrome BUITEN DE OPSLAG houdt blijft wél breed; die zit in de
    submit-handler en hoort daar."""
    import re as _re
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    js = _re.sub(r"/\*.*?\*/", " ", js, flags=_re.S)
    js = _re.sub(r"^\s*//[^\n]*", " ", js, flags=_re.M)

    i = js.index("function grepen(")
    lichaam = js[i:js.index("\n  }", i)]
    assert 'querySelectorAll(".wb-greep")' in lichaam, "grepen() sloopt nog alle chrome"
    assert 'querySelectorAll("[data-chrome]")' not in lichaam

    # en de opslag-verdediging staat er nog wél
    j = js.index("wiki-body-veld")
    assert 'querySelectorAll("[data-chrome]")' in js[:j], \
        "de verdediging die chrome buiten de opslag houdt is meegesloopt"
