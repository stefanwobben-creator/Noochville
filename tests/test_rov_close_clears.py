"""Sluiten rondt de vergadering af — en gooit niet weg wat er niet behandeld is.

OMGEDRAAID OP 28 SEPTEMBER 2026, en de premisse van dit bestand was de bug.

Hier stond: "de resterende onbehandelde agendapunten van die cirkel gaan van de agenda, zodat de
groene Governance meeting-knop (die op `_rov_items` afgaat) niet blijft hangen." Die knop gaat niet
op `_rov_items` af. `cockpit2_util.overleg_items` geeft het roloverleg een gewone link en alleen het
WERKoverleg een live-staat — dat staat er zelfs met zoveel woorden in ("Roloverleg heeft geen
open/dicht-staat"). Er werd dus werk weggegooid voor een schermeffect dat niet bestaat.

WAT HET KOSTTE, gemeld op 28 september: een domein toevoegen aan een rol, dan op de opvallendste
groene knop drukken ("Close meeting", in de vaste voet) — en het voorstel was weg. Geen rol met
domein, geen agendapunt, geen reden. Zie `tests/test_roloverleg_domein.py` voor die keten.

WAT SLUITEN WÉL DOET: de aangenomen voorstellen schrijven en van de agenda halen. De rest blijft
liggen; `Agenda.open()` geeft open én objected punten het volgende overleg gewoon terug.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.roloverleg import _rov_items

CIRCLE = "mother_earth__nooch"
ROLE = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _add_open_item(dd, iid="x1"):
    st = cockpit2._Stores(dd)
    st.agenda._items.append({"id": iid, "role_id": ROLE, "kind": "amend_role", "change": {},
                             "status": "open", "title": "Test", "group": iid, "created_at": 1.0})
    st.agenda._save()


def test_een_onbehandeld_punt_blijft_liggen(tmp_path):
    """DE OMGEKEERDE ASSERTIE VAN VROEGER. Niet behandeld is niet hetzelfde als afgewezen, en al
    helemaal niet hetzelfde als nooit ingediend."""
    dd = _dd(tmp_path)
    _add_open_item(dd)
    cockpit2.dispatch(dd, "rov2_end", {"circle": [CIRCLE], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    assert st.agenda.get("x1") is not None
    assert _rov_items(st, CIRCLE), "de agenda van deze cirkel is leeggehaald"
    assert st.agenda.get("x1") in st.agenda.open(), "het komt niet terug in het volgende overleg"


def test_de_knop_hing_nooit_aan_de_agenda():
    """De rechtvaardiging die hier stond, nagemeten in plaats van overgenomen."""
    import inspect
    import re

    from nooch_village.cockpit2_util import overleg_items
    kaal = re.sub(r'"""(?:.|\n)*?"""', "", inspect.getsource(overleg_items))
    assert "agenda" not in kaal and "_rov_items" not in kaal
    assert "c2-overleg--live" not in overleg_items(CIRCLE, werk_open=True).split("/roloverleg2")[1]


def test_sluiten_raakt_andere_cirkels_niet(tmp_path):
    """Ongewijzigd van betekenis: wat een andere cirkel op de agenda heeft, is niet van deze
    vergadering. Nu geldt dat voor allebei de kanten — er wordt nergens meer iets weggegooid."""
    dd = _dd(tmp_path)
    _add_open_item(dd, "mine")
    st = cockpit2._Stores(dd)
    st.agenda._items.append({"id": "other", "role_id": "mother_earth__secretary", "kind": "amend_role",
                             "change": {}, "status": "open", "title": "Ander", "group": "other",
                             "created_at": 1.0})
    st.agenda._save()
    cockpit2.dispatch(dd, "rov2_end", {"circle": [CIRCLE], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    assert st.agenda.get("mine") is not None
    assert st.agenda.get("other") is not None
