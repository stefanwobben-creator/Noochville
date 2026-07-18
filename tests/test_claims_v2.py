"""Claims-checker v2: de governeerde view, de server-side scan, de taakkoppeling en
de wekelijkse zelfscan.

De twee dingen die hier écht bewaakt worden: de **dedupe** (zonder dedupe spamt elke scan
het bord vol) en de **fail-closed**-regel (een mislukte scan mag nooit als 'geen claims' lezen).
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from nooch_village import claims_board, claims_db, cockpit2
from nooch_village.projects import ProjectLedger
from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill
from nooch_village.views.claims import render_claims, render_rapport, rol_voor

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nooch_village")


def _ledger(tmp_path) -> ProjectLedger:
    return ProjectLedger(str(tmp_path / "projects.json"))


def _omg(tmp_path, ledger=None):
    """Minimale omgeving voor zet_op_bord: het projectenbord plus een data_dir waar de
    berichten-store zichzelf uit kan opbouwen."""
    return SimpleNamespace(projects=ledger or _ledger(tmp_path), records=None,
                           data_dir=str(tmp_path))


def _bev(term="zero waste", gevonden=("zero waste",), stoplicht="red",
         categorie="Toekomst/absoluut", pagina="home", url="https://nooch.earth/"):
    return {"term": term, "gevonden": list(gevonden), "stoplicht": stoplicht,
            "categorie": categorie, "waarom": "absolute claim", "alternatief": "made on demand",
            "pagina": pagina, "url": url}


# ── Taak 1: de view ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("tab", ["check", "werklijst", "database", "landen"])
def test_elk_tabblad_rendert_in_het_designsysteem(tab):
    html = render_claims(csrf_token="t", tab=tab)
    assert "/static/nooch.css" in html                  # designsysteem, geen eigen opmaak
    assert "<style>" not in html.split("</head>")[1]    # geen eigen stylesheet in de body
    assert "style=" not in html
    assert "Claims-checker" in html


def test_beheerblok_alleen_voor_wie_mag_cureren():
    zonder = render_claims(csrf_token="t", tab="werklijst", kan_cureren=False)
    met = render_claims(csrf_token="t", tab="werklijst", kan_cureren=True)
    assert "claims_term_add" not in zonder and "claims_work_status" not in zonder
    assert "claims_term_add" in met and "claims_work_status" in met


def test_database_tab_filtert_op_zoekterm():
    alles = render_claims(tab="database")
    gefilterd = render_claims(tab="database", zoek="klimaneutral")
    assert gefilterd.count("<tr>") < alles.count("<tr>")
    assert "klimaneutral" in gefilterd


def test_rapport_toont_score_stoplicht_en_rolroutering():
    uitslag = claims_db.check_tekst("100% planet-safe en zero waste")
    uitslag["tekst"] = "100% planet-safe en zero waste"
    html = render_rapport(uitslag, markten=["NL"], bron="geplakte tekst", db=claims_db.load())
    assert "kpi-val" in html                             # score als groot getal
    assert "chip coral" in html                          # rood stoplicht
    assert "rol: copywriter" in html                     # rol-routing per bevinding
    assert "<mark>" in html                              # gemarkeerde tekst-preview
    assert "Marktspecifiek" in html                      # landnotitie NL
    assert "style=" not in html


def test_rapport_zonder_bevindingen_is_geen_lege_pagina():
    uitslag = claims_db.check_tekst("Handgemaakt in Portugal.")
    html = render_rapport(uitslag, db=claims_db.load())
    assert "Geen vlagwoorden gevonden" in html
    assert "claims_to_board" not in html                 # niets om op het bord te zetten


def test_bordknop_alleen_voor_compliance():
    uitslag = claims_db.check_tekst("zero waste")
    zonder = render_rapport(uitslag, csrf_token="t", kan_bord=False, db=claims_db.load())
    met = render_rapport(uitslag, csrf_token="t", kan_bord=True, db=claims_db.load())
    assert "claims_to_board" not in zonder
    assert "claims_to_board" in met


def test_defecte_database_geeft_zichtbare_fout(monkeypatch, tmp_path):
    monkeypatch.setattr(claims_db, "DB_PATH", str(tmp_path / "weg.json"))
    html = render_claims()
    assert "kon niet geladen worden" in html             # fail-closed, geen lege checker


# ── Taak 3: de server-side scan ─────────────────────────────────────────────

def test_scan_van_tekst():
    uitslag, bron = cockpit2._claims_scan({"tekst": ["zero waste en klimaatneutraal"]})
    assert uitslag["rood"] >= 2
    assert bron == "geplakte tekst"


def test_scan_weigert_interne_url():
    """SSRF: de server mag zijn eigen netwerk niet uitlenen aan een ingetypte URL."""
    uitslag, _ = cockpit2._claims_scan({"url": ["http://127.0.0.1:8766/claims"]})
    assert "interne adressen" in uitslag["error"]
    assert "bevindingen" not in uitslag                  # geen stille lege uitslag


def test_scan_weigert_niet_http():
    uitslag, _ = cockpit2._claims_scan({"url": ["file:///etc/passwd"]})
    assert "http" in uitslag["error"]


def test_scan_zonder_invoer():
    uitslag, _ = cockpit2._claims_scan({})
    assert "error" in uitslag


def test_mislukte_fetch_leest_nooit_als_schoon(monkeypatch):
    """Fail-closed: een onbereikbare pagina geeft een fout, geen score van 100."""
    from nooch_village import safe_fetch

    def kapot(url, _fetch=None):
        raise safe_fetch.FetchMislukt("timeout")
    monkeypatch.setattr(safe_fetch, "haal_tekst", kapot)
    uitslag, _ = cockpit2._claims_scan({"url": ["https://nooch.earth/"]})
    assert "error" in uitslag and "score" not in uitslag
    assert "handmatig" in uitslag["error"]               # het advies uit de brief


def test_geen_publieke_proxy_meer_in_de_code():
    """De client-side proxy-omweg (allorigins/corsproxy) is volledig verdwenen."""
    with open(os.path.join(PKG, "views", "claims.py"), encoding="utf-8") as f:
        bron = f.read()
    assert "allorigins" not in bron and "corsproxy" not in bron


# ── Taak 4: taken op het bord ───────────────────────────────────────────────

def test_bekende_claim_uit_de_werklijst_levert_geen_taak(tmp_path):
    """De acceptatietest: een scan met bekende bevindingen zet niets nieuws op het bord."""
    led = _ledger(tmp_path)
    db = claims_db.load()
    # "100% Planet-Safe" staat als werklijst-item #1; de scan vindt 'Planet-Safe'
    verslag = claims_board.zet_op_bord(_omg(tmp_path, led), db, [_bev(gevonden=["Planet-Safe"])],
                                       "https://nooch.earth/", rol_voor)
    assert verslag["aangemaakt"] == []
    assert verslag["overgeslagen"] == 1
    assert led.all() == []


def test_nieuwe_rode_term_levert_precies_een_taak_bij_de_juiste_rol(tmp_path):
    led = _ledger(tmp_path)
    db = claims_db.load()
    nieuw = _bev(term="gifvrij", gevonden=["volstrekt gifvrij"], categorie="Statistiek")
    verslag = claims_board.zet_op_bord(_omg(tmp_path, led), db, [nieuw], "https://nooch.earth/", rol_voor)
    assert len(verslag["aangemaakt"]) == 1
    taak = verslag["aangemaakt"][0]
    assert taak["owner"] == claims_board.ROL_IDS["marketeer"]      # Statistiek → marketeer
    project = led.get(taak["pid"])
    assert "volstrekt gifvrij" in project["scope"]
    assert "made on demand" in project["description"]              # de herformulering zit erin
    assert "tov + legal" in project["description"]                 # de nacheck ook
    assert project["origin"] == claims_board.ORIGIN


def test_tweede_scan_van_dezelfde_bevinding_dedupliceert(tmp_path):
    led = _ledger(tmp_path)
    db = claims_db.load()
    nieuw = _bev(term="gifvrij", gevonden=["volstrekt gifvrij"])
    eerste = claims_board.zet_op_bord(_omg(tmp_path, led), db, [nieuw], "x", rol_voor)
    tweede = claims_board.zet_op_bord(_omg(tmp_path, led), db, [nieuw], "x", rol_voor)
    assert len(eerste["aangemaakt"]) == 1
    assert tweede["aangemaakt"] == []                              # geen bord-spam
    assert len(led.all()) == 1


def test_dedupe_binnen_een_run(tmp_path):
    led = _ledger(tmp_path)
    nieuw = _bev(term="gifvrij", gevonden=["volstrekt gifvrij"])
    verslag = claims_board.zet_op_bord(_omg(tmp_path, led), claims_db.load(), [nieuw, dict(nieuw)],
                                       "x", rol_voor)
    assert len(verslag["aangemaakt"]) == 1


def test_afgehandelde_werklijst_blokkeert_een_terugkeer_niet(tmp_path):
    """Status 'live' = opgelost. Duikt de claim daarna weer op, dan is dat nieuw werk."""
    led = _ledger(tmp_path)
    db = claims_db.load()
    for w in db["werklijst"]:                       # de hele audit afgehandeld
        w["status"] = "live"
    verslag = claims_board.zet_op_bord(_omg(tmp_path, led), db, [_bev(gevonden=["Planet-Safe"])],
                                       "x", rol_voor)
    assert len(verslag["aangemaakt"]) == 1


def test_groene_bevindingen_worden_nooit_werk(tmp_path):
    led = _ledger(tmp_path)
    verslag = claims_board.zet_op_bord(_omg(tmp_path, led), claims_db.load(),
                                       [_bev(term="vegan", gevonden=["vegan"], stoplicht="green")],
                                       "x", rol_voor)
    assert verslag["aangemaakt"] == []


@pytest.mark.parametrize("categorie,verwacht", [
    ("Labels", "visual designer"), ("Vergelijkend", "marketeer"), ("Statistiek", "marketeer"),
    ("Sociaal", "compliance"), ("Framing", "copywriter + compliance"), ("Generiek", "copywriter"),
])
def test_rolroutering(categorie, verwacht):
    assert rol_voor(categorie) == verwacht


def test_onbekende_rol_valt_terug_op_compliance():
    """Liever bij de domein-eigenaar dan bij een dood record-id."""
    class GeenRecords:
        def get(self, _):
            return None
    assert claims_board.rol_id_voor("copywriter", GeenRecords()) == "compliance"


def test_dispatch_bord_weigert_andere_rollen(tmp_path):
    payload = json.dumps({"bevindingen": [_bev()]})
    _, msg = cockpit2.dispatch(str(tmp_path), "claims_to_board",
                               {"bevindingen": [payload], "next": ["/claims"]},
                               "niemand@nergens.nl")
    assert "Geen toegang" in msg


def test_dispatch_bord_maakt_taken(tmp_path, monkeypatch):
    dd = tmp_path / "data"
    dd.mkdir()
    payload = json.dumps({"bevindingen": [_bev(term="gifvrij", gevonden=["volstrekt gifvrij"])]})
    _, msg = cockpit2.dispatch(str(dd), "claims_to_board",
                               {"bevindingen": [payload], "bron": ["https://nooch.earth/"],
                                "next": ["/claims"]}, "guest")
    assert msg.startswith("✓ 1 taak")
    assert len(ProjectLedger(str(dd / "projects.json")).all()) == 1


# ── Taak 5: de wekelijkse zelfscan ──────────────────────────────────────────

# 'eco-friendly' staat wél in de termendatabase maar niet in de werklijst → nieuw werk.
# 'zero waste' staat in beide → moet worden overgeslagen.
_PAGINA = ("<html><head><title>Test</title></head><body>"
           "Onze eco-friendly schoenen zijn compleet zero waste.</body></html>")


def _ctx(tmp_path, monkeypatch=None):
    """Scan-context met een WEGWERPKOPIE van de claims-database.

    De scan schrijft werklijst-statussen terug naar de bron (v3, zelfverificatie). Zonder deze
    kopie zou een test de repo-database muteren — `test_config_claims_database_blijft_ongemoeid`
    bewaakt dat dat nooit meer gebeurt."""
    if monkeypatch is not None:
        kopie = tmp_path / "claims_database.json"
        kopie.write_text(json.dumps(claims_db.load(), ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(claims_db, "DB_PATH", str(kopie))
    return SimpleNamespace(data_dir=str(tmp_path), settings={},
                           projects=_ledger(tmp_path), records=None)


def test_scan_maakt_taak_van_nieuwe_term_en_is_weekidempotent(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA)}, ctx)
    assert uit["ok"] and not uit["skipped"]
    assert uit["nieuw"] >= 1
    titels = [t["titel"] for t in uit["aangemaakt"]]
    assert any("eco-friendly" in t.lower() for t in titels)
    assert not any("zero waste" in t.lower() for t in titels)     # staat al in de werklijst

    tweede = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA)}, ctx)
    assert tweede["skipped"] is True                              # tweede puls dezelfde week
    assert len(ctx.projects.all()) == uit["nieuw"]


def test_scan_escaleert_als_geen_enkele_pagina_laadt(tmp_path):
    from nooch_village import safe_fetch

    def kapot(u):
        raise safe_fetch.FetchMislukt("host onbereikbaar")
    uit = ClaimsSiteScanSkill().run({"_fetch": kapot}, _ctx(tmp_path))
    assert uit["ok"] is False
    assert "geen enkele pagina" in uit["escalate"]["reason"]
    assert uit.get("nieuw") is None                               # geen stille 0


def test_scan_escaleert_bij_corrupte_database(tmp_path, monkeypatch):
    monkeypatch.setattr(claims_db, "DB_PATH", str(tmp_path / "weg.json"))
    uit = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA)}, _ctx(tmp_path))
    assert uit["ok"] is False and "onleesbaar" in uit["escalate"]["reason"]


def test_mislukte_scan_markeert_de_week_niet(tmp_path):
    """Fail-closed: een gefaalde run mag volgende puls opnieuw."""
    from nooch_village import safe_fetch
    from nooch_village.skills_impl import claims_site_scan as css

    def kapot(u):
        raise safe_fetch.FetchMislukt("stuk")
    ClaimsSiteScanSkill().run({"_fetch": kapot}, _ctx(tmp_path))
    assert not css.week_gedaan(str(tmp_path), css.period_key("week"))


def test_force_slaat_de_weekpoort_over(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA)}, ctx)
    tweede = ClaimsSiteScanSkill().run({"force": True, "_fetch": lambda u: (200, _PAGINA)}, ctx)
    assert tweede["skipped"] is False
    assert tweede["nieuw"] == 0                                   # alles loopt inmiddels


def test_scan_paginas_komen_uit_de_database():
    """Geen URL-lijst in code: de pagina-set is compliance-domein."""
    paginas = ClaimsSiteScanSkill() and __import__(
        "nooch_village.skills_impl.claims_site_scan", fromlist=["x"]).scan_paginas(claims_db.load())
    assert len(paginas) >= 5
    assert all(p["url"].startswith("https://nooch.earth") for p in paginas)
    with open(os.path.join(PKG, "skills_impl", "claims_site_scan.py"), encoding="utf-8") as f:
        assert "https://nooch.earth" not in f.read()


def test_skill_staat_in_de_registry():
    from nooch_village.registry_factory import build_skill_registry
    assert build_skill_registry().get("claims_site_scan") is not None


def test_claims_check_blijft_puur_lokaal():
    """v1-garantie: de lokale toets praat nooit buiten de deur; de fetch hoort in de scan-skill."""
    with open(os.path.join(PKG, "skills_impl", "claims_check.py"), encoding="utf-8") as f:
        bron = f.read()
    assert "requests" not in bron and "safe_fetch" not in bron


# ── De pulshaak: DNA-gated, geen eigen klasse nodig ─────────────────────────

def _inwoner(tmp_path, skills, resultaat):
    """Een generieke inwoner met de scan-skill in zijn DNA — precies zoals compliance
    materialiseert (geen CLASS_MAP-entry, dus geen eigen klasse)."""
    from nooch_village.event_bus import EventBus
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RecordType, RoleDefinition
    from nooch_village.skills import Skill

    class _Stub(Skill):
        name = "claims_site_scan"
        cost = "free"
        description = "stub"

        def run(self, payload, context=None):
            return resultaat

    from nooch_village.skills import SkillRegistry
    reg = SkillRegistry()
    reg.register(_Stub())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          records=None, projects=_ledger(tmp_path))
    rec = Record(id="compliance", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="claims bewaken", skills=list(skills)),
                 source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _meldingen(tmp_path) -> list[str]:
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    from nooch_village.notifications import NotifStore
    pad = os.path.join(str(tmp_path), "notifications.json")
    if not os.path.exists(pad):
        return []
    return [n.get("snippet", "") for n in NotifStore(pad).for_targets([("role", FOUNDER_ROLE_ID)])]


def test_zonder_grant_gebeurt_er_niets(tmp_path):
    """De DNA-grant is de poort: een rol zonder de skill scant niet."""
    inw = _inwoner(tmp_path, skills=[], resultaat={"ok": True, "nieuw": 3, "rood": 3})
    inw._run_pulse_skills(None)
    assert _meldingen(tmp_path) == []


def test_rode_bevindingen_geven_een_headsup_aan_de_founder(tmp_path):
    inw = _inwoner(tmp_path, skills=["claims_site_scan"],
                   resultaat={"ok": True, "skipped": False, "nieuw": 2, "rood": 1, "week": "2026-W29",
                              "headsup": "🔴 Claim-scan: 1 nieuwe verboden claim(s) op nooch.earth"})
    inw._run_pulse_skills(None)
    meldingen = _meldingen(tmp_path)
    assert len(meldingen) == 1
    assert "verboden claim" in meldingen[0]
    assert "approve" not in meldingen[0].lower()          # heads-up, geen beslisknop


def test_niets_nieuws_geeft_geen_bordruis(tmp_path):
    inw = _inwoner(tmp_path, skills=["claims_site_scan"],
                   resultaat={"ok": True, "skipped": False, "nieuw": 0, "gescand": 5,
                              "overgeslagen": 12, "week": "2026-W29"})
    inw._run_pulse_skills(None)
    assert _meldingen(tmp_path) == []                     # alleen een logregel


def test_escalatie_wordt_zichtbaar(tmp_path):
    inw = _inwoner(tmp_path, skills=["claims_site_scan"],
                   resultaat={"ok": False, "escalate": {"reason": "geen enkele pagina kon worden opgehaald"}})
    inw._run_pulse_skills(None)
    assert "kon niet draaien" in _meldingen(tmp_path)[0]


def test_al_gescand_deze_week_is_stil(tmp_path):
    inw = _inwoner(tmp_path, skills=["claims_site_scan"], resultaat={"ok": True, "skipped": True})
    inw._run_pulse_skills(None)
    assert _meldingen(tmp_path) == []
