"""Tests voor de mens-zetel (Record.held_by + Records.set_holder). Thread-vrij."""
from __future__ import annotations

from nooch_village.governance import Records
from nooch_village.seeds import seed_records, migrate_records


def _seeded(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_set_holder_zet_de_zetel(tmp_path):
    records = _seeded(tmp_path)
    assert records.set_holder("the_source", "Stefan") is True
    assert records.get("the_source").held_by == "Stefan"


def test_held_by_overleeft_opslaan_en_herladen(tmp_path):
    path = str(tmp_path / "gov.json")
    r1 = Records(path)
    seed_records(r1)
    migrate_records(r1)
    r1.set_holder("the_source", "Stefan")

    r2 = Records(path)                       # vers ingeladen vanaf schijf
    assert r2.get("the_source").held_by == "Stefan"


def test_set_holder_onbekende_rol_false(tmp_path):
    records = _seeded(tmp_path)
    assert records.set_holder("bestaat_niet", "Stefan") is False


def test_held_by_default_none(tmp_path):
    records = _seeded(tmp_path)
    assert records.get("the_source").held_by is None      # vóór seating
