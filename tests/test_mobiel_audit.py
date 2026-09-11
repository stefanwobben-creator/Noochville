"""mobiel_audit — een echte Lighthouse-run op mobiel via PageSpeed Insights, en dezelfde meting als
wekelijkse meetbron.

Aanleiding (11 september 2026): het mobiel-project zat vast op "○ no skill" voor een audit van
Core Web Vitals / Lighthouse op mobiel; Stefan wil de skill voor nooch.earth (de preview-versie) en
"wekelijks of dagelijks een soort QA-check". Alles hier draait zonder netwerk: de fetch is
geïnjecteerd met een klein maar echt-gevormd PSI-antwoord.
"""
from __future__ import annotations

import datetime
import types

from nooch_village import cockpit2
from nooch_village.collector import collect_daily_observations
from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.mobiel_audit import MobielAuditSkill, _METRICS

URL = "https://nooch.earth/"


def _psi(*, met_veld: bool = True, origin_fallback: bool = False) -> dict:
    """De vorm van Google's antwoord, ingekort tot wat de skill leest."""
    audits = {
        "largest-contentful-paint": {"score": 0.55, "numericValue": 3210.4, "displayValue": "3.2 s"},
        "cumulative-layout-shift": {"score": 0.98, "numericValue": 0.021, "displayValue": "0.021"},
        "total-blocking-time": {"score": 0.7, "numericValue": 210, "displayValue": "210 ms"},
        "first-contentful-paint": {"score": 0.8, "numericValue": 1800, "displayValue": "1.8 s"},
        "speed-index": {"score": 0.6, "numericValue": 4100, "displayValue": "4.1 s"},
        "interactive": {"score": 0.5, "numericValue": 6200, "displayValue": "6.2 s"},
        "render-blocking-resources": {"score": 0.3, "title": "Eliminate render-blocking resources",
                                      "details": {"type": "opportunity", "overallSavingsMs": 450}},
        "uses-responsive-images": {"score": 0.5, "title": "Properly size images",
                                   "details": {"type": "opportunity", "overallSavingsMs": 900,
                                               "overallSavingsBytes": 420000}},
        "unused-css-rules": {"score": 1, "title": "Reduce unused CSS",
                             "details": {"type": "opportunity", "overallSavingsMs": 0}},
        "viewport": {"score": 1, "title": "Has a viewport meta tag", "scoreDisplayMode": "binary"},
        "tap-targets": {"score": 0.4, "title": "Tap targets are not sized appropriately",
                        "displayValue": "62% appropriately sized tap targets", "scoreDisplayMode": "binary"},
        "font-size": {"score": None, "scoreDisplayMode": "notApplicable", "title": "Font sizes"},
        "errors-in-console": {"score": 0, "title": "Browser errors were logged to the console",
                              "scoreDisplayMode": "binary", "displayValue": ""},
        "third-party-cookies": {"score": 0, "title": "Uses third-party cookies", "displayValue": "3 cookies found",
                                "scoreDisplayMode": "binary"},
        "lcp-lazy-loaded": {"score": 0, "title": "Largest Contentful Paint image was lazily loaded",
                            "scoreDisplayMode": "binary"},
        "largest-contentful-paint-element": {"score": 0, "scoreDisplayMode": "informative",
            "title": "Largest Contentful Paint element", "displayValue": "20,300 ms",
            "details": {"type": "list", "items": [
                {"type": "table", "items": [{"node": {"type": "node", "selector": "div.hero > img",
                                                      "nodeLabel": "Nooch 269 in het gras", "snippet": "<img src=\"hero.jpg\">"}}]},
                {"type": "table", "items": [{"phase": "TTFB", "timing": 400}, {"phase": "Load Delay", "timing": 15200},
                                            {"phase": "Load Time", "timing": 3900}, {"phase": "Render Delay", "timing": 800}]}]}},
    }
    refs = {
        "performance": [{"id": "largest-contentful-paint", "weight": 25}, {"id": "render-blocking-resources", "weight": 0},
                        {"id": "lcp-lazy-loaded", "weight": 0}, {"id": "largest-contentful-paint-element", "weight": 0},
                        {"id": "uses-responsive-images", "weight": 0}, {"id": "cumulative-layout-shift", "weight": 25}],
        "accessibility": [{"id": "target-size", "weight": 7}],
        "best-practices": [{"id": "errors-in-console", "weight": 1}, {"id": "third-party-cookies", "weight": 5}],
        "seo": [{"id": "viewport", "weight": 1}],
    }
    data = {
        "lighthouseResult": {
            "finalDisplayedUrl": URL, "lighthouseVersion": "12.6.0", "fetchTime": "2026-09-11T09:00:00.000Z",
            "categories": {"performance": {"score": 0.72, "auditRefs": refs["performance"]},
                           "accessibility": {"score": 0.95, "auditRefs": refs["accessibility"]},
                           "best-practices": {"score": 1.0, "auditRefs": refs["best-practices"]},
                           "seo": {"score": 0.92, "auditRefs": refs["seo"]}},
            "audits": audits, "runWarnings": ["The page loaded too slowly to finish within the time limit."],
        },
    }
    if met_veld:
        data["loadingExperience"] = {
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2600, "category": "AVERAGE"},
                        "INTERACTION_TO_NEXT_PAINT": {"percentile": 150, "category": "FAST"},
                        "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5, "category": "FAST"},
                        "FIRST_CONTENTFUL_PAINT_MS": {"percentile": 1900, "category": "AVERAGE"}},
            "overall_category": "AVERAGE",
        }
        if origin_fallback:
            data["loadingExperience"]["origin_fallback"] = True
    return data


