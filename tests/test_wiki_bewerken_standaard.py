"""Vier aanvullingen op de wiki-pagina (26 september 2026).

1. Een lege Facts- of Links here-sectie verschijnt niet meer vanzelf onderaan. Zelf geplaatst via
   het blokmenu blijft hij wél staan, ook leeg — dat is bewuste plaatsing, geen restant.
2. "Geen domein" is een keuze in de dropdown, in plaats van stilzwijgend op de eerste waarde
   vallen.
3. Bewerken is de stand voor wie mag bewerken, niet een modus achter een knop. Opslaan blijft
   expliciet.
4. Titel en tekst zijn één doorlopend document in plaats van een kop boven een omrande kaart.
"""
from __future__ import annotations

import pathlib
import re

from conftest import js_zonder_uitleg
from nooch_village import cockpit2, wiki
from nooch_village.views.overview import _domain_field
from nooch_village.views.wiki import render_pagina

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


def _dorp(tmp_path, *, body="Gewone tekst.", feiten=(), domeinen=("bibliotheek", "materials")):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    rec = st.records.get(rol)
    rec.definition.domains = list(domeinen)
    st.records.put(rec)
    mens = st.people.add("Beheerder", "b@t.nl")
    st.assign.assign(rol, "person", mens.id)
    a = st.att.add(rol, "note", title="Een pagina", body=body)
    if feiten:
        st.att.update(a.id, meta={"feiten": [wiki.maak_feit(f) for f in feiten]})
    return dd, st, st.att.get(a.id)


def _html(tmp_path, **kw):
    dd, st, a = _dorp(tmp_path, **kw)
    return render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl"), a


# ── 1. Een lege sectie is geen sectie ────────────────────────────────────────
def test_zonder_feiten_geen_feiten_sectie(tmp_path):
    """Op de 92 pagina's van prod heeft er vandaag nul een feit, dus dit kopje stond onder élke
    tekst met "No facts yet" eronder. Dat is meubilair, geen informatie."""
    html, _a = _html(tmp_path)
    assert ">Facts</h3>" not in html


def test_zonder_backlinks_geen_links_here(tmp_path):
    html, _a = _html(tmp_path)
    assert ">Links here</h3>" not in html


def test_met_feiten_staat_de_sectie_er_wel(tmp_path):
    html, _a = _html(tmp_path, feiten=("Een schoen weegt 300 gram",))
    assert ">Facts</h3>" in html


def test_een_wens_telt_ook_als_inhoud(tmp_path):
    """De backlink-sectie draagt twee dingen: wie hierheen wijst, en waar déze pagina heen wijst
    zonder dat die pagina bestaat. Dat tweede is óók iets te melden."""
    html, _a = _html(tmp_path, body="Zie [[Een pagina die nog niet bestaat]].")
    assert ">Links here</h3>" in html
    assert "Wanted pages" in html


def test_de_verlanglijst_verschijnt_niet_zonder_reden(tmp_path):
    """De tegenproef bij de toets hierboven: zonder verwijzing ook geen sectie. Anders meet die
    alleen dat de sectie altijd verschijnt."""
    html, _a = _html(tmp_path, body="Tekst zonder enige verwijzing.")
    assert ">Links here</h3>" not in html


def test_zelf_geplaatst_blijft_staan_ook_als_hij_leeg_is(tmp_path):
    """DE UITZONDERING DIE JE ZOU VERGETEN. Wie de sectie via het blokmenu in zijn tekst zet,
    kiest die plek bewust — dan is leeg een plek die op vulling wacht, geen restant. De leeg-regel
    geldt alleen voor de sectie die er automatisch bij komt."""
    html, _a = _html(tmp_path, body="Tekst.\n\n{{facts}}\n\nMeer tekst.")
    assert ">Facts</h3>" in html
    assert "data-blok='facts'" in html, "de sectie staat niet op de plek waar hij gezet is"


def test_zelf_geplaatst_staat_er_nog_steeds_maar_een_keer(tmp_path):
    """De oude regel blijft: in de tekst óf eronder, nooit allebei."""
    html, _a = _html(tmp_path, body="Tekst.\n\n{{facts}}", feiten=("Een feit",))
    assert html.count(">Facts</h3>") == 1


# ── 2. Geen domein is een keuze ──────────────────────────────────────────────
def test_de_dropdown_kent_een_lege_keuze():
    veld = _domain_field(["bibliotheek", "materials"], huidig="")
    assert "<option value=''" in veld


