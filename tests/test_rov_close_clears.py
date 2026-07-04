"""Regressie: 'Vergadering sluiten' (rov2_end) rondt de governance-meeting écht af — de resterende
onbehandelde agendapunten van die cirkel gaan van de agenda, zodat de groene "Governance meeting"-
knop (die op _rov_items afgaat) niet blijft hangen."""
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


def test_sluiten_ruimt_open_punten_op_en_knop_gaat_uit(tmp_path):
    dd = _dd(tmp_path)
    _add_open_item(dd)
    assert _rov_items(cockpit2._Stores(dd), CIRCLE)              # knop groen vóór sluiten
    cockpit2.dispatch(dd, "rov2_end", {"circle": [CIRCLE], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    assert _rov_items(st, CIRCLE) == []                          # knop uit na sluiten
    assert st.agenda.get("x1") is None                          # onbehandeld punt van de agenda


def test_sluiten_raakt_andere_cirkel_niet(tmp_path):
    # Alleen de agenda van DEZE cirkel wordt geleegd; een punt van een andere cirkel blijft.
    dd = _dd(tmp_path)
    _add_open_item(dd, "mine")
    st = cockpit2._Stores(dd)
    st.agenda._items.append({"id": "other", "role_id": "mother_earth__secretary", "kind": "amend_role",
                             "change": {}, "status": "open", "title": "Ander", "group": "other",
                             "created_at": 1.0})
    st.agenda._save()
    cockpit2.dispatch(dd, "rov2_end", {"circle": [CIRCLE], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    assert st.agenda.get("mine") is None                        # deze cirkel: weg
    assert st.agenda.get("other") is not None                   # andere cirkel: blijft
