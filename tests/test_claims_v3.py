"""Claims-checker v3: wetscheck, @rol-berichten, zichtbaar ritme en zelfverifiërende status.

De harde grenzen die hier bewaakt worden:
- `regulation_watch` DETECTEERT en duidt nooit; hij raakt de claims-database niet aan.
- een @rol-bericht aan een onbemande rol komt tóch bij een mens aan (Circle Lead-vangnet).
- een automatisch gezette status is altijd als automatisch herkenbaar.
- alles wat terugkeert leeft in de repo — geen externe scheduler.
"""
from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

import pytest

from nooch_village import claims_board, claims_db, claims_verify, role_rhythm
from nooch_village.projects import ProjectLedger
from nooch_village.skills_impl import regulation_watch as rw
from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill, markeer_week
from nooch_village.skills_impl.regulation_watch import RegulationWatchSkill

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nooch_village")

_BRONNEN = ("\nA | EU-richtlijn 2024/825 | https://eur-lex.europa.eu/x\n"
            "B | ACM Leidraad | https://www.acm.nl/y\n"
            "C | NL-omzetting EmpCo — PROXY (tracker) | https://www.internetconsultatie.nl/\n")


def _ctx(tmp_path, bronnen=_BRONNEN):
    return SimpleNamespace(data_dir=str(tmp_path), settings={"regulation_sources": bronnen},
                           projects=ProjectLedger(str(tmp_path / "p.json")), records=None)


def _fetch(inhoud: str, ctype: str = "text/html"):
    return lambda url: (200, f"<html><body>{inhoud}</body></html>".encode(), ctype)


# ── Taak 1: de wetscheck ────────────────────────────────────────────────────

def test_bronnen_parsen_uit_settings():
    bronnen = rw.parse_bronnen({"regulation_sources": _BRONNEN})
    assert [b["letter"] for b in bronnen] == ["A", "B", "C"]
    assert bronnen[2]["proxy"] is True                    # PROXY-label herkend
    assert bronnen[0]["proxy"] is False


def test_kapotte_regel_laat_de_rest_staan():
    bronnen = rw.parse_bronnen({"regulation_sources": "onzin\nA | Goed | https://x.nl\n| |"})
    assert len(bronnen) == 1


def test_hash_negeert_opmaak_maar_niet_inhoud():
    """Andere witruimte is geen wetswijziging; een ander woord wel."""
    a = rw.hash_van(b"<html><body>De   wet\n\nzegt X</body></html>", "text/html")
    b = rw.hash_van(b"<html><body>De wet zegt X</body></html>", "text/html")
    c = rw.hash_van(b"<html><body>De wet zegt Y</body></html>", "text/html")
    assert a == b
    assert a != c


def test_pdf_hasht_op_bytes():
    """Een PDF door de HTML-stripper halen geeft ruis; op bytes is stabiel."""
    ruw = b"%PDF-1.4 binaire troep \x00\x01"
    assert rw.hash_van(ruw, "application/pdf") == rw.hash_van(ruw, "application/pdf")
    assert rw.hash_van(ruw, "application/pdf") != rw.hash_van(ruw + b"x", "application/pdf")


def test_eerste_run_is_nulmeting_zonder_alarm(tmp_path):
    ctx = _ctx(tmp_path)
    uit = RegulationWatchSkill().run({"_fetch": _fetch("wettekst")}, ctx)
    assert uit["ok"] and uit["gewijzigd"] == []
    assert uit["nieuw"] == 0                              # nulmeting is geen nieuws
    assert len(rw.lees_log(str(tmp_path))) == 3
    assert ctx.projects.all() == []


