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
    page = cockpit.render_process(item, snap["roster"], "tok123")
    assert "Process Tension" in page
    assert "Wat heb je nodig" in page
    assert "Add Reference" in page                # live rail: info vastleggen
    assert "Add Project" in page                  # live rail: uitkomst voor een rol
    assert "Bring to Governance" in page          # live rail: rol een skill geven
    assert "website_watcher" in page              # rol-keuze uit de roster
    assert 'value="tok123"' in page               # csrf in de formulieren


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

        # Add Reference via POST → kennis-kaart geschreven, spanning blijft OPEN
        # (rail sluit niet; next=stay → terug naar de process-pagina)
        body = urllib.parse.urlencode({
            "csrf": token, "iid": "aaa111aaa111", "action": "add_reference",
            "next": "/process?iid=aaa111aaa111",
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
        assert inbox["aaa111aaa111"]["status"] == "pending"    # nog OPEN na de rail

        # Daarna bewust sluiten via "Klaar — afgehandeld" → resolved (niet withdrawn)
        done = urllib.parse.urlencode({
            "csrf": token, "iid": "aaa111aaa111", "action": "resolve", "next": "/"}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=done, method="POST"), timeout=5) as resp:
            assert resp.status == 200
        inbox = _json.loads((tmp_path / "data" / "human_inbox.json").read_text())
        assert inbox["aaa111aaa111"]["status"] == "resolved"   # afgehandeld via uitkomst
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=5)


def test_default_hides_grey_history_shows_it():
    snap = {
        "roster": [
            {"id": "live_role", "type": "role", "parent": "x", "version": 1,
             "archived": False, "source": "seed", "purpose": "p",
             "accountabilities": [], "domains": [], "skills": [], "policies": [], "members": []},
            {"id": "dead_role", "type": "role", "parent": "x", "version": 2,
             "archived": True, "source": "sensed", "purpose": "p",
             "accountabilities": [], "domains": [], "skills": [], "policies": [], "members": []},
        ],
        "inbox": [
            {"id": "i1", "type": "keyword", "subject": "open_word", "status": "pending",
             "context": {}, "created_at": 1.0},
            {"id": "i2", "type": "keyword", "subject": "closed_word", "status": "withdrawn",
             "context": {}, "created_at": 1.0},
        ],
        "projects": [
            {"id": "p1", "owner": "live_role", "scope": "open project", "status": "running",
             "blocked_on": None, "updated_at": 1.0},
            {"id": "p2", "owner": "live_role", "scope": "klaar project", "status": "done",
             "blocked_on": None, "updated_at": 1.0},
        ],
        "generated_at": 1.0, "data_dir": "x",
    }
    default = cockpit.render_html(snap, csrf_token="t")
    assert "open_word" in default and "open project" in default and "live_role" in default
    assert "closed_word" not in default        # gesloten inbox-item verborgen
    assert "dead_role" not in default          # gearchiveerde rol verborgen
    assert "klaar project" not in default      # done-project verborgen

    history = cockpit.render_html(snap, csrf_token="t", show_all=True)
    assert "closed_word" in history and "dead_role" in history and "klaar project" in history


def test_project_status_change_to_running(tmp_path):
    import json as _json
    data_dir = _seed(tmp_path)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit.make_handler(data_dir))
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        import re
        with urllib.request.urlopen(f"{base}/", timeout=5) as resp:
            token = re.search(r'name="csrf" value="([^"]+)"', resp.read().decode()).group(1)
        body = urllib.parse.urlencode({
            "csrf": token, "iid": "p1p1p1p1p1p1", "action": "proj_active", "next": "/"}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=body, method="POST"), timeout=5) as resp:
            assert resp.status == 200
        proj = _json.loads((tmp_path / "data" / "projects.json").read_text())
        items = proj.get("projects", proj) if isinstance(proj, dict) else {}
        assert items["p1p1p1p1p1p1"]["status"] == "running"
    finally:
        httpd.shutdown(); httpd.server_close(); t.join(timeout=5)


