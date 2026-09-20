"""Punt 4 — inline bewerken, met dezelfde ENE save-actie.

Het besluit (Stefan, 20 september 2026): geen drie versie-entries voor één bewerking. Dus niet per
veld opslaan, geen debounce-timer en geen sessie-concept — gewoon het formulier dat er al is, met
de knop anders gepositioneerd: een balk die verschijnt zodra een veld dirty is, in plaats van
achter een aparte edit-`<details>`.

Deze tests bewaken vooral wat er NIET mag veranderen. De rechtencheck en de versie-opslag zijn het
punt van het hele artefact-model; een UI-wijziging mag daar niet langs.
"""
from __future__ import annotations

import re
import pathlib
import tempfile

import pytest

from nooch_village import cockpit2

REPO = pathlib.Path(__file__).resolve().parents[1]
OWNER = "mother_earth__nooch__creator_of_shoes"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Schrijver", "schrijf@test.nl")
    st.assign.assign(OWNER, "person", mens.id)
    a = st.att.add(OWNER, "note", title="Selco", body="Eerste tekst.",
                   actor_id=mens.id, actor_type="person")
    return st, mens, a, dd


def _ctx(st, dd, velden, username):
    return cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/pagina",
                         form=velden, username=username, action="artefact_edit", data_dir=dd)


def test_een_bewerking_is_een_versie_entry(dorp):
    """De kern van besluit 6. Drie velden tegelijk wijzigen blijft ÉÉN entry."""
    st, mens, a, dd = dorp
    voor = len(st.att.get(a.id).versions or [])
    cockpit2.ACTIONS["artefact_edit"](_ctx(st, dd, {
        "aid": a.id, "title": "Selco (supplier)", "body": "Tweede tekst."}, mens.email))
    na = st.att.get(a.id)
    assert len(na.versions) == voor + 1
    assert na.title == "Selco (supplier)" and na.body == "Tweede tekst."


def test_de_change_note_blijft_dezelfde(dorp):
    """"dezelfde version/change_note-opslag als nu" — dus niet stilletjes een andere tekst."""
    st, mens, a, dd = dorp
    cockpit2.ACTIONS["artefact_edit"](_ctx(st, dd, {"aid": a.id, "body": "Nieuw."}, mens.email))
    assert (st.att.get(a.id).versions or [])[-1].get("change_note") == "bewerkt"


def test_de_rechtencheck_staat_nog_voor_de_mutatie(dorp):
    """Structureel, op volgorde in de bron: `_artefact_gate` moet vóór `st.att.update` staan.
    Een poort ná de schrijfactie is geen poort."""
    src = pathlib.Path(cockpit2.__file__).read_text()
    blok = re.search(r"def _act_artefact_edit\(c\):(.*?)\ndef ", src, re.S).group(1)
    assert blok.index("_artefact_gate(") < blok.index("st.att.update(")


def test_wie_de_rol_niet_vervult_mag_niet_bewerken(dorp):
    st, _mens, a, dd = dorp
    buiten = st.people.add("Buitenstaander", "buiten@test.nl")
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.ACTIONS["artefact_edit"](_ctx(st, dd, {"aid": a.id, "body": "x"}, buiten.email))
    assert st.att.get(a.id).body == "Eerste tekst."


def test_het_formulier_heeft_nog_precies_een_submit(dorp):
    """Zou er per veld een knop komen, dan zijn er meerdere save-acties en dus meerdere entries."""
    from nooch_village.views.overview import _artefact_edit_form
    html = _artefact_edit_form(st_a(dorp), "csrf")
    assert html.count("type='submit'") == 1
    assert html.count("value='artefact_edit'") == 1


def st_a(dorp):
    _st, _m, a, _dd = dorp
    return a


def test_de_opslaan_balk_hangt_aan_dirty_en_de_tekst_opent_het_formulier(dorp):
    """De UI-helft van besluit 6, op de haken getoetst en niet op de opmaak."""
    from nooch_village.views.overview import _artefact_edit_form
    html = _artefact_edit_form(st_a(dorp), "csrf")
    assert "data-qadd-dirty" in html and "qadd-bar" in html and "data-qadd-cancel" in html
    js = (REPO / "nooch_village" / "static" / "nooch.js").read_text()
    for haak in ("data-qadd-open", "data-qadd-dirty", "data-qadd-cancel", "qadd-bar"):
        assert haak in js, haak


def test_zonder_js_blijft_bewerken_mogelijk(dorp):
    """De balk is in de HTML zichtbaar en wordt pas door JS verborgen. Andersom zou de knop
    onbereikbaar zijn zodra scripts uitstaan — dan is 'inline' een regressie, geen verbetering."""
    from nooch_village.views.overview import _artefact_edit_form
    html = _artefact_edit_form(st_a(dorp), "csrf")
    assert "qadd-bar' hidden" not in html and 'qadd-bar" hidden' not in html
    assert "<summary class='muted'>edit</summary>" in html      # de no-JS-ingang blijft
    js = (REPO / "nooch_village" / "static" / "nooch.js").read_text()
    assert "b.hidden = true" in js
