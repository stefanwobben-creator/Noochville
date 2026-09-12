"""Read-only tests voor de cockpit. Geen Village, geen netwerk-afhankelijkheid
buiten een korte loopback-server op poort 0."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer

import pytest



def _seed(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "governance_records.json").write_text(json.dumps({
        "noochville": {
            "id": "noochville", "type": "circle", "parent": None,
            "definition": {"purpose": "anchor", "accountabilities": [],
                           "domains": [], "skills": [], "policies": ["plasticvrij"]},
            "members": ["website_watcher"], "version": 2, "archived": False, "source": "seed",
        },
        "website_watcher": {
            "id": "website_watcher", "type": "role", "parent": "noochville",
            "definition": {"purpose": "Data omzetten in advies",
                           "accountabilities": ["bezoekersdata duiden"],
                           "domains": ["analytics"], "skills": ["plausible_stats"],
                           "policies": []},
            "members": [], "version": 8, "archived": False, "source": "seed",
        },
    }), encoding="utf-8")
    (data / "human_inbox.json").write_text(json.dumps({
        "aaa111aaa111": {
            "id": "aaa111aaa111", "type": "means_gap", "subject": "ngram_2019_cutoff",
            "context": {"gap_key": "ngram_2019_cutoff",
                        "description": "ngram-data stopt bij 2019", "role_id": "website_watcher"},
            "status": "pending", "created_at": time.time(),
            "resolved_at": None, "resolution": None,
        },
    }), encoding="utf-8")
    (data / "projects.json").write_text(json.dumps({
        "p1p1p1p1p1p1": {
            "id": "p1p1p1p1p1p1", "owner": "website_watcher", "scope": "GSC menukaart",
            "trigger": "human", "status": "running", "blocked_on": None,
            "created_at": time.time(), "updated_at": time.time(), "outcome": None,
        },
    }), encoding="utf-8")
    return str(data)
























def test_means_gap_stores_sensed_by(tmp_path):
    from nooch_village.human_inbox import HumanInbox
    hi = HumanInbox(str(tmp_path / "i.json"))
    iid = hi.add_means_gap("g", "iets", role_id="website_watcher", sensed_by="harry_hemp")
    assert hi.get(iid)["context"]["sensed_by"] == "harry_hemp"












def test_projectledger_to_future(tmp_path):
    from nooch_village.projects import ProjectLedger
    pl = ProjectLedger(str(tmp_path / "p.json"))
    pid = pl.create("trends", "iets voor later", "human")
    assert pl.to_future(pid) is True
    assert pl.get(pid)["status"] == "future"
    pl.complete(pid)                                   # done is terminal
    assert pl.to_future(pid) is False                  # done blijft done


def test_projectledger_edit(tmp_path):
    from nooch_village.projects import ProjectLedger
    pl = ProjectLedger(str(tmp_path / "p.json"))
    pid = pl.create("analyst", {"kind": "discovery"}, "human")
    assert pl.edit(pid, scope="Bezoekersdata per locale analyseren", owner="website_watcher")
    p = pl.get(pid)
    assert p["scope"] == "Bezoekersdata per locale analyseren" and p["owner"] == "website_watcher"
    assert p["status"] == "future"                     # status ongemoeid
    pl.complete(pid)
    assert pl.edit(pid, scope="x") is False            # done vergrendeld










