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

from nooch_village import cockpit


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
            "trigger": "human", "status": "queued", "blocked_on": None,
            "created_at": time.time(), "updated_at": time.time(), "outcome": None,
        },
    }), encoding="utf-8")
    return str(data)


def test_gather_reads_three_stores(tmp_path):
    snap = cockpit.gather(_seed(tmp_path))
    assert {r["id"] for r in snap["roster"]} == {"noochville", "website_watcher"}
    assert snap["inbox"][0]["subject"] == "ngram_2019_cutoff"
    assert snap["projects"][0]["owner"] == "website_watcher"


def test_gather_missing_dir_is_safe(tmp_path):
    snap = cockpit.gather(str(tmp_path / "leeg"))
    assert snap == {**snap, "roster": [], "inbox": [], "projects": []}


def test_render_contains_key_facts(tmp_path):
    page = cockpit.render_html(cockpit.gather(_seed(tmp_path)))
    assert "website_watcher" in page and "ngram_2019_cutoff" in page
    assert "plausible_stats" in page and "GSC menukaart" in page
    assert "read-only" in page.lower()


def test_render_writable_has_action_buttons(tmp_path):
    snap = cockpit.gather(_seed(tmp_path))
    page = cockpit.render_html(snap, csrf_token="tok123")
    assert "verwerk-modus" in page
    assert "Defer" in page                      # pending means_gap krijgt een defer-knop
    assert 'value="tok123"' in page             # csrf-token in de formulieren
    # read-only (geen token) → geen knoppen
    ro = cockpit.render_html(snap)
    assert "Defer" not in ro


def test_render_escapes_html(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "governance_records.json").write_text(json.dumps({
        "x": {"id": "x", "type": "role", "parent": None,
              "definition": {"purpose": "<script>alert(1)</script>",
                             "accountabilities": [], "domains": [], "skills": [],
                             "policies": []},
              "members": [], "version": 1, "archived": False, "source": "seed"},
    }), encoding="utf-8")
    page = cockpit.render_html(cockpit.gather(str(data)))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_server_get_and_post_action(tmp_path):
    import re, json as _json
    data_dir = _seed(tmp_path)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit.make_handler(data_dir))
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # GET → 200, en haal de CSRF-token uit de pagina
        with urllib.request.urlopen(f"{base}/", timeout=5) as resp:
            assert resp.status == 200
            page = resp.read().decode("utf-8")
        token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

        # POST naar verkeerd pad → 404
        with pytest.raises(urllib.error.HTTPError) as e404:
            urllib.request.urlopen(urllib.request.Request(
                f"{base}/", data=b"x", method="POST"), timeout=5)
        assert e404.value.code == 404

        # POST /action zonder geldige token → 403
        bad = urllib.parse.urlencode({"csrf": "fout", "iid": "aaa111aaa111",
                                      "action": "defer"}).encode()
        with pytest.raises(urllib.error.HTTPError) as e403:
            urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=bad, method="POST"), timeout=5)
        assert e403.value.code == 403

        # POST /action mét token → defert het item (303 → gevolgd naar GET /)
        good = urllib.parse.urlencode({"csrf": token, "iid": "aaa111aaa111",
                                       "action": "defer", "reason": "later"}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=good, method="POST"), timeout=5) as resp:
            assert resp.status == 200      # urllib volgt de 303 naar GET /

        # Effect: het item staat nu op 'deferred' in de store
        inbox = _json.loads((tmp_path / "data" / "human_inbox.json").read_text())
        assert inbox["aaa111aaa111"]["status"] == "deferred"
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=5)


def test_process_page_renders_glassfrog_flow(tmp_path):
    snap = cockpit.gather(_seed(tmp_path))
    item = snap["inbox"][0]                       # de pending means_gap
    page = cockpit.render_process(item, "tok123")
    assert "Process Tension" in page
    assert "Wat heb je nodig" in page
    assert "Add Reference" in page                # de live rail
    assert 'value="tok123"' in page               # csrf in de formulieren
    assert "volgende stap" in page                # de nog-niet-live rails als structuur


def test_server_process_get_and_add_reference(tmp_path):
    import re, json as _json
    data_dir = _seed(tmp_path)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit.make_handler(data_dir))
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # /process?iid= → 200 met de flow + de csrf-token
        with urllib.request.urlopen(f"{base}/process?iid=aaa111aaa111", timeout=5) as resp:
            assert resp.status == 200
            page = resp.read().decode("utf-8")
        token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

        # Add Reference via POST → kennis-kaart geschreven + item gesloten
        body = urllib.parse.urlencode({
            "csrf": token, "iid": "aaa111aaa111", "action": "add_reference",
            "claim": "Visitor data must be analysed per locale.",
            "grounds": "Different markets behave differently; one aggregate hides the signal.",
        }).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=body, method="POST"), timeout=5) as resp:
            assert resp.status == 200

        notes = _json.loads((tmp_path / "data" / "notes.json").read_text())
        notes_items = notes.get("notes", notes) if isinstance(notes, dict) else {}
        assert any("locale" in (c.get("claim", "")) for c in notes_items.values())
        inbox = _json.loads((tmp_path / "data" / "human_inbox.json").read_text())
        assert inbox["aaa111aaa111"]["status"] == "approved"   # spanning gesloten
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=5)


def test_serve_refuses_non_local_host():
    with pytest.raises(SystemExit):
        cockpit.serve(host="0.0.0.0", port=0)
