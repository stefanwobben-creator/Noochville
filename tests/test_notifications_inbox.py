"""Inbox-levenscyclus op NotifStore: nieuw → gelezen → verwerkt, archiveren alleen als verwerkt,
en de wachtrij (open_for_targets) verbergt gearchiveerde items. Backward-compat met oude 'read'-vlag."""
from __future__ import annotations

from nooch_village.notifications import NotifStore


def _store(tmp_path):
    return NotifStore(str(tmp_path / "notif.json"))


def test_status_of_drie_toestanden():
    assert NotifStore.status_of({}) == "nieuw"
    assert NotifStore.status_of({"read": True}) == "gelezen"
    assert NotifStore.status_of({"read": True, "processed": True}) == "verwerkt"
    assert NotifStore.status_of({"processed": True}) == "verwerkt"          # processed wint


def test_levenscyclus_nieuw_gelezen_verwerkt(tmp_path):
    s = _store(tmp_path)
    n = s.add("person", "p1", "proj1", "e1", by="scout", snippet="hoi")
    assert NotifStore.status_of(n) == "nieuw"
    assert s.mark_item_read(n["id"]) and NotifStore.status_of(s._find(n["id"])) == "gelezen"
    assert not s.mark_item_read(n["id"])                                    # idempotent
    assert s.mark_item_processed(n["id"]) and NotifStore.status_of(s._find(n["id"])) == "verwerkt"


def test_archiveren_alleen_als_verwerkt(tmp_path):
    s = _store(tmp_path)
    n = s.add("person", "p1", "proj1")
    assert not s.archive_item(n["id"])                                     # nieuw → mag niet
    s.mark_item_processed(n["id"])
    assert s.archive_item(n["id"])                                         # verwerkt → mag
    assert s._find(n["id"])["archived"] is True


def test_open_for_targets_verbergt_gearchiveerd(tmp_path):
    s = _store(tmp_path)
    a = s.add("person", "p1", "proj1", by="x")
    b = s.add("role", "r1", "proj2", by="y")
    s.mark_item_processed(a["id"]); s.archive_item(a["id"])
    open_ids = [n["id"] for n in s.open_for_targets([("person", "p1"), ("role", "r1")])]
    assert open_ids == [b["id"]]                                           # a gearchiveerd → weg
    # persoon + rollen samen: beide doelen tellen mee
    assert len(s.for_targets([("person", "p1"), ("role", "r1")])) == 2


def test_persoon_en_rollen_samengevoegd(tmp_path):
    # de inbox van een persoon bundelt mentions aan de persoon ZELF en aan elke rol die hij vervult
    s = _store(tmp_path)
    s.add("person", "stefan", "p1", by="noochie")
    s.add("role", "founding_father", "p2", by="secretary")
    s.add("role", "andere_rol", "p3", by="x")                             # niet van stefan
    targets = [("person", "stefan"), ("role", "founding_father")]
    got = {n["project_id"] for n in s.open_for_targets(targets)}
    assert got == {"p1", "p2"}                                            # p3 hoort niet bij stefan
