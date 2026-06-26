"""Diepe end-to-end journeys door de échte cockpit-HTTP-handler: GET de pagina, POST een actie
met geldige CSRF, GET opnieuw en verifieer dat de state ECHT veranderde. Dit vangt wat losse
render-tests missen (routes, redirects, dispatch, persistentie samen)."""
from __future__ import annotations
import json
import re
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer

from nooch_village import cockpit


def _seed(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "strategy.json").write_text(json.dumps({
        "purpose": "Nooch transforms the shoe industry.",
        "core_values": [{"title": "Care for All", "desc": "x"}],
        "north_star": {"target": 1000000}, "goals": [{"target": 1000, "active": True}]}),
        encoding="utf-8")
    recs = {"noochville": {"id": "noochville", "type": "circle", "parent": None, "version": 1,
                           "definition": {"purpose": "p"}, "members": ["scout", "harry_hemp"]},
            "scout": {"id": "scout", "type": "role", "parent": "noochville", "version": 1,
                      "definition": {"purpose": "markt", "accountabilities": ["Volgen van de markt"],
                                     "domains": []}},
            "harry_hemp": {"id": "harry_hemp", "type": "role", "parent": "noochville", "version": 1,
                           "definition": {"purpose": "hennep", "accountabilities": [], "domains": []}}}
    (data / "governance_records.json").write_text(json.dumps(recs), encoding="utf-8")
    (data / "projects.json").write_text(json.dumps({
        "p1": {"id": "p1", "owner": "harry_hemp", "scope": "Elastaan-vervanger zoeken",
               "trigger": "human", "status": "queued", "blocked_on": None, "created_at": 1,
               "updated_at": 1, "outcome": None, "hypothesis": "", "business_case": None,
               "origin": "", "executions": 0, "formalized": False, "comments": [], "log": []}}),
        encoding="utf-8")
    for f in ("human_inbox.json", "library.json"):
        (data / f).write_text("{}", encoding="utf-8")
    return str(data)


class _Server:
    def __init__(self, data_dir):
        self.httpd = HTTPServer(("127.0.0.1", 0), cockpit.make_handler(data_dir))
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return r.read().decode("utf-8")

    def csrf(self, path="/"):
        return re.search(r'name="csrf" value="([^"]+)"', self.get(path)).group(1)

    def post(self, fields):
        data = urllib.parse.urlencode(fields).encode()
        # volg redirect (303 → GET next); urllib doet dit automatisch
        with urllib.request.urlopen(self.base + "/action", data=data, timeout=8) as r:
            return r.read().decode("utf-8")

    def stop(self):
        self.httpd.shutdown()


def test_journey_home_toont_signaal_en_routes(tmp_path):
    srv = _Server(_seed(tmp_path))
    try:
        home = srv.get("/")
        assert "De missie" in home and "Aan jou" in home and "Het dorp werkt" in home
        # alle hoofd-routes laden (geen 500/empty)
        for path in ("/roloverleg", "/project?pid=p1", "/triage", "/fieldnotes"):
            body = srv.get(path)
            assert len(body) > 200, path
    finally:
        srv.stop()


def test_journey_project_status_en_chat(tmp_path):
    data = _seed(tmp_path)
    srv = _Server(data)
    try:
        token = srv.csrf("/")
        # status → toekomst (proj_future); verifieer dat de status ECHT wijzigt in de records
        srv.post({"csrf": token, "iid": "p1", "action": "proj_future", "next": "/"})
        from nooch_village.projects import ProjectLedger
        assert ProjectLedger(data + "/projects.json").get("p1")["status"] == "future"
        # de projectpagina toont de huidige status gemarkeerd
        page = srv.get("/project?pid=p1")
        assert "Toekomst" in page
        # bericht aan de rol → komt in het gesprekslog (rol-reply faalt fail-closed zonder LLM, prima)
        token2 = srv.csrf("/project?pid=p1")
        srv.post({"csrf": token2, "iid": "p1", "action": "proj_comment",
                  "comment": "focus op natuurlijke vezels", "next": "/project?pid=p1"})
        log = ProjectLedger(data + "/projects.json").get("p1").get("log", [])
        assert any(m["who"] == "mens" and "natuurlijke vezels" in m["text"] for m in log)
    finally:
        srv.stop()


def test_journey_project_spinoff_andere_rol(tmp_path):
    data = _seed(tmp_path)
    srv = _Server(data)
    try:
        token = srv.csrf("/project?pid=p1")
        srv.post({"csrf": token, "iid": "p1", "action": "proj_spinoff",
                  "spin_owner": "scout", "spin_msg": "toets de marktvraag",
                  "next": "/project?pid=p1"})
        from nooch_village.projects import ProjectLedger
        led = ProjectLedger(data + "/projects.json")
        assert any(p["owner"] == "scout" and p["scope"] == "toets de marktvraag" for p in led.all())
    finally:
        srv.stop()


def test_journey_roloverleg_consent_en_doorvoeren(tmp_path):
    data = _seed(tmp_path)
    # zet een voorstel op de agenda: scout krijgt een nieuwe accountability (herschrijving veilig)
    from nooch_village.roloverleg import Agenda
    ag = Agenda(data + "/roloverleg_agenda.json")
    iid = ag.add("scout", "amend_role", {"add_accountabilities": ["Bewaken van de socials"]},
                 "meer bereik", by="founder", title="Scout")
    srv = _Server(data)
    try:
        # consent
        token = srv.csrf(f"/roloverleg?iid={iid}")
        srv.post({"csrf": token, "iid": iid, "action": "rov_consent", "next": "/roloverleg"})
        assert Agenda(data + "/roloverleg_agenda.json").get(iid)["status"] == "consented"
        # einde roloverleg → doorvoeren → records bijgewerkt + item van de agenda
        token2 = srv.csrf("/roloverleg")
        srv.post({"csrf": token2, "action": "rov_end", "next": "/roloverleg"})
        from nooch_village.governance import Records
        rec = Records(data + "/governance_records.json").get("scout")
        assert "Bewaken van de socials" in rec.definition.accountabilities   # ECHT doorgevoerd
        assert Agenda(data + "/roloverleg_agenda.json").get(iid) is None     # van de agenda af
    finally:
        srv.stop()
