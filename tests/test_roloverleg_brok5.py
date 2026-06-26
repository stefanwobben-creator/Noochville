"""Roloverleg brok 5: na consent dóór naar het volgende open agendapunt (p.4 punt 11)."""
from __future__ import annotations

from nooch_village import cockpit
from nooch_village.roloverleg import Agenda


def _agenda(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = Agenda(str(data / "roloverleg_agenda.json"))
    return data, ag


def test_volgende_open_agendapunt(tmp_path):
    data, ag = _agenda(tmp_path)
    a = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r1", by="scout")
    b = ag.add(role_id="librarian", kind="amend_role", change={"purpose": "y"}, reason="r2", by="librarian")
    # na consent op a → door naar b
    nxt = cockpit._next_open_agenda(str(data), a)
    assert nxt == f"/roloverleg?iid={b}"


def test_geen_open_meer_terug_naar_overview(tmp_path):
    data, ag = _agenda(tmp_path)
    a = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r", by="scout")
    # a is het enige punt → na consent geen volgende → overview
    nxt = cockpit._next_open_agenda(str(data), a)
    assert nxt == "/roloverleg"


def test_consented_punt_telt_niet_als_volgende(tmp_path):
    data, ag = _agenda(tmp_path)
    a = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r1", by="scout")
    b = ag.add(role_id="librarian", kind="amend_role", change={"purpose": "y"}, reason="r2", by="librarian")
    ag.set_status(b, "consented")           # b is al aangenomen → geen open punt meer
    assert cockpit._next_open_agenda(str(data), a) == "/roloverleg"
