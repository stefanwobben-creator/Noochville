"""Koppeling rol → inwoner: Record.persona_id, Records.set_persona en serialisatie-rondrit."""
from __future__ import annotations
import os
import tempfile

from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition


def _records():
    path = os.path.join(tempfile.mkdtemp(), "gov.json")
    recs = Records(path)
    recs.put(Record(id="librarian", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="cureert de bibliotheek")))
    return recs, path


def test_set_persona_koppelt_en_ontkoppelt():
    recs, _ = _records()
    assert recs.set_persona("librarian", "p123") is True
    assert recs.get("librarian").persona_id == "p123"
    assert recs.set_persona("librarian", None) is True          # ontkoppelen
    assert recs.get("librarian").persona_id is None
    assert recs.set_persona("bestaat_niet", "p1") is False


def test_persona_id_overleeft_serialisatie():
    recs, path = _records()
    recs.set_persona("librarian", "sam")
    # herladen uit het bestand
    assert Records(path).get("librarian").persona_id == "sam"


def test_persona_id_blijft_na_amend():
    recs, _ = _records()
    recs.set_persona("librarian", "sam")
    rec = recs.get("librarian")
    rec.definition.accountabilities.append("nieuwe accountability")  # amend in-place
    rec.version += 1
    recs.put(rec)
    assert recs.get("librarian").persona_id == "sam"            # koppeling niet weg
