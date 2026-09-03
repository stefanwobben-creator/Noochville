"""Een rol met één vervuller kiest die vervuller voor als owner.

WAAROM (4 sep 2026): het projectformulier koos niemand voor, ook niet als de rol precies één
vervuller had. Wie dat veld liet staan maakte een project zonder eigenaar — de wees-projecten die
`afslank_wezen` achteraf opruimde. Dit voorkomt ze aan de voorkant.

EN WAAROM NIET OP `bestemming()`: die beantwoordt dezelfde vraag voor het ROUTEREN van werk en heeft
daar een derde stap — bij een onbemande rol hopt hij naar de Circle Lead. Voor werk is dat juist; als
formulier-default zou het "no owner" stilletjes ombouwen tot "de Circle Lead is eigenaar", en dan
maak je dezelfde wezen opnieuw, alleen met een naam erop.
"""
from __future__ import annotations

import types

from nooch_village import cockpit2


class _St:
    """Alleen wat `mens_vervullers` aanraakt."""

    def __init__(self, per_rol):
        self._per = per_rol
        self.records = types.SimpleNamespace(get=lambda r: object())
        outer = self

        class _Assign:
            def fillers_of(self, rol, record=None):
                return [types.SimpleNamespace(id=p, type="person")
                        for p in outer._per.get(rol, [])]
        self.assign = _Assign()


def test_een_vervuller_wordt_de_default():
    st = _St({"rol_a": ["p1"]})
    assert cockpit2.standaard_trekker(st, "rol_a") == "person:p1"


def test_meerdere_vervullers_laten_kiezen():
    """Een stille gok tussen twee mensen is erger dan geen keuze: niemand ziet dat er gegokt is."""
    st = _St({"rol_a": ["p1", "p2"]})
    assert cockpit2.standaard_trekker(st, "rol_a") == ""


def test_geen_vervuller_houdt_no_owner():
    """Nooit blokkeren, nooit iemand verzinnen — 'no owner' is een geldige uitkomst."""
    st = _St({"rol_a": []})
    assert cockpit2.standaard_trekker(st, "rol_a") == ""
    assert cockpit2.standaard_trekker(st, "") == ""


def test_hij_hopt_NIET_naar_de_circle_lead():
    """De vondst die de bouwvorm bepaalde. `bestemming()` doet dat wel — terecht, voor werk — en
    hergebruik daarvan zou een onbemande rol stilletjes een eigenaar geven."""
    st = _St({"onbemand": []})
    assert cockpit2.standaard_trekker(st, "onbemand") == ""


def test_een_persona_telt_niet_als_owner():
    """`mens_vervullers` filtert op type == 'person'. Een AI-vervulde rol krijgt geen mens als
    default-eigenaar toegewezen."""
    st = _St({})

    class _Assign:
        def fillers_of(self, rol, record=None):
            return [types.SimpleNamespace(id="persona1", type="persona")]
    st.assign = _Assign()
    assert cockpit2.standaard_trekker(st, "rol_a") == ""


def test_de_expliciete_keuze_wint_van_de_default():
    """In de route: `trekker` uit de querystring gaat vóór. Zonder die volgorde overschrijft de
    default wat de vorige stap al wist (bijvoorbeeld het groeperen per persoon op het bord)."""
    import pathlib
    src = pathlib.Path("nooch_village/cockpit2.py").read_text(encoding="utf-8")
    blok = src[src.index("render_wizard(st, effective_csrf"):]
    blok = blok[:blok.index("chrome=False")]
    assert 'trekker=((qs.get("trekker") or [""])[0]' in blok
    assert "or standaard_trekker(st," in blok
