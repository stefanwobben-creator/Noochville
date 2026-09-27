"""Accountabilities worden in de Engelse gerund geschreven, en één functie weet dat.

DE REGEL WAS NEDERLANDS. `secretary_check` toetste de -en-werkwoordsvorm ("Bewaken van …") in een
verder Engelse interface. Eerst is alleen de MELDING vertaald — maar dan beschrijft een Engelse
zin een Nederlandse vormeis, en dat is half werk. Nu is de REGEL Engels: "Guarding …",
"Monitoring …".

ÉÉN IMPLEMENTATIE, GEDEELD. `governance_review` had al `_ing_start`, die precies dit doet (en ook
een leidend "- " of "* " verdraagt). `secretary_check` gebruikt hem nu ook, in plaats van een
eigen variant. Twee modules met dezelfde vormeis oordelen na één wijziging verschillend — dat is
dezelfde fout als twee kopieën van één regel elders in dit dorp, en deze toets legt vast dat er
maar één is.

GEEN CIRKEL-IMPORT: `governance_review` importeert alleen `re` en noemt `roloverleg` uitsluitend
in een comment over verwijderde code. Ook dát staat hier vast, want zo'n cyclus is precies het
soort ding dat pas bij het importeren van een dérde module opvalt.
"""
from __future__ import annotations

import inspect
import tempfile

import pytest

from nooch_village.governance_review import _ing_start
from nooch_village.roloverleg import secretary_check


@pytest.fixture(scope="module")
def records():
    """Een echt register: de G-poort in `secretary_check` leest het, dus `None` knalt daar al
    voordat de vormcheck aan de beurt is."""
    from nooch_village import cockpit2
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd).records


def _issues(records, *accs) -> list[str]:
    """De meldingen van de secretaris-check voor deze accountabilities."""
    item = {"kind": "amend_role", "role_id": "mother_earth__nooch__compliance",
            "change": {"add_accountabilities": list(accs)}}
    return [i["msg"] for i in secretary_check(item, records)]


def _vorm_issues(records, *accs) -> list[str]:
    return [m for m in _issues(records, *accs) if "verb form" in m]


# ══ De regel ═════════════════════════════════════════════════════════════════
def test_een_engelse_gerund_levert_geen_melding_op(records):
    assert _vorm_issues(records, "Monitoring social channels") == []
    assert _vorm_issues(records, "Guarding the brand voice") == []


def test_een_nederlandse_en_vorm_levert_nu_wel_een_melding_op(records):
    """DE OMKERING, en dit is de kern van deze wijziging: precies de vorm die hiervóór de ENIGE
    goede was, is nu de vorm die piept."""
    m = _vorm_issues(records, "Bewaken van sociale kanalen")
    assert len(m) == 1, m
    assert "-ing verb form" in m[0]
    assert "Bewaken van sociale kanalen" in m[0], "de melding noemt niet wélke regel het betreft"


def test_een_gebiedende_wijs_ook(records):
    """"Respond to tickets" is Engels maar geen gerund — de vorm is de eis, niet de taal."""
    assert len(_vorm_issues(records, "Respond to tickets quickly")) == 1


def test_de_melding_geeft_een_voorbeeld(records):
    """Zonder voorbeeld moet de lezer raden wat "an -ing verb form" betekent."""
    m = _vorm_issues(records, "Bewaken van iets")[0]
    assert "e.g." in m and "Guarding" in m


def test_een_leidend_streepje_hoort_erbij(records):
    """`_ing_start` stript "- " en "* ". Zou `secretary_check` zijn eigen check houden, dan zou
    een geplakte lijstregel hier wél piepen en in `governance_review` niet."""
    assert _vorm_issues(records, "- Guarding the brand voice") == []


def test_meerdere_accountabilities_geven_meerdere_meldingen(records):
    m = _vorm_issues(records, "Bewaken van A", "Monitoring B", "Opstellen van C")
    assert len(m) == 2, m


# ══ Eén implementatie ════════════════════════════════════════════════════════
def test_secretary_check_gebruikt_de_gedeelde_functie():
    bron = inspect.getsource(secretary_check)
    assert "_ing_start(a)" in bron
    assert 'endswith("en")' not in bron, "er staat nog een eigen -en-check"
    assert 'endswith("ing")' not in bron, "de vormeis is hier opnieuw uitgeschreven"


def test_de_vormeis_staat_op_een_plek():
    """Wie 'ing' een tweede keer uitschrijft, maakt een tweede waarheid."""
    from nooch_village import governance_review, roloverleg
    assert inspect.getsource(governance_review).count('endswith("ing")') == 1
    assert 'endswith("ing")' not in inspect.getsource(roloverleg)


def test_er_is_geen_cirkel_import():
    """`governance_review` mag niets uit `roloverleg` nodig hebben — anders is de import die
    `secretary_check` nu doet een cyclus die pas elders opvalt."""
    import re
    bron = inspect.getsource(__import__("nooch_village.governance_review", fromlist=["x"]))
    code = "\n".join(re.sub(r"#.*$", "", r) for r in bron.splitlines())
    assert "roloverleg" not in code, "governance_review verwijst terug naar roloverleg"


def test_beide_modules_laden_samen():
    """De toets die de cyclus écht zou vangen: importeer ze allebei, in beide volgordes."""
    import importlib
    for eerste, tweede in (("nooch_village.governance_review", "nooch_village.roloverleg"),
                           ("nooch_village.roloverleg", "nooch_village.governance_review")):
        importlib.import_module(eerste)
        importlib.import_module(tweede)
    assert _ing_start("Monitoring X") is True
