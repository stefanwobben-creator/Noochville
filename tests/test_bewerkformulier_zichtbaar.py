"""Het bewerkformulier staat open op een permalink, en ingeklapt in een lijst (27 sep 2026).

DE MELDING: "wiki is niet bewerkbaar". Gemeten bleek het tegendeel — alle 18 artefacten op prod
renderen een formulier en de server staat het toe. Wat er misging was de PRESENTATIE.

ROOT CAUSE. `_artefact_edit_form` wikkelt zijn formulier in
`<details class='qadd' data-qadd-inline><summary class='muted'>edit</summary>`. Dat ontwerp is
voor de ROLPAGINA: daar staat een lijst artefacten, en twintig openstaande tekstvakken onder
elkaar is geen pagina meer. Op de PERMALINK van één artefact gaat die rechtvaardiging niet op —
daar staat niets anders op het scherm, en dan is de inklapping alleen nog een klein "edit"-linkje
dat je eerst moet vinden. De summaries op zo'n pagina waren letterlijk `['edit', '3 versions']`.

DE PARAMETER, geen tweede formulier: `ingeklapt=True` (default) houdt de `<details>`,
`ingeklapt=False` rendert hem open. Eén formulier, één actie, één versie-entry — alleen de
verpakking verschilt.

WAT HIER NIET MEER TE TOETSEN VIEL, en dat is een premisse-correctie: de rolpagina-lijst ROEPT
DIT FORMULIER NIET MEER AAN. #620 haalde het bewerken daar weg (de lijst toont "Edit on its
page"). De gevraagde regressietest op de rolpagina kan dus niet bestaan; wat er wél op ligt is de
DEFAULT van de functie zelf, zodat een toekomstig lijst-oppervlak de inklapping terugkrijgt zonder
dat iemand het opnieuw moet bedenken.
"""
from __future__ import annotations

import inspect

from nooch_village import cockpit2
from nooch_village.views.overview import _artefact_edit_form, render_node
from nooch_village.views.wiki import render_pagina

ROL = "mother_earth__nooch__compliance"
DETAILS = "<details class='qadd' data-qadd-inline>"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    buiten = st.people.add("Buitenstaander", "buiten@test.nl")
    st.assign.assign("mother_earth__circle_lead", "person", baas.id)
    return dd, st, baas, buiten


def _pagina(st, a):
    return render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")


# ══ 1. De permalink: direct zichtbaar ════════════════════════════════════════
def test_een_policy_toont_het_formulier_meteen(tmp_path):
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="Mits dit.")
    h = _pagina(st, a)
    assert DETAILS not in h, "het zit nog achter een inklapper"
    assert ">edit</summary>" not in h, "het kleine edit-linkje staat er nog"
    assert "value='artefact_edit'" in h and "name='title'" in h


def test_een_tool_ook(tmp_path):
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title="Serpstat", url="https://x", body="y")
    h = _pagina(st, a)
    assert DETAILS not in h
    assert "value='artefact_edit'" in h and "name='url'" in h


def test_er_is_geen_tweede_kopie_van_de_tekst_meer(tmp_path):
    """DE VOLGENDE STAP IN DEZELFDE OPRUIMING (28 september 2026).

    Hier stond dat het formulier een kopje "Edit" hoort te hebben, want zonder de `<summary>` zei
    niets meer wat dat blok was. Dat blok is er niet meer: een policy wordt nu in de tekst zelf
    bewerkt, zoals een note. Een kopje boven een tweede kopie van dezelfde tekst is precies wat
    er niet meer hoeft."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = _pagina(st, a)
    assert "<p class='att-lbl'>Edit</p>" not in h
    assert "id='wiki-body'" in h and "id='wiki-form'" in h


def test_de_versiehistorie_blijft_wel_ingeklapt(tmp_path):
    """Die IS een lijst, en hoort dus dicht te staan — dat is precies het onderscheid."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    st.att.update(a.id, body="y", actor_id=baas.id, actor_type="person")
    h = _pagina(cockpit2._Stores(dd), st.att.get(a.id))
    assert "versions</summary>" in h or "version</summary>" in h


