"""Eén lookup bepaalt de memo-ontvanger én de landing van het project dat eruit volgt.

WAAROM ÉÉN: zou de memo naar de ene rol gaan en het project naar de andere, dan kan "één persoon
oordeelt én bezit" alleen per toeval kloppen, en breekt het stil zodra de org verschuift.

WAAROM GEEN VASTE ID: `creator_of_shoes` is vandaag het antwoord, niet de regel. Rolvervulling en
rol-eigenaarschap veranderen; een bevroren id wijst dan stil naar de verkeerde plek.
"""
from __future__ import annotations

import types

import pytest

from nooch_village import triage_rol


@pytest.fixture
def dorp(monkeypatch):
    """Een dorp waarin ik per test bepaal wie welke rol vervult."""
    staat = {"match": "", "mensen": {}, "lead": {}}

    monkeypatch.setattr(triage_rol, "classificeer",
                        lambda tekst, records, **kw: {"rol": staat["match"],
                                                      "grond": "gematcht door de secretary"})
    import nooch_village.cockpit2 as c
    monkeypatch.setattr(c, "mens_vervullers", lambda st, rol: staat["mensen"].get(rol, []))
    monkeypatch.setattr(c, "_circle_lead_van", lambda st, rol: staat["lead"].get(rol, ""))
    return staat


def _st():
    return types.SimpleNamespace(records=object())


def test_een_bemande_rol_krijgt_het_werk(dorp):
    dorp["match"] = "creator_of_shoes"
    dorp["mensen"] = {"creator_of_shoes": ["lotte"]}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X")
    assert uit["rol"] == "creator_of_shoes" and uit["mens"] == "lotte"
    assert uit["via"] == ""                               # geen omleiding nodig


def test_een_AI_VERVULDE_rol_is_een_dead_letter(dorp):
    """DE GUARD. Een persona leest de NotifStore nooit, dus een bericht daarheen valt stil.
    `bestemming()` hopt hier NIET — die vraagt of de rol kan UITVOEREN, en dat kan een persona.
    Wij vragen of er iemand LEEST, en dat is een andere vraag."""
    dorp["match"] = "harry_hemp"
    dorp["mensen"] = {"harry_hemp": [], "nooch_lead": ["stefan"]}   # AI-vervuld → geen mens
    dorp["lead"] = {"harry_hemp": "nooch_lead"}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X")
    assert uit["rol"] == "nooch_lead" and uit["mens"] == "stefan"
    assert "geen menselijke vervuller" in uit["via"]


def test_geen_gegronde_match_valt_open_naar_de_lead(dorp):
    dorp["match"] = ""
    uit = triage_rol.menselijke_eigenaar(_st(), "iets onherkenbaars")
    assert uit["via"].startswith("geen gegronde match")


def test_ook_de_lead_onbemand_valt_open_naar_de_founder(dorp):
    """Nooit stil laten vallen: er is altijd een laatste adres."""
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    dorp["match"] = "harry_hemp"
    dorp["mensen"] = {}
    dorp["lead"] = {"harry_hemp": "lege_lead"}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X")
    assert uit["rol"] == FOUNDER_ROLE_ID
    assert "ook de Circle Lead is onbemand" in uit["via"]


def test_de_uitkomst_is_leesbaar_zonder_de_code_ernaast(dorp):
    """`via` en `waarom` zijn er voor de droge run: een bestemming zonder uitleg dwingt de lezer
    de code te openen om te zien of hij klopt."""
    dorp["match"] = "harry_hemp"
    dorp["mensen"] = {"nooch_lead": ["stefan"]}
    dorp["lead"] = {"harry_hemp": "nooch_lead"}
    uit = triage_rol.menselijke_eigenaar(_st(), "x")
    assert uit["waarom"] == "gematcht door de secretary"
    assert "harry_hemp" in uit["via"]


def test_notify_rol_is_niet_meer_hardwired_op_de_founder():
    """De enige meldweg van de pulslus stuurde élke headsup naar FOUNDER_ROLE_ID, ook als het werk
    aantoonbaar bij iemand anders hoorde."""
    import inspect
    from nooch_village.inhabitant import Inhabitant
    assert hasattr(Inhabitant, "_notify_rol")
    src = inspect.getsource(Inhabitant._notify_rol)
    # De CODE, niet de docstring: die noemt FOUNDER_ROLE_ID juist wel, als uitleg van wat er
    # veranderde. Een assertie over de hele bron zou de uitleg verbieden in plaats van de hardwire.
    code = src[src.index('"""', src.index('"""') + 3) + 3:]
    assert "FOUNDER_ROLE_ID" not in code              # de rol komt van de aanroeper
    assert 'NotifStore(pad).add("role", rol_id' in src