def test_zonder_domein_staat_de_lege_keuze_voor():
    """DE STILLE VERPLAATSING: zonder een geselecteerde lege optie kiest de browser `option[0]`,
    dus de eerstvolgende keer opslaan zette het artefact op 'bibliotheek' — een verplaatsing die
    niemand vroeg. Precies dezelfde fout als waar `huidig` voor bestaat, aan de lege kant."""
    veld = _domain_field(["bibliotheek", "materials"], huidig="")
    eerste = veld.split("<option")[1]
    assert "selected" in eerste and "value=''" in eerste


def test_met_domein_staat_dat_domein_voor():
    veld = _domain_field(["bibliotheek", "materials"], huidig="materials")
    assert "value='materials' selected" in veld
    assert "value=''>" in veld or "value='' >" in veld    # de lege keuze blijft bereikbaar
    assert "value='' selected" not in veld


def test_de_server_schrijft_een_lege_keuze_ook_echt_weg():
    """DE UI IS MAAR DE HELFT. `_act_artefact_edit` onderscheidt AFWEZIG van LEEG — een
    ontbrekend veld laat het domein met rust (anders wiste elke tekstbewerking de indeling), een
    expliciet lege keuze wist het wél. Zonder dat onderscheid doet de nieuwe optie niets."""
    import inspect
    src = inspect.getsource(cockpit2._act_artefact_edit)
    assert '"domain" in form' in src, "de actie kijkt niet of het veld überhaupt is meegestuurd"
    assert "nieuw_domein = gekozen" in src, "een lege keuze wordt niet doorgeschreven"


# ── 3. Bewerken is de stand ──────────────────────────────────────────────────
def _wikiedit() -> str:
    kaal = js_zonder_uitleg(JS)
    return kaal.split("function wikiEdit(")[1].split("\n  function ")[0]


def test_de_pagina_gaat_bewerkbaar_open():
    haak = _wikiedit()
    assert "editeerbaar(true);" in haak, "er wordt niets aangezet bij het laden"
    assert "data-wiki-start" not in haak, "er hangt nog een startknop in de weg"


def test_de_knop_is_weg_van_de_pagina(tmp_path):
    html, _a = _html(tmp_path)
    assert "data-wiki-start" not in html


def test_de_poort_is_het_formulier_en_niets_anders():
    """GEEN `can_edit`-TAK IN DE BROWSER. `_wiki_editor` rendert zonder bewerkrecht geen
    `#wiki-form`; valt die koppeling weg, dan is de pagina voor iedereen bewerkbaar of voor
    niemand. De poort hoort op één plek te staan, en dat is de server."""
    haak = _wikiedit()
    assert 'querySelector("#wiki-form")' in haak
    assert "!form" in haak, "de functie valt niet terug zonder bewerkvlak"


def test_zonder_bewerkrecht_gebeurt_er_niets(tmp_path):
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="", username=None)
    assert "id='wiki-form'" not in html
    assert "contenteditable" not in html


def test_opslaan_blijft_een_eigen_handeling():
    """GEEN AUTOSAVE. De balk verschijnt bij een wijziging; wegschrijven doet pas de knop."""
    haak = _wikiedit()
    assert "form.hidden = true;" in haak, "de opslaan-balk staat meteen open"
    assert "function gewijzigd()" in haak
    for verboden in ("setTimeout(bewaar", "autosave", "form.submit()"):
        assert verboden not in haak, f"er wordt vanzelf opgeslagen ({verboden})"


def test_elke_wijziging_laat_de_balk_zien_en_niet_een_lijst_aanroepen():
    """EEN MutationObserver EN GEEN OPSOMMING AANROEPPUNTEN. Er zijn minstens acht plekken die het
    document veranderen (typen, plakken, de werkbalk, het blokmenu, een upload, slepen,
    omhoog/omlaag, verwijderen). Eén vergeten aanroep betekent: iemand bewerkt, ziet geen knop, en
    verliest zijn werk. De waarnemer hangt aan de boom zelf en kan er dus geen missen."""
    haak = _wikiedit()
    assert "new MutationObserver(gewijzigd)" in haak
    for eigenschap in ("childList", "subtree", "characterData"):
        assert eigenschap in haak, f"de waarnemer let niet op {eigenschap}"
    assert 'titel.addEventListener("input", gewijzigd)' in haak, "de titel telt niet mee"


