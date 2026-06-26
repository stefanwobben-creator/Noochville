"""Brok 5 — roster toont de inwoner (karakter) + de bemenst-as (onbemand = punt 3, via
role_status.json). Twee aparte signalen: wie zit erin, en kan de rol überhaupt werken."""
from __future__ import annotations
import json
import os
import tempfile

from nooch_village import cockpit
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.personas import PersonaStore


def _setup():
    d = tempfile.mkdtemp()
    recs = Records(os.path.join(d, "governance_records.json"))
    recs.put(Record(id="trends", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="vind woorden")))
    recs.put(Record(id="ghost", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="spook")))
    ps = PersonaStore(os.path.join(d, "personas.json"))
    sam = ps.add("Sam", "INTJ", "droog")
    recs.set_persona("trends", sam.id)
    return d


def test_gather_koppelt_inwoner_en_onbemand():
    d = _setup()
    json.dump({"manned": ["trends"], "unmanned": ["ghost"]},
              open(os.path.join(d, "role_status.json"), "w"))
    snap = cockpit.gather(d)
    tr = next(r for r in snap["roster"] if r["id"] == "trends")
    gh = next(r for r in snap["roster"] if r["id"] == "ghost")
    assert tr["inhabitant"] == {"name": "Sam", "mbti": "INTJ"} and tr["unmanned"] is False
    assert gh["inhabitant"] is None and gh["unmanned"] is True


def test_zonder_role_status_geen_onbemand_markering():
    d = _setup()                                  # geen role_status.json → niet kunnen weten
    snap = cockpit.gather(d)
    assert all(r["unmanned"] is False for r in snap["roster"])


def test_render_toont_inwoner_en_onbemand():
    d = _setup()
    json.dump({"manned": ["trends"], "unmanned": ["ghost"]},
              open(os.path.join(d, "role_status.json"), "w"))
    h = cockpit.render_html(cockpit.gather(d), csrf_token="t")
    assert "<th>inwoner</th>" in h
    assert "Sam" in h and "INTJ" in h
    assert "onbemand" in h and "geen inwoner" in h
