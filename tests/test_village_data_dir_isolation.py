"""R2-hardening: Village(data_dir=...) isoleert ALLE schrijf-stores.

Achtergrond: simulate() draaide op de echte data-dir en schreef proposals/
escalaties naar de echte human_inbox + governance_records (de escalatie-storm).
De override moet alle schrijf-paden naar de wegwerp-map sturen, zodat productie
ongemoeid blijft. Geen netwerk; we starten de dorpsthreads niet."""
from __future__ import annotations
import os
import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__)))

from nooch_village.village import Village


def test_data_dir_override_verplaatst_alle_stores(tmp_path):
    sandbox = str(tmp_path / "sandbox")
    v = Village(heartbeat_seconds=86400, data_dir=sandbox)

    # context.data_dir wijst naar de sandbox
    assert v.context.data_dir == sandbox

    # De kern-schrijfbestanden landen in de sandbox, niet in de echte data-dir
    assert os.path.exists(os.path.join(sandbox, "governance_records.json"))
    # De schrijf-stores (records + human_inbox) wijzen naar de sandbox
    assert sandbox in v.records.path
    assert sandbox in v.human_inbox.path


def test_twee_sandboxes_delen_geen_state(tmp_path):
    a = Village(heartbeat_seconds=86400, data_dir=str(tmp_path / "a"))
    b = Village(heartbeat_seconds=86400, data_dir=str(tmp_path / "b"))
    assert a.context.data_dir != b.context.data_dir
    assert a.records.path != b.records.path