def test_gewijzigde_bron_wordt_taak_en_headsup(tmp_path):
    ctx = _ctx(tmp_path)
    RegulationWatchSkill().run({"_fetch": _fetch("oude wettekst")}, ctx)
    uit = RegulationWatchSkill().run({"force": True, "_fetch": _fetch("NIEUWE wettekst")}, ctx)
    assert len(uit["gewijzigd"]) == 3
    # De proxy-bron levert bewust geen taak: die pagina verandert om andere redenen.
    assert uit["nieuw"] == 2
    assert "gewijzigd" in uit["headsup"].lower() or "wetscheck" in uit["headsup"].lower()
    titels = [p["scope"] for p in ctx.projects.all()]
    assert all(t.startswith("📜 Bron gewijzigd") for t in titels)
    assert all(p["owner"] == "compliance" for p in ctx.projects.all())


def test_proxybron_maakt_geen_taak(tmp_path):
    ctx = _ctx(tmp_path, bronnen="C | NL-omzetting EmpCo — PROXY | https://www.internetconsultatie.nl/\n")
    RegulationWatchSkill().run({"_fetch": _fetch("a")}, ctx)
    uit = RegulationWatchSkill().run({"force": True, "_fetch": _fetch("b")}, ctx)
    assert len(uit["gewijzigd"]) == 1 and uit["nieuw"] == 0
    assert ctx.projects.all() == []


def test_dedupe_zolang_de_taak_open_staat(tmp_path):
    ctx = _ctx(tmp_path, bronnen="A | Wet | https://eur-lex.europa.eu/x\n")
    RegulationWatchSkill().run({"_fetch": _fetch("v1")}, ctx)
    RegulationWatchSkill().run({"force": True, "_fetch": _fetch("v2")}, ctx)
    RegulationWatchSkill().run({"force": True, "_fetch": _fetch("v3")}, ctx)
    assert len(ctx.projects.all()) == 1                   # geen stapel duplicaten


def test_maand_idempotent(tmp_path):
    ctx = _ctx(tmp_path)
    RegulationWatchSkill().run({"_fetch": _fetch("x")}, ctx)
    tweede = RegulationWatchSkill().run({"_fetch": _fetch("x")}, ctx)
    assert tweede["skipped"] is True


def test_een_misser_is_geen_alarm_twee_wel(tmp_path):
    from nooch_village import safe_fetch

    def kapot(url):
        raise safe_fetch.FetchMislukt("timeout")
    ctx = _ctx(tmp_path, bronnen="A | Wet | https://eur-lex.europa.eu/x\n")
    eerste = RegulationWatchSkill().run({"_fetch": kapot}, ctx)
    assert eerste["escalate"]["reason"].startswith("geen enkele bron")   # alles stuk deze run
    tweede = RegulationWatchSkill().run({"force": True, "_fetch": kapot}, ctx)
    assert "twee maanden achtereen" in tweede["escalate"]["reason"]


def test_zonder_bronnen_escaleert(tmp_path):
    uit = RegulationWatchSkill().run({}, _ctx(tmp_path, bronnen=""))
    assert uit["ok"] is False and "regulation_sources" in uit["escalate"]["reason"]


def test_mijlpaal_handhaving_eenmalig(tmp_path, monkeypatch):
    monkeypatch.setattr(rw, "HANDHAVING_MAAND", "2000-01")   # altijd bereikt
    ctx = _ctx(tmp_path, bronnen="A | Wet | https://eur-lex.europa.eu/x\n")
    eerste = RegulationWatchSkill().run({"_fetch": _fetch("x")}, ctx)
    assert any("EmpCo-handhaving" in t["titel"] for t in eerste["aangemaakt"])
    tweede = RegulationWatchSkill().run({"force": True, "_fetch": _fetch("x")}, ctx)
    assert not any("EmpCo-handhaving" in t["titel"] for t in tweede["aangemaakt"])