def _skill(antwoord=None, status=200, exc=None):
    gezien = []

    def haal(params):
        gezien.append(dict(params))
        if exc:
            raise exc
        return status, antwoord

    s = MobielAuditSkill(haal=haal, controleer=lambda u: u)
    s._gezien = gezien
    return s


KEY = "test-key-123"


def _ctx(**settings):
    """Een context mét key, tenzij de test hem expliciet weglaat: zonder key draait de skill niet
    (gemeten op 11 september: keyless = 429 bij de eerste aanroep)."""
    settings.setdefault("PAGESPEED_API_KEY", KEY)
    return types.SimpleNamespace(settings={k: v for k, v in settings.items() if v is not None})


# ── contract ─────────────────────────────────────────────────────────────────

def test_metadata_en_contract():
    s = MobielAuditSkill()
    assert s.name == "mobiel_audit" and s.SOURCE == "mobiel_audit"
    assert s.cost == "rate_limited" and s.side_effect_free is True
    assert s.required_env == ("PAGESPEED_API_KEY",), "keyless deelt een uitgeput anoniem quotum"
    assert not s.is_configured(_ctx(PAGESPEED_API_KEY=None)) and s.is_configured(_ctx())
    assert set(s.available_metrics()) == set(_METRICS) and len(_METRICS) == 7
    assert s.DEFAULT_FREQUENCY == "weekly"


# ── op afroep ────────────────────────────────────────────────────────────────

