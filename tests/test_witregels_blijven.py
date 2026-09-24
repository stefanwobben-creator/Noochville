"""Twee witregels blijven twee witregels (24 september 2026).

WAT ER MIS WAS. `_md_naar_bron` eindigde met een lus die drie of meer regeleindes terugbracht tot
twee, met in het commentaar de aanname: "drie of meer is nooit iets anders dan twee". Die aanname
klopt niet zodra iemand ÉCHT twee lege regels typt — dan is drie regeleindes precies wat hij
bedoelde, en at elke bewerkronde er één op.

WAAROM DIE LUS ER OOIT STOND. Een browser sluit een alinea met `</p>` én opent de volgende met
`<p>`: twee signalen voor één overgang. Wie ze allebei telt, laat de tekst bij elke bewerking
verder uit elkaar staan. Dat probleem is echt — maar het wordt al opgelost door `_nieuwe_regel`,
die weigert een regeleinde toe te voegen als er al één staat. De lus erachteraan was dus een
tweede verdediging tegen iets dat de eerste al tegenhield, en zij was degene die inhoud koste.

GEMETEN VOORDAT HIJ WEGGING: zonder die lus blijft de rondgang heel op alle 122 artefacten van
prod, en de volle suite blijft groen. De schade die hij aanrichtte was één witregel op één pagina
(DESIGNSYSTEM-001) — klein, maar het is stil verlies van wat de schrijver typte, en dat wordt
groter zodra er codeblokken in de wiki komen waar lege regels betekenis hebben.
"""
from __future__ import annotations

import pytest

from nooch_village.cockpit2_util import _md, _md_naar_bron


def _rondgang(bron: str) -> bool:
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


# ── 1. Witregels overleven ───────────────────────────────────────────────────
@pytest.mark.parametrize("bron", [
    "een\n\ntwee",
    "een\n\n\ntwee",
    "een\n\n\n\ntwee",
    "# Kop\n\n\ntekst",
    "- a\n\n\ntekst",
])
def test_de_rondgang_blijft_gelijk(bron):
    assert _rondgang(bron), f"de rondgang breekt op {bron!r}"


@pytest.mark.parametrize("aantal", [1, 2, 3])
def test_het_aantal_witregels_blijft_gelijk(aantal):
    """DE KERN. Twee lege regels zijn iets anders dan één, en de schrijver bepaalt dat."""
    bron = "een" + "\n" * (aantal + 1) + "twee"
    assert _md_naar_bron(_md(bron)) == bron


def test_de_echte_pagina_die_hierop_stukging():
    """DESIGNSYSTEM-001 had precies deze vorm: een kop, twee lege regels, dan de tekst. Dat was
    de enige pagina op prod waar de rondgang brak."""
    bron = "# NOOCH DESIGN SYSTEM\n\n\n## Color System"
    assert _rondgang(bron)
    assert _md_naar_bron(_md(bron)) == bron


# ── 2. Waar de oude lus tegen beschermde, blijft beschermd ───────────────────
@pytest.mark.parametrize("bron", [
    "# Kop\ntekst",
    "- a\n- b",
    "1. a\n2. b",
    "> citaat\ntekst",
    "---\ntekst",
    "# Kop\n- a\n- b\n## Kop twee",
])
def test_blok_grenzen_stapelen_zich_niet_op(bron):
    """Een blok-tag opent én sluit; wie beide regeleindes telt, laat de tekst bij elke bewerking
    verder uit elkaar staan. `_nieuwe_regel` houdt dat tegen — deze toetsen bewaken dat het
    weghalen van de lus die bescherming niet meenam."""
    assert _md_naar_bron(_md(bron)) == bron


def test_er_wordt_niet_meer_globaal_platgeslagen():
    """Op de BRON, zonder commentaar: een nieuwe lus die regeleindes samenvouwt zou dezelfde
    inhoud weer opeten, en dan valt alleen de toets hierboven nog op — als iemand hem draait."""
    import inspect
    import re
    from nooch_village import cockpit2_util
    bron = inspect.getsource(cockpit2_util._md_naar_bron)
    bron = re.sub(r"^\s*#[^\n]*", "", bron, flags=re.M)
    assert '"\\n\\n\\n"' not in bron, "er slaat weer iets regeleindes plat"