def test_mijlpaal_nl_omzetting_bij_echte_bron(tmp_path):
    """Zolang de bron een PROXY is bestaat de wettekst niet. Vult compliance de echte bron in
    (label zonder PROXY), dan is dát het moment om hem naast de database te leggen."""
    proxy = _ctx(tmp_path, bronnen="C | NL-omzetting EmpCo — PROXY | https://www.acm.nl/p\n")
    uit = RegulationWatchSkill().run({"_fetch": _fetch("x")}, proxy)
    assert not any("NL-wettekst" in t["titel"] for t in uit["aangemaakt"])

    echt = _ctx(tmp_path, bronnen="A | NL-omzetting EmpCo (Stb. 2026) | https://www.acm.nl/wet\n")
    echt.projects = proxy.projects
    uit2 = RegulationWatchSkill().run({"force": True, "_fetch": _fetch("x")}, echt)
    assert any("NL-wettekst" in t["titel"] for t in uit2["aangemaakt"])


def test_wetscheck_raakt_de_claims_database_nooit_aan(tmp_path):
    """De harde grens: detecteren mag, muteren niet. Dit is compliance-domein."""
    voor = open(claims_db.DB_PATH, encoding="utf-8").read()
    ctx = _ctx(tmp_path)
    RegulationWatchSkill().run({"force": True, "_fetch": _fetch("heel andere wettekst")}, ctx)
    assert open(claims_db.DB_PATH, encoding="utf-8").read() == voor


def test_wetscheck_bevat_geen_llm_en_geen_duiding():
    """Geen model dat de wijziging 'even samenvat': dat zou duiding zijn, en duiding is
    compliance-werk. Alleen de docstring mag het woord LLM noemen (om dit uit te leggen)."""
    with open(os.path.join(PKG, "skills_impl", "regulation_watch.py"), encoding="utf-8") as f:
        code = "\n".join(r for r in f.read().splitlines()
                         if not r.lstrip().startswith("#"))
    for verboden in ("from nooch_village.llm", "import llm", "use_skill(", "claims_db.save",
                     "add_term", "set_werk_status"):
        assert verboden not in code, f"regulation_watch mag niet {verboden} gebruiken"


def test_log_is_append_only(tmp_path):
    ctx = _ctx(tmp_path, bronnen="A | Wet | https://www.acm.nl/x\n")
    RegulationWatchSkill().run({"_fetch": _fetch("a")}, ctx)
    RegulationWatchSkill().run({"force": True, "_fetch": _fetch("b")}, ctx)
    rijen = rw.lees_log(str(tmp_path))
    assert len(rijen) == 2                                # de eerste meting blijft staan
    assert rijen[0]["hash"] != rijen[1]["hash"]


def test_kapotte_logregel_gooit_de_geschiedenis_niet_weg(tmp_path):
    pad = tmp_path / rw.LOGBESTAND
    pad.write_text('{"soort":"meting","url":"a","status":"ok","hash":"1"}\nkapot\n'
                   '{"soort":"meting","url":"a","status":"ok","hash":"2"}\n', encoding="utf-8")
    assert len(rw.lees_log(str(tmp_path))) == 2


# ── Taak 2: zichtbaar ritme ─────────────────────────────────────────────────

def _rec(skills):
    return SimpleNamespace(id="compliance", definition=SimpleNamespace(skills=skills))


def test_rol_zonder_ritme_toont_niets(tmp_path):
    assert role_rhythm.ritmes_voor("x", _rec(["claim_evidence"]), str(tmp_path)) == []


def test_ritme_toont_verse_run(tmp_path):
    from nooch_village.checklists import period_key
    markeer_week(str(tmp_path), period_key("week"),
                 {"nieuw": 2, "overgeslagen": 35, "gescand": 5, "statussen": 0})
    r = role_rhythm.ritmes_voor("compliance", _rec(["claims_site_scan"]), str(tmp_path))[0]
    assert r["overtijd"] is False
    assert "laatste run" in r["laatst"]
    assert "2 nieuwe" in r["uitkomst"]


