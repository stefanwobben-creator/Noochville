"""Inbox, werkoverleg en wall delen één verwerk-mechaniek — en dus dezelfde uitkomsten.

DRIE werk-uitkomsten, en niet meer: Actie · Project · Roloverleg.

WAAROM DIT EEN POORT IS. Alle drie de schermen hadden een vierde bak voor 'informatie delen', en
gemeten over de hele historie op prod:

    werkoverleg : 9 uitkomsten — 8x actie, 1x project, **0x info**
    inbox       : 42 uitkomsten — 26x 'niks nodig', 6x ping (de info-intentie), 3x project, 0x action
    wall        : **1** notificatie ooit uit een info-uitkomst; 5 herkomst-regels van alle vijf de
                  types samen

Een bak die niemand vult is niet gratis: hij staat op elk scherm, hij kost een keuze, en hij laat de
schermen uit elkaar lopen zodra er één een vijfde krijgt. Dat is de drift die docs/CONVENTIES.md
verbiedt.

DAT DE WALL DRIFT WAS EN GEEN BROADCAST is nagegaan voor hij meeging, want die twee vragen om het
tegenovergestelde: drift veeg je mee, een apart concern laat je juist staan. Vier dingen wezen
dezelfde kant op — de handler noemt zichzelf "dezelfde routes als het werkoverleg", het formulier
werd letterlijk mét de inbox gedeeld (`extra_hid`), `_outcome_info` stuurde per `@mention` een
notificatie (precies wat een actie met `@` doet), en zónder mention stuurde hij NIETS terwijl hij
"iedereen" meldde. Een echt prikbord zou juist daar broadcasten.

EN HIJ IS NIET VERLOREN. Een mededeling aan iemand is een ACTIE met `@`: dezelfde landing, maar als
werk dat terugkomt in plaats van als los bericht dat daarna nergens meer opduikt. Een ping is een
actie zonder stap voor de ander.

HEROPENEN MAG — maar dan als besluit, met een reden, niet als bijvangst van een refactor.
"""
from __future__ import annotations

import inspect
import pathlib

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


def test_de_wall_biedt_hem_ook_niet_meer():
    """Het derde scherm. Zie de docstring hierboven voor waarom dit drift was en geen broadcast."""
    import inspect as _i

    from nooch_village.views.feed import _wall_outcome_form
    html = _wall_outcome_form("p", "e", "t", "tekst", "<option>r</option>", "<option>p</option>")
    assert "value='info'" not in html and ">Info<" not in html
    # en de handler kent hem niet meer: fail-closed op een post met otype=info
    assert 'if otype == "info"' not in _i.getsource(cockpit2._act_wall_outcome)
    # de helper die "iedereen" uitsprak bestaat niet meer — weggehaald, niet gepatcht
    assert not hasattr(cockpit2, "_outcome_info")


def test_note_valt_bewust_buiten_de_drie():
    """`note` blijft, en dat is BESLOTEN (29 aug 2026) — geen vergeten hoekje.

    De reden is inhoudelijk, niet numeriek: `note` schrijft KENNIS bij een rol, de drie
    verwerk-uitkomsten routeren WERK uit een spanning. Dat zijn twee concerns — kennisbank versus
    werkroutering — en die vegen we niet samen.

    Dit is precies de omgekeerde afweging van de wall-info hierboven, en daarom staat hij hier: die
    LEEK een apart concern en was drift; `note` LIJKT een vierde peer en is een ander concern. Wie
    alleen naar het aantal kijkt ("drie hier, vier daar, dus die vierde moet weg") trekt de
    verkeerde conclusie. Zie docs/CONVENTIES.md → 'Verwerken is werk routeren'.

    Open ontwerppunt dat daar ook staat: juist omdat het een kennis-schrijf is, hoort `note`
    eigenlijk een eigen affordance te zijn en geen vierde peer in dezelfde kiezer. Nul gebruik op
    prod, dus geen haast — maar wél bewust doen als iemand hem gaat gebruiken."""
    import inspect as _i

    from nooch_village.views.feed import _wall_outcome_form
    html = _wall_outcome_form("p", "e", "t", "tekst", "<option>r</option>", "<option>p</option>")
    aangeboden = {o for o in ("info", "project", "action", "note", "roloverleg")
                  if f"value='{o}'" in html}
    assert aangeboden == {"project", "action", "note", "roloverleg"}
    assert "note" in _i.getsource(cockpit2._act_wall_outcome)
    # De reden staat opgeschreven waar een refactor hem tegenkomt, niet alleen hier.
    doc = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "CONVENTIES.md") \
        .read_text(encoding="utf-8")
    assert "`note` hoort er NIET bij" in doc
    assert "kennisbank versus werkroutering" in doc


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