def test_run_parst_scores_lab_veld_kansen_en_mobiel():
    s = _skill(_psi())
    r = s.run({"url": URL}, _ctx())
    assert r["ok"] and r["strategie"] == "mobile" and r["lighthouse_versie"] == "12.6.0"
    assert r["scores"] == {"performance": 72, "accessibility": 95, "best_practices": 100, "seo": 92}
    assert r["lab"]["lcp_ms"]["waarde"] == 3210.4 and r["lab"]["lcp_ms"]["weergave"] == "3.2 s"
    assert r["lab"]["cls"]["waarde"] == 0.021
    assert r["veld"]["bron"] == "url" and r["veld"]["oordeel"] == "AVERAGE"
    assert r["veld"]["veld_lcp_ms"] == 2600 and r["veld"]["veld_inp_ms"] == 150
    assert r["veld"]["veld_cls"] == 0.05, "CLS komt uit de API als percentiel ×100"
    assert [k["audit"] for k in r["kansen"]] == ["uses-responsive-images", "render-blocking-resources"], \
        "gesorteerd op winst; een kans zonder geschatte winst is een bevinding, geen kans"
    assert r["kansen"][0]["winst_ms"] == 900 and r["kansen"][0]["winst_bytes"] == 420000
    mobiel = {m["audit"]: m for m in r["mobiel"]}
    assert mobiel["viewport"]["geslaagd"] is True and mobiel["tap-targets"]["geslaagd"] is False
    assert "font-size" not in mobiel, "notApplicable is geen oordeel"
    assert r["waarschuwingen"] and "duur_s" in r
    assert "performance 72" in r["text"] and "Tap targets" in r["text"] and "Veld (url, p75)" in r["text"]
    # de bevindingen: falende audits per categorie, zwaarste eerst; metrics en informatieve audits niet
    bev = [(b["categorie"], b["audit"]) for b in r["bevindingen"]]
    assert bev == [("performance", "lcp-lazy-loaded"), ("performance", "render-blocking-resources"),
                   ("performance", "uses-responsive-images"),          # gelijk gewicht → slechtste score eerst
                   ("best_practices", "third-party-cookies"), ("best_practices", "errors-in-console")], bev
    assert all(b["audit"] not in ("largest-contentful-paint", "largest-contentful-paint-element") for b in r["bevindingen"])
    # het LCP-element met zijn fases: het antwoord op 'waarom zo traag'
    le = r["lcp_element"]
    assert le["element"] == "Nooch 269 in het gras" and le["selector"] == "div.hero > img"
    assert le["fases_ms"] == {"TTFB": 400, "Load Delay": 15200, "Load Time": 3900, "Render Delay": 800}
    assert "LCP-element: Nooch 269 in het gras (meeste tijd: Load Delay)" in r["text"]
    assert "Falende audits: performance 3, best_practices 2" in r["text"]
    # de aanvraag: mobiel, alle vier categorieën, de key als parameter en nergens in de uitvoer
    p = s._gezien[0]
    assert p["url"] == URL and p["strategy"] == "mobile" and p["key"] == KEY
    assert KEY not in repr(r)
    assert set(p["category"]) == {"performance", "accessibility", "best-practices", "seo"}


def test_url_default_uit_settings_en_key_gaat_mee_maar_nooit_terug():
    s = _skill(_psi())
    r = s.run({}, _ctx(mobiel_audit_url="https://nooch.earth/?preview_theme_id=1234",
                       PAGESPEED_API_KEY="geheim-123"))
    assert r["ok"]
    assert s._gezien[0]["url"] == "https://nooch.earth/?preview_theme_id=1234"
    assert s._gezien[0]["key"] == "geheim-123"
    assert "geheim-123" not in repr(r)


def test_zonder_velddata_is_dat_een_feit_geen_fout():
    r = _skill(_psi(met_veld=False)).run({"url": URL}, _ctx())
    assert r["ok"] and r["veld"]["bron"] is None and "te weinig Chrome-verkeer" in r["veld"]["reden"]
    assert "Veld: geen velddata" in r["text"]


def test_origin_fallback_wordt_als_origin_gemeld():
    r = _skill(_psi(origin_fallback=True)).run({"url": URL}, _ctx())
    assert r["veld"]["bron"] == "origin"


def test_desktop_mag_onbekende_strategie_niet():
    s = _skill(_psi())
    assert s.run({"url": URL, "strategie": "desktop"}, _ctx())["strategie"] == "desktop"
    assert s._gezien[-1]["strategy"] == "desktop"
    r = s.run({"url": URL, "strategie": "tablet"}, _ctx())
    assert "error" in r and r["tijdelijk"] is False


