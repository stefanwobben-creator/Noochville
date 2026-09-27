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


def test_er_staat_een_kopje_boven(tmp_path):
    """Zonder de summary is er niets dat zegt wat dit blok is. Bestaande klasse (`att-lbl`), geen
    nieuwe."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    assert "<p class='att-lbl'>Edit</p>" in _pagina(st, a)


def test_de_versiehistorie_blijft_wel_ingeklapt(tmp_path):
    """Die IS een lijst, en hoort dus dicht te staan — dat is precies het onderscheid."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    st.att.update(a.id, body="y", actor_id=baas.id, actor_type="person")
    h = _pagina(cockpit2._Stores(dd), st.att.get(a.id))
    assert "versions</summary>" in h or "version</summary>" in h


def test_zonder_bewerkrecht_geen_formulier(tmp_path):
    """De po\xf3rt is niet geraakt — alleen de verpakking."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = render_pagina(st, a.id, csrf_token="t", username="buiten@test.nl")
    assert "value='artefact_edit'" not in h and DETAILS not in h


def test_een_note_is_niet_geraakt(tmp_path):
    """"notes hebben al hun eigen inline-editor zonder details-wrapper en blijven ongemoeid.\""""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Een note", body="tekst")
    h = _pagina(st, a)
    assert "data-blok" in h, "de blok-editor van de note is weg"
    assert "<p class='att-lbl'>Edit</p>" not in h, "de note kreeg het policy-kopje"


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


def test_er_is_maar_een_aanroeper_in_productie():
    """PREMISSE-CORRECTIE, vastgelegd zodat hij niet opnieuw verrast: na #620 roept alleen de
    permalink dit formulier nog aan. De default bestaat voor wat er nog kan komen, niet voor iets
    wat er nu staat."""
    from nooch_village.views import overview, wiki
    aanroepen = [m for m in (inspect.getsource(overview), inspect.getsource(wiki))
                 if "_artefact_edit_form(" in m]
    assert "_artefact_edit_form(" not in inspect.getsource(overview._artefact_own_card)
    assert "ingeklapt=False" in inspect.getsource(wiki._artefact_pagina)
    assert aanroepen


def test_de_rolpagina_wijst_nog_steeds_door(tmp_path):
    """Wat #620 daar neerzette is niet omgegooid."""
    dd, st, baas, buiten = _dorp(tmp_path)
    st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = render_node(st, ROL, "wiki", csrf_token="t", username="anchor@test.nl")
    assert "value='artefact_edit'" not in h
    assert "Edit on its page" in h