def test_ritme_waarschuwt_bij_overtijd(tmp_path):
    """Een oude datum die er netjes uitziet wekt vertrouwen dat er niet is."""
    markeer_week(str(tmp_path), "2026-W02", {"nieuw": 0, "gescand": 5})
    r = role_rhythm.ritmes_voor("compliance", _rec(["claims_site_scan"]), str(tmp_path))[0]
    assert r["overtijd"] is True
    assert "niet gedraaid" in r["overtijd_tekst"]


def test_ritme_zonder_run_belooft_niets(tmp_path):
    r = role_rhythm.ritmes_voor("compliance", _rec(["claims_site_scan"]), str(tmp_path))[0]
    assert r["laatst"] == "" and r["overtijd"] is False
    assert "eerstvolgende" in r["uitkomst"]


def test_wetscheck_ritme_leest_de_meetreeks(tmp_path):
    ctx = _ctx(tmp_path)
    RegulationWatchSkill().run({"_fetch": _fetch("x")}, ctx)
    r = role_rhythm.ritmes_voor("compliance", _rec(["regulation_watch"]), str(tmp_path))[0]
    assert "ongewijzigd" in r["uitkomst"]
    assert r["overtijd"] is False


def test_rolpagina_toont_het_blok(tmp_path):
    from nooch_village.views.overview import _ritme_html
    from nooch_village.checklists import period_key
    markeer_week(str(tmp_path), period_key("week"), {"nieuw": 0, "gescand": 5, "overgeslagen": 12})
    html = _ritme_html(SimpleNamespace(dd=str(tmp_path)), _rec(["claims_site_scan"]))
    assert "Terugkerend ritme" in html and "Wekelijkse site-scan" in html
    assert "style=" not in html


# ── Taak 3: @rol-berichten ──────────────────────────────────────────────────

class _Assign:
    """Assignments-dubbel: rol → lijst fillers."""
    def __init__(self, mapping):
        self._m = mapping

    def fillers_of(self, rid, record=None):
        return self._m.get(rid, [])


def _omg(tmp_path, fillers=None, ouder="cirkel"):
    class _Records:
        def get(self, rid):
            return SimpleNamespace(id=rid, parent=ouder)
    return SimpleNamespace(projects=ProjectLedger(str(tmp_path / "p.json")),
                           records=_Records(), assign=_Assign(fillers or {}),
                           data_dir=str(tmp_path))


def _notifs(tmp_path):
    from nooch_village.notifications import NotifStore
    return NotifStore(str(tmp_path / "notifications.json")).all()


def test_bericht_aan_bemande_rol_gaat_alleen_daarheen(tmp_path):
    omg = _omg(tmp_path, {"rolx": [SimpleNamespace(type="person", id="p1")]})
    doelen = claims_board.bericht_aan_rol(omg, "rolx", "er is iets gevonden")
    assert doelen == ["rolx"]
    assert len(_notifs(tmp_path)) == 1


def test_onbemande_rol_bereikt_toch_de_circle_lead(tmp_path):
    """compliance heeft geen mens; zonder vangnet komt het bericht bij niemand aan."""
    omg = _omg(tmp_path, {})
    doelen = claims_board.bericht_aan_rol(omg, "compliance", "er is iets gevonden")
    assert doelen == ["compliance", "cirkel__circle_lead"]
    snippets = [n["snippet"] for n in _notifs(tmp_path)]
    assert any("onbemand" in s for s in snippets)


def test_persona_telt_niet_als_mens(tmp_path):
    """Een rol die alleen een AI-persona draagt heeft geen menselijke ontvanger."""
    omg = _omg(tmp_path, {"rolx": [SimpleNamespace(type="persona", id="a1")]})
    doelen = claims_board.bericht_aan_rol(omg, "rolx", "x")
    assert "cirkel__circle_lead" in doelen


def test_bericht_faalt_zacht(tmp_path):
    """Berichten mogen een puls of een klik nooit laten klappen."""
    assert claims_board.bericht_aan_rol(SimpleNamespace(), "rolx", "x") in ([], ["rolx"])