# ── fail-closed ──────────────────────────────────────────────────────────────

def test_google_fout_is_een_error_met_googles_reden():
    r = _skill({"error": {"code": 500, "message": "Lighthouse returned error: FAILED_DOCUMENT_REQUEST. "
                                                   "Lighthouse was unable to reliably load the page."}},
               status=500).run({"url": URL}, _ctx())
    assert "error" in r and "FAILED_DOCUMENT_REQUEST" in r["error"] and r["tijdelijk"] is False
    assert "scores" not in r


def test_quota_en_storing_zijn_tijdelijk():
    r = _skill({"error": {"code": 429, "message": "Quota exceeded"}}, status=429).run({"url": URL}, _ctx())
    assert r["tijdelijk"] is True
    r2 = _skill(None, status=503).run({"url": URL}, _ctx())
    assert "error" in r2 and r2["tijdelijk"] is True


def test_runtime_error_van_lighthouse_en_leeg_antwoord():
    kapot = _psi()
    kapot["lighthouseResult"]["runtimeError"] = {"code": "ERRORED_DOCUMENT_REQUEST", "message": "404"}
    r = _skill(kapot).run({"url": URL}, _ctx())
    assert "error" in r and "ERRORED_DOCUMENT_REQUEST" in r["error"]
    r2 = _skill({"lighthouseResult": {}}).run({"url": URL}, _ctx())
    assert "error" in r2 and r2["tijdelijk"] is True


def test_netwerkfout_verbergt_de_key():
    s = _skill(exc=ConnectionError("Max retries exceeded with url: /runPagespeed?url=x&key=geheim-123"))
    r = s.run({"url": URL}, _ctx(PAGESPEED_API_KEY="geheim-123"))
    assert "error" in r and r["tijdelijk"] is True
    assert "geheim-123" not in r["error"] and "***" in r["error"]


def test_zonder_key_draait_de_skill_niet_en_zegt_waarom():
    s = _skill(_psi())
    r = s.run({"url": URL}, _ctx(PAGESPEED_API_KEY=None))
    assert "error" in r and "PAGESPEED_API_KEY" in r["error"] and r["tijdelijk"] is False
    assert s._gezien == [], "geen aanroep zonder key: die zou alleen een 429 delen"
    v = s.daily_values(_ctx(PAGESPEED_API_KEY=None), "2026-09-08")
    assert all(x is None for x in v.values())


def test_geweigerde_url_en_plaatshouder():
    from nooch_village import safe_fetch

    def weiger(u):
        raise safe_fetch.FetchGeweigerd("interne adressen worden niet gescand")
    s = MobielAuditSkill(haal=lambda p: (200, _psi()), controleer=weiger)
    r = s.run({"url": "http://10.0.0.1/"}, _ctx())
    assert "error" in r and "geweigerd" in r["error"] and r["tijdelijk"] is False
    assert MobielAuditSkill().validate_payload({"url": "PLACEHOLDER — de URL uit stap 1"}, None)
    assert MobielAuditSkill().validate_payload({"url": URL}, None) == []
    assert MobielAuditSkill().validate_payload({}, None) == []


# ── als meetbron ─────────────────────────────────────────────────────────────

def test_daily_values_levert_de_zeven_velden_of_none():
    s = _skill(_psi())
    v = s.daily_values(_ctx(), "2026-09-08")
    assert v == {"performance": 72, "lcp_ms": 3210.4, "cls": 0.021, "tbt_ms": 210,
                 "veld_lcp_ms": 2600, "veld_inp_ms": 150, "veld_cls": 0.05}
    meta = s.observation_meta(_ctx(), "2026-09-08", "performance")
    assert meta["lighthouse"] == "12.6.0" and meta["veld_bron"] == "url" and meta["url"] == URL
    # zonder velddata: de veld-velden None, de rest gewoon gevuld
    v2 = _skill(_psi(met_veld=False)).daily_values(_ctx(), "2026-09-08")
    assert v2["performance"] == 72 and v2["veld_lcp_ms"] is None
    # Google plat: alles None, geen exception (fail-closed per veld)
    v3 = _skill({"error": {"message": "boem"}}, status=500).daily_values(_ctx(), "2026-09-08")
    assert set(v3) == set(_METRICS) and all(x is None for x in v3.values())


