"""Tak 2 heeft nu een zichtbaar oppervlak: bij meerdere vervullers kun je de owner kiezen.

CONTEXT. #431 gaf het projectformulier een owner-default: één vervuller → voorgekozen, geen
vervuller → "no owner". Tak 2 — meerdere vervullers — kreeg bewust géén stille gok, maar had ook
geen oppervlak: de wizard heeft sinds #371 geen trekker-kiezer meer. Die viel daar niet af omdat hij
fout was, maar omdat hij niet op het twee-tik-pad hoorde ("idee, uitkomst, rol, opslaan").

Vandaar de plaats: in de OPGEVOUWEN laag (`Who could pick this up`), niet op de snelle route.
"""
from __future__ import annotations

import re

from nooch_village.views.wizard import render_wizard


class _St:
    class records:
        @staticmethod
        def all():
            return []

        @staticmethod
        def get(_r):
            return None
    people = personas = None


def _js(**kw) -> str:
    """De wizard-pagina als tekst, met een meegegeven vervullers-map."""
    class _S:
        class records:
            @staticmethod
            def all():
                return []

            @staticmethod
            def get(_r):
                return None

        class people:
            @staticmethod
            def all():
                return []

        class personas:
            @staticmethod
            def all():
                return {}
    return render_wizard(_S(), "tok", **kw)


def test_bij_twee_vervullers_rendert_de_kiezer():
    html = _js(role="rol_a", vervullers={"rol_a": [{"v": "person:p1", "n": "Nina"},
                                                   {"v": "person:p2", "n": "Lotte"}]})
    assert '"rol_a"' in html                              # de map zit in de pagina
    assert "Nina" in html and "Lotte" in html
    assert "wz-owner" in html                             # het veld bestaat


def test_bij_een_of_geen_vervuller_rendert_hij_niet():
    """De map draagt alleen rollen met ≥2 (cockpit2.vervullers_map); de JS controleert het nog eens,
    zodat een rolwissel in het scherm niet alsnog een kiezer met één naam toont."""
    html = _js(role="rol_a", vervullers={})
    assert "VERVULLERS={}" in html.replace(" ", "")
    # de guard staat in de code, niet alleen in de data
    assert "opties.length<2" in html


def test_de_kiezer_is_ondubbelzinnig_de_EIGENAAR():
    """GUARD. Eronder staat 'Or assign a step yourself', en dat wijst een STAP toe aan een rol.
    Zonder eigen kop kiest iemand daar een stap-uitvoerder in de veronderstelling dat hij de
    eigenaar zet."""
    html = _js(role="rol_a", vervullers={"rol_a": [{"v": "person:p1", "n": "Nina"},
                                                   {"v": "person:p2", "n": "Lotte"}]})
    blok = html[html.index("function eigenaarBlok"):]
    blok = blok[:blok.index("function taak(")]
    assert '<div class="wz-clab">Owner</div>' in blok     # zelfde term als de projectkaart
    assert "Pick who owns the project" in blok
    # en hij eindigt met een eigen kop voor het stap-blok, zodat de twee niet in elkaar overlopen
    assert '<div class="wz-clab">Hand out steps</div>' in blok


def test_de_owner_kiezer_staat_boven_het_stap_blok():
    html = _js(role="rol_a", vervullers={"rol_a": [{"v": "person:p1", "n": "Nina"},
                                                   {"v": "person:p2", "n": "Lotte"}]})
    assert html.index("eigenaarBlok()") < html.index("Or assign a step yourself")


def test_niets_kiezen_blijft_geldig():
    """Nooit blokkeren: 'no owner' is een geldige uitkomst, ook als er te kiezen valt."""
    html = _js(role="rol_a", vervullers={"rol_a": [{"v": "person:p1", "n": "Nina"},
                                                   {"v": "person:p2", "n": "Lotte"}]})
    assert "— no owner —" in html


def test_hij_zit_in_de_opgevouwen_laag_en_niet_op_de_snelle_route():
    """#371 klapte de wizard in tot idee → uitkomst → rol → opslaan. De kiezer terugzetten op die
    route zou dat terugdraaien; in de details-laag respecteert hij hem."""
    html = _js(role="rol_a", vervullers={"rol_a": [{"v": "person:p1", "n": "Nina"},
                                                   {"v": "person:p2", "n": "Lotte"}]})
    # het blok wordt gerenderd door drawRollen(), en dat draait pas als de details opengaat
    assert 'ontoggle="if(this.open)rollen()"' in html
    snelle_route = html[html.index('class="wz-clab">Your idea'):html.index("box-details")]
    assert "wz-owner" not in snelle_route


# ── een cirkel hoort niet in de kiezer ─────────────────────────────────────────────────────────

def test_een_cirkel_komt_nooit_in_de_map(monkeypatch):
    """GEVONDEN OP DE LIVE-VERIFICATIE van #432: de map droeg `mother_earth__nooch` — een CIRKEL —
    als owner-kiezer-ingang. Praktisch onschadelijk (de rolkiezer biedt nooit een cirkel-id, dus de
    kiezer rendert er nooit voor), maar `_act_proj_add` weigert een project op een cirkel expliciet:
    "a circle cannot contain a project". Een ingang die per definitie nooit bruikbaar is, is de
    dood-maar-intact-vorm die iemand later doet denken dat het wél kan.

    Ook mét twee vervullers blijft hij eruit — juist dan, want dat is het enige geval waarin hij
    anders zou renderen."""
    import types
    from nooch_village import cockpit2

    cirkel = types.SimpleNamespace(id="een_cirkel", archived=False)
    rol = types.SimpleNamespace(id="een_rol", archived=False)

    class _St:
        class records:
            @staticmethod
            def all():
                return [cirkel, rol]

            @staticmethod
            def get(r):
                return cirkel if r == "een_cirkel" else rol

        class assign:
            @staticmethod
            def fillers_of(rol_id, record=None):
                return [types.SimpleNamespace(id="p1", type="person"),
                        types.SimpleNamespace(id="p2", type="person")]

    monkeypatch.setattr(cockpit2.org, "is_circle", lambda rec: getattr(rec, "id", "") == "een_cirkel")
    monkeypatch.setattr(cockpit2, "_person_name", lambda st, p: p.upper())
    mp = cockpit2.vervullers_map(_St())

    assert "een_cirkel" not in mp                     # ook al heeft hij er twee
    assert "een_rol" in mp and len(mp["een_rol"]) == 2


def test_de_map_gebruikt_het_bestaande_cirkel_predikaat():
    """Geen eigen string-check ('__circle_lead' in id, of id.count('__')<2): een derde definitie van
    'dit is een cirkel' is precies hoe twee vormen van dezelfde vraag uit elkaar gaan lopen."""
    import inspect
    from nooch_village import cockpit2
    src = inspect.getsource(cockpit2.vervullers_map)
    assert "org.is_circle(rec)" in src