def test_taak_gaat_vergezeld_van_een_bericht(tmp_path):
    from nooch_village.views.claims import rol_voor
    omg = _omg(tmp_path)
    bev = {"term": "gifvrij", "gevonden": ["volstrekt gifvrij"], "stoplicht": "red",
           "categorie": "Statistiek", "waarom": "x", "alternatief": "y"}
    verslag = claims_board.zet_op_bord(omg, claims_db.load(), [bev], "bron", rol_voor)
    assert len(verslag["aangemaakt"]) == 1
    assert verslag["aangemaakt"][0]["doelen"]              # er is iemand bereikt
    assert _notifs(tmp_path)


def test_terugkoppeling_noemt_de_rollen(tmp_path):
    from nooch_village import cockpit2
    verslag = {"aangemaakt": [{"owner": "a__copywriter", "stoplicht": "red", "pid": "1", "titel": "t"},
                              {"owner": "a__copywriter", "stoplicht": "orange", "pid": "2", "titel": "t"},
                              {"owner": "compliance", "stoplicht": "red", "pid": "3", "titel": "t"}],
               "overgeslagen": 4, "lopend": []}
    melding = cockpit2._bord_melding(verslag)
    assert "3 taak/taken" in melding
    assert "@copywriter (2)" in melding and "@compliance (1)" in melding
    assert "4 liepen al" in melding


def test_terugkoppeling_bij_nul_is_niet_stil(tmp_path):
    from nooch_village import cockpit2
    melding = cockpit2._bord_melding({"aangemaakt": [], "overgeslagen": 4, "lopend": []})
    assert "0 nieuw" in melding and "al als taak" in melding


def test_bordresultaat_toont_links():
    from nooch_village.views.claims import render_bordresultaat
    html = render_bordresultaat({"aangemaakt": [{"pid": "abc", "owner": "x__copywriter",
                                                 "titel": "🔴 Vervang: zero waste"}],
                                 "lopend": [], "overgeslagen": 0})
    assert "/project?pid=abc" in html and "@copywriter" in html
    assert "style=" not in html


def test_bordresultaat_bij_nul_toont_waar_het_al_ligt():
    from nooch_village.views.claims import render_bordresultaat
    html = render_bordresultaat({"aangemaakt": [], "overgeslagen": 2,
                                 "lopend": [{"soort": "werklijst", "nr": 1, "titel": "planet-safe"},
                                            {"soort": "taak", "pid": "p9", "titel": "oude taak"}]})
    assert "0 nieuw" in html
    assert "/claims?tab=werklijst" in html and "/project?pid=p9" in html


# ── Taak 4: zelfverifiërende werklijst-status ───────────────────────────────

def _db_met(werklijst):
    db = claims_db.load()
    db["werklijst"] = werklijst
    return db


def test_verdwenen_claim_wordt_auto_opgelost():
    db = _db_met([{"nr": 13, "claim": "“PLANET-FRIENDLY.” — productpagina", "oordeel": "red",
                   "herformulering": "-", "status": "open"}])
    v = claims_verify.verifieer(db, {"product": "Onze schoenen zijn gemaakt van planten."})
    assert len(v) == 1
    assert v[0]["naar"].startswith("opgelost (auto-geverifieerd")
    assert v[0]["nr"] == 13


def test_teruggekeerde_claim_is_een_regressie():
    db = _db_met([{"nr": 13, "claim": "“PLANET-FRIENDLY.” — productpagina", "oordeel": "red",
                   "herformulering": "-", "status": "live"}])
    v = claims_verify.verifieer(db, {"product": "PLANET-FRIENDLY. schoenen"})
    assert v[0]["naar"] == claims_db.AUTO_REGRESSIE


def test_claim_die_er_nog_staat_verandert_niets():
    db = _db_met([{"nr": 13, "claim": "“PLANET-FRIENDLY.” — productpagina", "oordeel": "red",
                   "herformulering": "-", "status": "open"}])
    assert claims_verify.verifieer(db, {"product": "PLANET-FRIENDLY. schoenen"}) == []