def test_gather_and_render_knowledge_views(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "human_inbox.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    (data / "library.json").write_text(json.dumps({
        "vegan sneakers": {"status": "approved", "by": "human", "date": "2026-06-24"},
        "fairtrade schoenen": {"status": "forbidden", "by": "human", "date": "2026-06-24"},
    }), encoding="utf-8")
    (data / "notes.json").write_text(json.dumps({
        "c1": {"id": "c1", "claim": "Most vegan sneakers contain plastic.", "source": "x",
               "grounds": "g", "status": "supported", "grounding_count": 3},
    }), encoding="utf-8")
    snap = cockpit.gather(str(data))
    assert any(x["word"] == "vegan sneakers" and x["status"] == "approved" for x in snap["library"])
    assert any(x["status"] == "forbidden" for x in snap["library"])
    assert snap["insights"][0]["grounding_count"] == 3

    # Standaard: alleen actieve (approved) woorden; forbidden verborgen.
    page = cockpit.render_html(snap, csrf_token="t")
    assert "Woordenschat" in page and "vegan sneakers" in page
    assert "fairtrade schoenen" not in page
    assert "Inzichten" in page and "Most vegan sneakers contain plastic" in page

    # Geschiedenis toont ook de verboden woorden.
    hist = cockpit.render_html(snap, csrf_token="t", show_all=True)
    assert "fairtrade schoenen" in hist


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
    assert p["status"] == "queued"                     # status ongemoeid
    pl.complete(pid)
    assert pl.edit(pid, scope="x") is False            # done vergrendeld


def test_server_project_edit(tmp_path):
    import re, json as _json
    data_dir = _seed(tmp_path)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit.make_handler(data_dir))
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"{base}/project?pid=p1p1p1p1p1p1", timeout=5) as resp:
            assert resp.status == 200
            page = resp.read().decode("utf-8")
        assert "Project bewerken" in page and "GSC menukaart" in page
        token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        body = urllib.parse.urlencode({
            "csrf": token, "iid": "p1p1p1p1p1p1", "action": "proj_edit", "next": "/",
            "owner": "website_watcher", "scope": "Nieuwe scope-tekst"}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=body, method="POST"), timeout=5) as resp:
            assert resp.status == 200
        proj = _json.loads((tmp_path / "data" / "projects.json").read_text())
        items = proj.get("projects", proj) if isinstance(proj, dict) else {}
        assert items["p1p1p1p1p1p1"]["scope"] == "Nieuwe scope-tekst"
    finally:
        httpd.shutdown(); httpd.server_close(); t.join(timeout=5)


def test_server_add_governance_grants_skill(tmp_path):
    import re, json as _json
    data_dir = _seed(tmp_path)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit.make_handler(data_dir))
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"{base}/process?iid=aaa111aaa111", timeout=5) as resp:
            page = resp.read().decode("utf-8")
        token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

        body = urllib.parse.urlencode({
            "csrf": token, "iid": "aaa111aaa111", "action": "add_governance",
            "next": "/process?iid=aaa111aaa111",
            "role": "website_watcher", "skill": "serpapi_trends",
            "rationale": "serpapi-bron bestaat al en wordt aangeroepen",
        }).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"{base}/action", data=body, method="POST"), timeout=5) as resp:
            assert resp.status == 200
            assert "toegekend" in resp.read().decode("utf-8")   # flash-banner zichtbaar

        recs = _json.loads((tmp_path / "data" / "governance_records.json").read_text())
        ww = recs["website_watcher"] if "website_watcher" in recs else recs
        assert "serpapi_trends" in ww["definition"]["skills"]   # skill via de gate toegekend
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=5)


def test_serve_refuses_non_local_host():
    with pytest.raises(SystemExit):
        cockpit.serve(host="0.0.0.0", port=0)