def test_de_waarnemer_start_na_het_aanzetten():
    """Aanzetten hangt zelf de grepen en de plus in elk blok. Startte de waarnemer daarvóór, dan
    stond de opslaan-balk meteen open op elke pagina die je opent — zonder dat je iets deed."""
    haak = _wikiedit()
    assert haak.index("editeerbaar(true);") < haak.index("new MutationObserver")


def test_annuleren_telt_niet_als_wijziging():
    """GEMETEN IN FIREFOX, niet bedacht. De waarnemer draait ASYNCHROON: `form.hidden = true` liep
    eerst, daarna kwam de callback van het terugzetten langs en stond de balk weer open —
    annuleren leek dan niets te doen. `takeRecords()` leegt de wachtrij van wat het herstel zélf
    net veroorzaakte; alles wat erna gebeurt telt gewoon weer mee."""
    haak = _wikiedit()
    annuleer = haak.split("data-wiki-cancel")[1].split("});")[0]
    assert "waarnemer.takeRecords()" in annuleer, \
        "het herstel zet de opslaan-balk zelf weer open"
    assert annuleer.index("takeRecords") < annuleer.index("form.hidden = true"), \
        "de wachtrij wordt geleegd nadat de balk al verborgen is"


def test_annuleren_neemt_het_bewerkrecht_niet_af():
    """Annuleren gooit je wijzigingen weg; het maakt de pagina niet read-only, want bewerkbaar is
    sinds deze stap de stand en niet een modus."""
    haak = _wikiedit()
    annuleer = haak.split("data-wiki-cancel")[1].split("});")[0]
    assert "editeerbaar(false)" not in annuleer, "annuleren zet de pagina op slot"
    assert "form.hidden = true" in annuleer, "de opslaan-balk blijft open na annuleren"


# ── 4. Eén doorlopend document ───────────────────────────────────────────────
def test_de_tekst_zit_niet_meer_in_een_kaart(tmp_path):
    """De kaart tekende een rand met een eigen vlak om de BODY terwijl de titel erbuiten stond —
    een kop met een los kader eronder, in plaats van één document."""
    html, _a = _html(tmp_path)
    voor = html.split("id='wiki-body'")[0]
    assert not voor.rstrip().endswith("<div class='card'><div class='att-body wiki-body'"), \
        "de body zit nog in een kaart"
    assert "class='att-body wiki-body'" in html


def test_titel_en_tekst_delen_een_omhulsel(tmp_path):
    html, _a = _html(tmp_path)
    doc = html.split("class='wiki-doc'")[1]
    assert doc.index("wiki-titel") < doc.index("id='wiki-body'"), \
        "de titel staat buiten het omhulsel van de tekst"


def test_het_omhulsel_houdt_de_goot_voor_de_greep():
    """DE PADDING IS GEEN DECORATIE. De blok-greep hangt op `left:-1.5rem`, buiten de doos van
    `.wb`; zonder ruimte links valt hij van de pagina af. Dat is dezelfde ruimte die de kaart gaf,
    nu zonder de rand eromheen."""
    regel = re.search(r"(?:^|[};])\s*\.wiki-doc\{([^}]*)\}", CSS, re.M)
    assert regel, ".wiki-doc heeft geen vormgeving"
    body = regel.group(1)
    assert "padding" in body
    assert "border:" not in body and "background" not in body, \
        "het omhulsel tekent weer een vlak met een rand"
    # DE LINKERWAARDE VAN DE SHORTHAND, en die staat op plek 4 van `padding: boven rechts onder
    # links`. Mijn eerste versie greep met een regex de EERSTE waarde en mat dus de bovenmarge —
    # groen te krijgen met een goot van nul. Een toets die het verkeerde getal leest, is erger dan
    # geen toets.
    decl = next(d for d in body.split(";") if d.strip().startswith("padding:"))
    delen = decl.split(":", 1)[1].split()
    links = {1: 0, 2: 1, 3: 1, 4: 3}[len(delen)]
    assert delen[links].endswith("rem") and float(delen[links][:-3]) >= 1.5, \
        f"de goot is te smal voor de greep (left:-1.5rem): {decl}"


def test_er_zweeft_geen_knoppenblok_boven_de_tekst(tmp_path):
    """"zonder de knoppen een eigen zwevend blokje te laten worden" — de kopbalk droeg alleen nog
    de Edit page-knop, en die is weg."""
    html, _a = _html(tmp_path)
    kop = html.split("id='wiki-body'")[0]
    assert "wiki-kopbalk" not in kop and "wiki-kopacties" not in kop