def test_frequentie_uit_settings_valt_terug_op_wekelijks():
    s = MobielAuditSkill(haal=lambda p: (200, _psi()), controleer=lambda u: u)
    assert s.frequency("performance") == "weekly"
    s.is_configured(_ctx(mobiel_audit_frequency="daily"))
    assert s.frequency("performance") == "daily"
    s.is_configured(_ctx(mobiel_audit_frequency="elk-uur"))
    assert s.frequency("performance") == "weekly"


def test_collector_schrijft_wekelijks_een_punt_per_veld(tmp_path):
    """De bestaande collector neemt de bron mee zodra hij actief staat: één meting per week, gelabeld
    op de maandag, idempotent. Zonder activatie schrijft hij niets (mens-gated, zoals Shopify/GSC)."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    reg = SkillRegistry()
    reg.register(_skill(_psi(met_veld=False)))
    st = cockpit2._Stores(dd)
    today = datetime.date(2026, 9, 11)                      # een donderdag
    assert collect_daily_observations(reg, st.sources, st.observations, _ctx(), today=today) == []
    st.sources.set_active("mobiel_audit", True)
    st = cockpit2._Stores(dd)
    assert collect_daily_observations(reg, st.sources, st.observations, _ctx(PAGESPEED_API_KEY=None),
                                      today=today) == [], "actief maar zonder key = niet geconfigureerd"
    assert cockpit2._Stores(dd).sources.configured("mobiel_audit") is False
    st = cockpit2._Stores(dd)
    w = collect_daily_observations(reg, st.sources, st.observations, _ctx(), today=today)
    assert sorted(w) == sorted([("mobiel_audit", "performance", "2026-09-07"),
                                ("mobiel_audit", "lcp_ms", "2026-09-07"),
                                ("mobiel_audit", "cls", "2026-09-07"),
                                ("mobiel_audit", "tbt_ms", "2026-09-07")])
    rows = cockpit2._Stores(dd).observations.daily_series("mobiel_audit_performance_day", bron="mobiel_audit")
    assert len(rows) == 1 and rows[0]["value"] == 72 and (rows[0].get("meta") or {}).get("lighthouse") == "12.6.0"
    st = cockpit2._Stores(dd)
    assert collect_daily_observations(reg, st.sources, st.observations, _ctx(), today=today) == [], "idempotent"


def test_catalogus_en_definities_kennen_de_reeks():
    from nooch_village import definitions, meetcatalog
    assert meetcatalog._in_catalog("mobiel_audit_performance_day", "mobiel_audit")
    assert meetcatalog._in_catalog("mobiel_audit_veld_cls_day", "mobiel_audit")
    namen = {e["name"]: e for e in definitions._DEFINITION_SEED if e.get("source") == "mobiel_audit"}
    assert len(namen) == 7
    velden = {definitions._SEED_VELD[n] for n in namen}
    assert velden == set(_METRICS), "elke definitie hangt aan een veld dat de skill echt levert"
    assert definitions._SOURCE_CATEGORIE["mobiel_audit"] == "Website"


def test_geregistreerd_en_in_de_rugzak():
    import json
    from nooch_village.registry_factory import build_skill_registry
    assert build_skill_registry().get("mobiel_audit") is not None
    rz = json.load(open("config/rugzakken.json", encoding="utf-8"))
    assert "mobiel_audit" in rz["onze_cijfers"]["skills"]