def test_zonder_bewerkrecht_geen_formulier(tmp_path):
    """De po\xf3rt is niet geraakt — alleen de verpakking.

    MET EEN DOMEIN EROP, sinds 28 september. Een policy ZONDER domein mag ieder ingelogd mens
    bewerken — dat is geen verruiming van deze stap maar wat `_artefact_gate` altijd al deed
    (uitgevoerd: "policy updated" voor `buiten@test.nl`). Het scherm vroeg het alleen nog op de
    oude manier. Deze toets moet dus een pagina pakken waar de poort écht bijt."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x", domain="claim-verification")
    h = render_pagina(st, a.id, csrf_token="t", username="buiten@test.nl")
    assert "value='artefact_edit'" not in h and DETAILS not in h
    assert "id='wiki-form'" not in h, "de opslaan-balk hoort er ook niet te staan"


def test_een_note_is_niet_geraakt(tmp_path):
    """"notes hebben al hun eigen inline-editor zonder details-wrapper en blijven ongemoeid." En
    dat is de richting waarin dit is opgelost: niet de note kreeg het policy-kopje, de policy
    kreeg de editor van de note."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Een note", body="tekst")
    h = _pagina(st, a)
    assert "data-blok" in h, "de blok-editor van de note is weg"
    assert "<p class='att-lbl'>Edit</p>" not in h


# ══ 2. De inklapping blijft bestaan voor een lijst ═══════════════════════════
def test_de_default_is_nog_steeds_ingeklapt(tmp_path):
    """DE REGRESSIETEST VOOR "TWINTIG OPEN VAKKEN", op de enige plek waar hij nog kan liggen.

    De rolpagina-lijst roept dit formulier sinds #620 niet meer aan (zie de kop van dit bestand),
    dus de inklapping is niet meer op een SCHERM te toetsen. Wat blijft is de functie zelf: wie
    hem zonder `ingeklapt` aanroept — een toekomstig lijst-oppervlak — krijgt de `<details>`."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    dicht = _artefact_edit_form(a, "TOK")
    assert dicht.startswith(DETAILS)
    assert ">edit</summary>" in dicht
    assert dicht.rstrip().endswith("</details>")


def test_open_en_dicht_dragen_hetzelfde_formulier(tmp_path):
    """\xc9\xc9N FORMULIER, \xe9\xe9n actie, \xe9\xe9n versie-entry — alleen de verpakking verschilt. Zou het
    formulier zelf meeveranderen, dan zijn het twee bewerkpaden met \xe9\xe9n naam."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title="Serpstat", url="https://x", body="y")
    dicht = _artefact_edit_form(a, "TOK", domains=["Materials"])
    open_ = _artefact_edit_form(a, "TOK", domains=["Materials"], ingeklapt=False)
    kern = lambda h: h[h.index("<form"):h.index("</form>")]
    assert kern(dicht) == kern(open_)
    assert open_.startswith("<div class='qadd'>") and open_.rstrip().endswith("</div>")


def test_de_annuleerknop_overleeft_het_ontbreken_van_de_details():
    """`data-qadd-cancel` doet `f.closest("details")` — met een `if (det)` eromheen, dus zonder
    wikkel reset hij alleen het formulier. Zou die guard verdwijnen, dan knalt de knop hier."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    stuk = js.split("data-qadd-cancel")[1][:400]
    assert 'closest("details")' in stuk and "if (det)" in stuk


def test_er_is_geen_aanroeper_meer_in_productie():
    """DE PREMISSE-CORRECTIE, bijgewerkt — en dit is een STAND, geen wens.

    Na #620 riep alleen de permalink dit formulier nog aan. Sinds 28 september bewerkt die pagina
    inline, dus er is er nu GEEN. De functie staat er nog, met zijn `ingeklapt`-parameter en zijn
    domein-veld; hem weghalen is een eigen besluit (en zou de laatste bewerkweg zonder JavaScript
    weghalen). Wat deze toets doet is dat zichtbaar houden: zolang hij nul aanroepers heeft, meet
    elke toets eronder iets wat geen scherm meer bereikt."""
    from nooch_village.views import overview, wiki
    bron = inspect.getsource(overview) + inspect.getsource(wiki)
    aanroepen = [r for r in bron.splitlines()
                 if "_artefact_edit_form(" in r and not r.lstrip().startswith(("def ", "#"))
                 and "`" not in r]
    assert not aanroepen, f"er is weer een aanroeper: {aanroepen}"


def test_de_rolpagina_wijst_nog_steeds_door(tmp_path):
    """Wat #620 daar neerzette is niet omgegooid."""
    dd, st, baas, buiten = _dorp(tmp_path)
    st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = render_node(st, ROL, "wiki", csrf_token="t", username="anchor@test.nl")
    assert "value='artefact_edit'" not in h
    assert "Edit on its page" in h
