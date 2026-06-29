"""Een bewuste persona-hernoeming overleeft migrate_records; een lege persona wordt nog wél
hersteld. Borgt dat de persona-restore in seeds.migrate_records geen opzettelijke namen klobbert."""
from __future__ import annotations

from nooch_village.governance import Records
from nooch_village.seeds import seed_records, migrate_records


def _seed(tmp_path) -> Records:
    recs = Records(str(tmp_path / "gov.json"))
    seed_records(recs)        # lege dir -> seed-rollen incl. website_watcher (persona "Corry Coconut")
    migrate_records(recs)
    return recs


def test_bewuste_hernoeming_overleeft_migrate(tmp_path):
    recs = _seed(tmp_path)
    rec = recs.get("website_watcher")
    rec.persona = "Walter Website"     # bewuste hernoeming door de mens
    recs.put(rec)
    migrate_records(recs)              # mag de hernoeming NIET terugdraaien
    assert recs.get("website_watcher").persona == "Walter Website"


def test_lege_persona_wordt_hersteld(tmp_path):
    recs = _seed(tmp_path)
    rec = recs.get("website_watcher")
    rec.persona = ""                   # verlies, bijv. na een save/_load die de persona dropte
    recs.put(rec)
    migrate_records(recs)              # moet de seed-naam herstellen
    assert recs.get("website_watcher").persona == "Corry Coconut"