def test_pagina_buiten_de_scanset_is_niet_verifieerbaar():
    """Geen status die betrouwbaarheid suggereert waar we niets zagen."""
    db = _db_met([{"nr": 99, "claim": "“zero waste” — nieuwsbrief", "oordeel": "red",
                   "herformulering": "-", "status": "open"}])
    v = claims_verify.verifieer(db, {"home": "schone tekst"})
    assert v[0]["naar"] == claims_db.NIET_VERIFIEERBAAR
    assert "buiten de vaste scan-set" in v[0]["reden"]


def test_item_zonder_citeerbare_frase_is_niet_verifieerbaar():
    db = _db_met([{"nr": 5, "claim": "PETA-logo in de footer", "oordeel": "orange",
                   "herformulering": "-", "status": "open"}])
    v = claims_verify.verifieer(db, {"home": "x"})
    assert v[0]["naar"] == claims_db.NIET_VERIFIEERBAAR


def test_handmatige_opgelost_wordt_niet_herbevestigd():
    """De scan overschrijft een mens-oordeel alleen als hij het tegendeel wáárneemt."""
    db = _db_met([{"nr": 1, "claim": "“planet-safe” — homepage", "oordeel": "red",
                   "herformulering": "-", "status": "live"}])
    assert claims_verify.verifieer(db, {"home": "schone tekst"}) == []


def test_automatische_status_is_als_zodanig_gelabeld():
    db = _db_met([{"nr": 13, "claim": "“PLANET-FRIENDLY.” — productpagina", "oordeel": "red",
                   "herformulering": "-", "status": "open"}])
    v = claims_verify.verifieer(db, {"product": "schone tekst"})
    claims_verify.pas_toe(db, v)
    item = db["werklijst"][0]
    assert item["status_bron"] == "auto"
    assert claims_db.is_auto(item["status"])
    assert not claims_db.is_auto("live")                   # mens-oordeel blijft onderscheidbaar


def test_scan_werkt_de_status_bij_en_meldt_regressie(tmp_path, monkeypatch):
    """Volledige doorloop: de wekelijkse scan verifieert, schrijft en bericht."""
    pad = tmp_path / "db.json"
    db = claims_db.load()
    db["werklijst"] = [{"nr": 13, "claim": "“PLANET-FRIENDLY.” — productpagina", "oordeel": "red",
                        "herformulering": "-", "status": "live"}]
    pad.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(claims_db, "DB_PATH", str(pad))
    ctx = _omg(tmp_path)
    ctx.settings = {}
    pagina = "<html><body>PLANET-FRIENDLY. sneakers</body></html>"
    uit = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, pagina)}, ctx)
    assert any(s["naar"] == claims_db.AUTO_REGRESSIE for s in uit["statussen"])
    assert claims_db.load(str(pad))["werklijst"][0]["status"] == claims_db.AUTO_REGRESSIE
    assert "regressie" in uit["headsup"].lower()
    assert any("Werklijst #13" in n["snippet"] for n in _notifs(tmp_path))


# ── Productprincipe: alles leeft in de repo ─────────────────────────────────

def test_beide_skills_lopen_via_de_pulslaag():
    """Geen externe scheduler: wat terugkeert, keert terug via pulse_skills."""
    from nooch_village.inhabitant import Inhabitant
    inw = Inhabitant.__new__(Inhabitant)
    inw.context = SimpleNamespace(settings={"pulse_skills": "claims_site_scan,regulation_watch"})
    assert inw._periodieke_skills() == ["claims_site_scan", "regulation_watch"]


def test_skills_staan_in_de_registry():
    from nooch_village.registry_factory import build_skill_registry
    reg = build_skill_registry()
    for naam in ("claims_check", "claims_site_scan", "regulation_watch"):
        assert reg.get(naam) is not None
