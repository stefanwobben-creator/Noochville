"""Inbox en werkoverleg delen één verwerk-mechaniek — en dus dezelfde uitkomsten.

DRIE, en niet meer: Actie · Project · Roloverleg.

WAAROM DIT EEN POORT IS. Beide schermen hadden een vierde bak voor 'informatie delen', en gemeten
over de hele historie op prod:

    werkoverleg : 9 uitkomsten — 8x actie, 1x project, **0x info**
    inbox       : 42 uitkomsten — 26x 'niks nodig', 6x ping (de info-intentie), 3x project, 0x action

Een bak die niemand vult is niet gratis: hij staat op elk scherm, hij kost een keuze, en hij laat
de twee schermen uit elkaar lopen zodra er één een vijfde krijgt. Dat is de drift die
docs/CONVENTIES.md verbiedt.

EN HIJ IS NIET VERLOREN. Een mededeling aan iemand is een ACTIE met `@`: dezelfde landing, maar als
werk dat terugkomt in plaats van als los bericht dat daarna nergens meer opduikt. Een ping is een
actie zonder stap voor de ander.

HEROPENEN MAG — maar dan als besluit, met een reden, niet als bijvangst van een refactor.
"""
from __future__ import annotations

import inspect

from nooch_village import cockpit2
from nooch_village.inbox_wizard import FLOWS, GOVERNANCE
from nooch_village.views.vangst import UITKOMST_LABEL, UITKOMST_SOORTEN

DRIE = {"actie", "project", "governance"}


def test_het_werkoverleg_biedt_er_drie():
    assert {k for k, _lbl, _veld in UITKOMST_SOORTEN} == DRIE


def test_de_inbox_biedt_dezelfde_drie():
    """Andere woorden (Engels, en 'roloverleg' heet er 'governance meeting'), zelfde set."""
    assert {f["otype"] for f in FLOWS} | {GOVERNANCE["otype"]} == {"action", "project",
                                                                   "roloverleg"}


def test_informatie_is_geen_keuze_meer_op_beide_schermen():
    assert "info" not in {k for k, _l, _v in UITKOMST_SOORTEN}
    assert "info" not in {f["otype"] for f in FLOWS}
    assert "ping" not in {f["otype"] for f in FLOWS}
    # en de handler kent hem niet meer: een post met otype=info valt fail-closed door
    bron = inspect.getsource(cockpit2.dispatch.__wrapped__ if hasattr(cockpit2.dispatch, "__wrapped__")
                             else cockpit2._act_vangst_uitkomst)
    assert 'elif otype == "info"' not in bron


def test_oude_uitkomsten_blijven_leesbaar():
    """LEES-ONLY, niet weg. Een stille drop zou betekenen dat een vastgelegde uitkomst uit een
    afgesloten overleg ineens niets meer zegt — de archieven dragen 'info' nog."""
    assert UITKOMST_LABEL.get("info") == "Informatie"


def test_de_telling_houdt_de_historie(tmp_path):
    """`_tel` telt 'info' nog steeds: het archief van een oud overleg mag zijn getal niet verliezen."""
    from nooch_village.werkoverleg import WerkoverlegStore
    st = {"agenda": [{"id": "a", "uitkomsten": [{"type": "info"}, {"type": "actie"}]}]}
    t = WerkoverlegStore._tel(st)
    assert t["info"] == 1 and t["acties"] == 1


def test_een_lege_info_regel_wordt_niet_getoond():
    """Een regel die eeuwig 0 toont is ruis; een oud overleg mét info houdt zijn regel."""
    import inspect as _i

    from nooch_village.views import werkoverleg as wv
    bron = _i.getsource(wv)
    assert 'if s.get("info") else ""' in bron
