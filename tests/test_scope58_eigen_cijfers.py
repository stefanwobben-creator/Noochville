"""Scope 58 — de eigen cijfers openen met het kopcijfer, en een skill zonder sleutel of data zegt dat.

Batch E van de skill-review (12 september 2026): plausible_stats, gsc_performance, gsc_report,
shopify_sales, site_health, mobiel_audit, co2_village en budget_adjust. Drie patronen, alle drie
gemeten door de echte uitvoerlaag (`Inhabitant._classify_result`, `_deliverable_note`,
`project_verslag.inhoud_tekst`) op representatieve resultaten te draaien:

1. Kopcijfers verloren van details: de grootste lijst won, dus plausible toonde paginapaden zonder
   bezoekers, shopify landen zonder paren, mobiel_audit falende audits zonder score. Nu `rows` met
   de kopcijfers eerst + een `text` als leeswijzer.
2. Leeg als gelukt: gsc met 0 rijen, gsc_report met elke payload, shopify met 0 orders, co2 zonder
   log — nu `no_data` + reason (📭), of `error` waar de bron niet geraadpleegd is.
3. Ontbrekende sleutel is geen plan-tijd-kennis: shopify werd vijf keer gepland zonder token. Nu
   `validate_payload`/`config_hint`, `.env.example` met de sleutelNAMEN, en een site_health die
   een 404 als bevinding meldt in plaats van als skill-fout.

Alles offline: requests, DNS en Google zijn gemockt of geïnjecteerd.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from nooch_village import project_verslag, site_audit
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.skills import SkillRegistry

C = Inhabitant._classify_result
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── gereedschap ──────────────────────────────────────────────────────────────

def _inw(*skills):
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    rec = Record(id="rol_e", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test", skills=[s.name for s in skills]), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", "deliverable_conclusie_enabled": "0",
                                    "lees_extract_enabled": "0"}, rugzakken={})
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


def _note(inw, skill: str, result: dict) -> str:
    status, arch = C(result)
    assert status == "gelukt", (status, result.get("reason") or result.get("error"))
    return inw._deliverable_note({"text": "item", "skill": skill}, result, arch)


# ══ 1. plausible_stats ═══════════════════════════════════════════════════════

def _plausible_ctx(**extra):
    return SimpleNamespace(settings={"PLAUSIBLE_API_KEY": "k", "PLAUSIBLE_SITE_ID": "nooch.earth", **extra})


def _plausible_get(url, **kw):
    """Aggregate met kopcijfers, breakdowns met tien pagina's — de vorm van de review-meting."""
    prop = kw.get("params", {}).get("property", "")
    resp = MagicMock(); resp.raise_for_status = MagicMock()
    if "aggregate" in url and kw["params"].get("period") == "day":
        resp.json.return_value = {"results": {"visitors": {"value": 40}}}
    elif "aggregate" in url:
        resp.json.return_value = {"results": {"visitors": {"value": 312}, "pageviews": {"value": 900},
                                              "visit_duration": {"value": 61}, "bounce_rate": {"value": 55}}}
    elif prop == "event:page":
        resp.json.return_value = {"results": [{"page": f"/p{i}", "visitors": 50 - i} for i in range(10)]}
    elif prop == "visit:source":
        resp.json.return_value = {"results": [{"source": "Google", "visitors": 100}]}
    elif prop == "visit:country":
        resp.json.return_value = {"results": [{"country": "NL", "visitors": 200}]}
    else:
        resp.json.return_value = {"results": []}
    return resp


def test_plausible_opent_met_de_kopcijfers_en_niet_met_paginapaden():
    from nooch_village.skills_impl.plausible import PlausibleSkill
    with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_plausible_get):
        r = PlausibleSkill().run({"period": "7d"}, _plausible_ctx())
    assert C(r) == ("gelukt", ("list", "rows"))                # rows wint van top_pages
    assert [x["metric"] for x in r["rows"][:5]] == ["visitors", "pageviews", "visit_duration", "bounce_rate",
                                                     "visitors_day"]
    assert r["rows"][0] == {"period": "7d", "metric": "visitors", "waarde": 312,
                            "text": "312 unique visitors in the last 7 days"}
    # de breakdown-regels dragen de naam als titelveld (het verslag kent geen `country` als titel)
    land = next(x for x in r["rows"] if x.get("dimension") == "country")
    assert land["name"] == "NL" and land["waarde"] == 200 and "NL" in land["text"]
    assert r["text"].startswith("312 unique visitors and 900 pageviews in the last 7 days")
    assert "Yesterday" in r["text"] and "top country NL (200)" in r["text"]
    # de oude sleutels blijven voor roles.py (_extract_pulse_metrics, _surface_locale)
    assert r["results"]["visitors"]["value"] == 312 and r["countries"][0]["country"] == "NL"
    note = _note(_inw(PlausibleSkill()), "plausible_stats", r)
    assert note.split("\n")[1].startswith("312 unique visitors")
    assert "metric: visitors | period: 7d | waarde: 312" in note
    verslag = project_verslag.inhoud_tekst(r)
    assert verslag.splitlines()[0].startswith("312 unique visitors")
    assert "• visitors — 312 unique visitors in the last 7 days" in verslag
    assert "• /p0 — 50 visitors on /p0 in the last 7 days" in verslag     # het verslag toont 8 records


def test_plausible_zonder_sleutel_is_een_fout_geen_lege_lijst():
    from nooch_village.skills_impl.plausible import PlausibleSkill
    with patch.dict(os.environ, {"PLAUSIBLE_API_KEY": "", "PLAUSIBLE_SITE_ID": ""}):
        r = PlausibleSkill().run({}, SimpleNamespace(settings={}))
    assert C(r)[0] == "fout" and "PLAUSIBLE_API_KEY" in r["error"] and "rows" not in r
    assert PlausibleSkill.required_env == ("PLAUSIBLE_API_KEY", "PLAUSIBLE_SITE_ID")
    assert not PlausibleSkill().is_configured(SimpleNamespace(settings={"PLAUSIBLE_API_KEY": "k"}))
    assert PlausibleSkill().is_configured(_plausible_ctx())


def test_plausible_http_fout_op_het_aggregaat_is_een_fout_zonder_sleutel_in_de_tekst():
    from nooch_village.skills_impl.plausible import PlausibleSkill
    resp = MagicMock(status_code=400, reason="Bad Request", text='{"error":"period is invalid"}')
    resp.raise_for_status.side_effect = requests.HTTPError(
        "400 Client Error: Bad Request for url: https://plausible.io/api/v1/stats/aggregate?site_id=nooch.earth")
    with patch("nooch_village.skills_impl.plausible.requests.get", return_value=resp):
        r = PlausibleSkill().run({"period": "30d"}, _plausible_ctx(PLAUSIBLE_API_KEY="geheim-sleutel-123"))
    assert C(r)[0] == "fout"
    assert "HTTP 400" in r["error"] and "period is invalid" in r["error"]
    assert "geheim-sleutel-123" not in r["error"] and "plausible.io" not in r["error"]
    with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=ConnectionError("down")):
        r2 = PlausibleSkill().run({}, _plausible_ctx())
    assert C(r2)[0] == "fout" and "unreachable" in r2["error"]


def test_plausible_periode_strandt_bij_het_plannen_en_kent_aliassen():
    from nooch_village.skills_impl.plausible import PERIODS, PlausibleSkill
    s = PlausibleSkill()
    assert s.validate_payload({"period": "last 30 days"}, None) == []          # alias → 30d
    assert s.validate_payload({"period": "week"}, None) == []
    assert s.validate_payload({}, None) == []
    fout = s.validate_payload({"period": "afgelopen kwartaal"}, None)
    assert fout and "afgelopen kwartaal" in fout[0] and all(p in fout[0] for p in PERIODS)
    assert s._period("Last 30 Days") == "30d" and s._period("year") == "12mo" and s._period("") == "7d"
    assert s.description.startswith("Real visitor numbers") and "period:" in s.input_schema
    assert all(p in s.input_schema for p in PERIODS)


# ══ 2. gsc_performance ═══════════════════════════════════════════════════════

def _gsc_ctx(site="sc-domain:nooch.earth"):
    return SimpleNamespace(settings={"GSC_SITE": site}, data_dir="/tmp/nv-e")


def _gsc_rows():
    return {"rows": [{"keys": ["vegan sneakers"], "clicks": 3, "impressions": 90, "position": 8.2},
                     {"keys": ["plastic free shoes"], "clicks": 0, "impressions": 40, "position": 14.0},
                     {"keys": ["barefoot shoes"], "clicks": 1, "impressions": 400, "position": 44.0},
                     {"keys": ["schoenen zonder plastic"], "clicks": 0, "impressions": 0, "position": 60.0}]}


def test_gsc_run_bucket_verdeling_locale_en_text():
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    gezien = {}

    def q(body):
        gezien.update(body)
        return _gsc_rows()
    r = GscPerformanceSkill().run({"_query": q, "row_limit": 50}, _gsc_ctx())
    assert gezien["dimensions"] == ["query"] and gezien["rowLimit"] == 50
    assert r["bucket_counts"] == {"page1": 1, "high_potential": 1, "low_ranking": 1, "content_gap": 1}
    assert r["total"] == 4 and r["locale"] == "en" and all(x["locale"] == "en" for x in r["rows"])
    assert r["text"].startswith("4 queries in ") and "1 high potential (position 11–30)" in r["text"]
    assert "1 low ranking (position 31+)" in r["text"] and "4 clicks on 530 impressions" in r["text"]
    assert C(r) == ("gelukt", ("list", "rows"))
    assert r["rows"][0]["text"] == "avg. position 8.2, 90 impressions, 3 clicks (page 1)"
    verslag = project_verslag.inhoud_tekst(r)
    assert verslag.splitlines()[0].startswith("4 queries in") and "• vegan sneakers — avg. position 8.2" in verslag
    # locale uit het domein
    assert GscPerformanceSkill().run({"_query": q}, _gsc_ctx("https://nooch.nl/"))["locale"] == "nl"


def test_gsc_nul_rijen_is_no_data_met_de_lag_als_reden():
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    r = GscPerformanceSkill().run({"_query": lambda b: {"rows": []}}, _gsc_ctx())
    assert C(r)[0] == "leeg" and r["no_data"] is True
    assert "0 rows" in r["reason"] and "28 days" in r["reason"] and "3 days" in r["reason"]
    assert r["rows"] == [] and r["total"] == 0 and r["bucket_counts"] == {}   # TrendsWorker leest deze nog
    fout = GscPerformanceSkill().run({"_query": lambda b: (_ for _ in ()).throw(RuntimeError("quota"))}, _gsc_ctx())
    assert C(fout)[0] == "fout" and "quota" in fout["error"]


def test_gsc_bucketgrenzen_leven_op_een_plek_en_de_planner_kent_alleen_row_limit():
    from nooch_village.skills_impl import gsc
    assert gsc.BUCKET_GRENZEN == {"page1": (1, 10), "high_potential": (11, 30), "low_ranking": (31, None)}
    assert gsc._bucket(10, 5) == "page1" and gsc._bucket(10.1, 5) == "high_potential"
    assert gsc._bucket(30, 5) == "high_potential" and gsc._bucket(30.1, 5) == "low_ranking"
    assert gsc._bucket(3, 0) == "content_gap"
    assert gsc.bucket_bereik("high_potential") == "position 11–30" and gsc.bucket_bereik("low_ranking") == "position 31+"
    s = gsc.GscPerformanceSkill()
    assert s.validate_payload({"row_limit": 200}, None) == [] and s.validate_payload({}, None) == []
    assert any("row_limit" in f for f in s.validate_payload({"row_limit": "veel"}, None))
    assert any("unsupported" in f and "query" in f for f in s.validate_payload({"query": "vegan"}, None))
    assert s.description.startswith("Search queries") and "row_limit" in s.input_schema and "28 days" in s.input_schema


# ══ 3. gsc_report ════════════════════════════════════════════════════════════

def test_gsc_report_zonder_rows_is_fout_en_schrijft_niets(tmp_path):
    from nooch_village.skills_impl.gsc_report import GscReportSkill
    s = GscReportSkill()
    assert s.required_payload == ("rows",) and s.side_effect_free is False
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    for payload in ({}, {"site": "sc-domain:nooch.earth"}, {"rows": "geen lijst"}):
        r = s.run(payload, ctx)
        assert C(r)[0] == "fout" and "rows" in r["error"]
    leeg = s.run({"rows": [], "no_data": True, "reason": "GSC returned 0 rows"}, ctx)
    assert C(leeg)[0] == "leeg" and leeg["reason"] == "GSC returned 0 rows"
    assert not os.path.exists(tmp_path / "output"), "geen lege nota meer in data/output"


def test_gsc_report_schrijft_de_nota_met_de_banden_uit_gsc(tmp_path):
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    from nooch_village.skills_impl.gsc_report import GscReportSkill
    result = GscPerformanceSkill().run({"_query": lambda b: _gsc_rows()}, _gsc_ctx())
    r = GscReportSkill().run(result, SimpleNamespace(data_dir=str(tmp_path)))
    assert C(r)[0] == "gelukt" and r["total"] == 4 and os.path.exists(r["path"])
    nota = open(r["path"], encoding="utf-8").read()
    assert "High potential (position 11–30)" in nota and "Low ranking (position 31+)" in nota
    assert "pos 11–20" not in nota and "21–50" not in nota                 # de oude, foute koppen
    assert "vegan sneakers" in nota and "4 zoekopdrachten" in nota


def test_trendsworker_schrijft_geen_nota_zonder_data():
    """`_maybe_write_nota` zet geen stempel en publiceert geen gsc_nota_written als er niets is."""
    from nooch_village.roles import TrendsWorker
    gepubliceerd = []
    w = SimpleNamespace(_nota_interval=0, _last_nota=0.0, log=MagicMock(), id="trends",
                        bus=SimpleNamespace(publish=gepubliceerd.append),
                        use_skill=lambda naam, payload: {"no_data": True, "reason": "0 rows"})
    TrendsWorker._maybe_write_nota(w, {"rows": []})
    assert gepubliceerd == [] and w._last_nota == 0.0
    w.use_skill = lambda naam, payload: {"path": "data/output/gsc_nota_x.md", "today": "x", "total": 4}
    TrendsWorker._maybe_write_nota(w, {"rows": [{"query": "a"}]})
    assert len(gepubliceerd) == 1 and w._last_nota > 0


# ══ 4. shopify_sales ═════════════════════════════════════════════════════════

def _gql(nodes, has_next=False, cursor=None):
    return {"data": {"orders": {"pageInfo": {"hasNextPage": has_next, "endCursor": cursor}, "nodes": nodes}}}


def _order(country, amount, items, created="2026-06-01T10:00:00Z"):
    return {"createdAt": created, "currentTotalPriceSet": {"shopMoney": {"amount": str(amount), "currencyCode": "EUR"}},
            "shippingAddress": {"countryCodeV2": country},
            "lineItems": {"nodes": [{"title": t, "quantity": q} for t, q in items]}, "customerJourneySummary": None}


def _shop_ctx(**settings):
    return SimpleNamespace(settings={"SHOPIFY_STORE": "x.myshopify.com", "SHOPIFY_TOKEN": "tok", **settings},
                           data_dir="/tmp/nv-e")


def test_shopify_niet_geconfigureerd_strandt_bij_het_plannen_met_de_sleutelnamen():
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    s = ShopifySalesSkill()
    reden = s.validate_payload({"window_days": 30}, SimpleNamespace(settings={"SHOPIFY_STORE": "x"}))
    assert reden and reden[0].startswith("Shopify not configured (")
    assert "SHOPIFY_TOKEN" in reden[0] and "SHOPIFY_CLIENT_ID" in reden[0] and "SHOPIFY_STORE" in reden[0]
    assert s.validate_payload({"window_days": 30}, _shop_ctx()) == []
    assert s.validate_payload({"window_days": 30}, None) == []               # zonder context geen oordeel
    # required_env en is_configured vertellen dezelfde waarheid: alleen de store is onvoorwaardelijk
    assert s.required_env == ("SHOPIFY_STORE",)
    assert set(s.optional_env) == {"SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"}
    assert s.is_configured(_shop_ctx()) and not s.is_configured(SimpleNamespace(settings={"SHOPIFY_STORE": "x"}))
    # de configuratiepoort van de planner noemt via config_hint de of-of, niet alleen 'SHOPIFY_STORE'
    inw = _inw(s)
    inw.context.settings.update({"SHOPIFY_STORE": "x.myshopify.com"})
    poort = inw._config_ontbreekt("shopify_sales")
    assert poort.startswith("shopify_sales is not configured") and "SHOPIFY_TOKEN" in poort
    assert inw._payload_issues("shopify_sales", {"window_days": 30}) == [poort]
    inw.context.settings.update({"SHOPIFY_TOKEN": "tok"})
    assert inw._config_ontbreekt("shopify_sales") == ""
    # de bronnen-view: store gezet maar geen auth-weg → niet 'connected', en de hint zegt wat er mist
    from nooch_village.views.bronnen import _keys_line
    regel = _keys_line({"req": ["SHOPIFY_STORE"], "missing": [], "hint": s.config_hint})
    assert "SHOPIFY_STORE</code> ✓" in regel and "SHOPIFY_TOKEN" in regel
    # vorm van de payload
    assert any("window_days" in f for f in s.validate_payload({"window_days": "vorige maand"}, _shop_ctx()))
    assert any("windows" in f for f in s.validate_payload({"windows": "7"}, _shop_ctx()))
    assert s.description.startswith("Sales figures") and "window_days" in s.input_schema and "windows" in s.input_schema


def test_env_example_noemt_de_shopify_sleutels_zonder_waarden():
    regels = open(os.path.join(BASE, ".env.example"), encoding="utf-8").read().splitlines()
    for naam in ("SHOPIFY_STORE", "SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"):
        assert f"{naam}=" in regels, f"{naam} hoort als lege regel in .env.example"


def test_shopify_opent_met_paren_en_omzet_en_niet_met_landen():
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    post = lambda q, v: _gql([_order("NL", 90, [("Groen", 1)]), _order("DE", 180, [("Groen", 2)])])
    r = ShopifySalesSkill().run({"window_days": 30, "_post": post}, _shop_ctx())
    assert C(r) == ("gelukt", ("list", "rows")) and r["truncated"] is False
    assert [x["metric"] for x in r["rows"][:4]] == ["pairs_sold", "orders", "revenue", "aov"]
    assert r["rows"][0]["text"] == "3 pairs sold in the last 30 days" and r["rows"][0]["waarde"] == 3
    assert r["text"].startswith("3 pairs in 2 orders, €270.00 (AOV €135.00) in the last 30 days")
    assert "stub" not in r["text"].lower()
    land = next(x for x in r["rows"] if x.get("dimension") == "country")
    assert land["name"] == "NL" and land["text"] == "1 order from NL in the last 30 days"
    note = _note(_inw(ShopifySalesSkill()), "shopify_sales", r)
    assert note.split("\n")[1].startswith("3 pairs in 2 orders") and "('NL', 1)" not in note
    assert "• pairs_sold — 3 pairs sold in the last 30 days" in project_verslag.inhoud_tekst(r)
    # de platte sleutels blijven voor de CLI en het dashboard
    assert r["pairs_sold"] == 3 and r["revenue"] == 270.0 and dict(r["by_country"])["NL"] == 1


def test_shopify_nul_orders_is_no_data_en_geen_timestamp():
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    r = ShopifySalesSkill().run({"window_days": 7, "_post": lambda q, v: _gql([])}, _shop_ctx())
    assert r["ok"] is True and r["no_data"] is True and "0 orders in the last 7 days" in r["reason"]
    assert C(r)[0] == "leeg"


def test_shopify_stub_zegt_stub_en_wijkt_voor_client_credentials():
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    r = ShopifySalesSkill().run({"stub": True}, SimpleNamespace(settings={}, data_dir="/tmp"))
    assert r["stub"] is True and r["text"].startswith("STUB") and "stub" in r["text"].lower()
    assert all(x["text"].startswith("stub:") for x in r["rows"]) and r["rows"][0]["waarde"] == 6
    note = _note(_inw(ShopifySalesSkill()), "shopify_sales", r)
    assert note.split("\n")[1].startswith("STUB")
    # client-credentials zijn een live route: de stub-vlag verliest, ook zonder statisch token
    ctx = SimpleNamespace(settings={"SHOPIFY_STORE": "x.myshopify.com", "SHOPIFY_CLIENT_ID": "cid",
                                    "SHOPIFY_CLIENT_SECRET": "sec", "shopify_stub": "true"}, data_dir="/tmp")
    live = ShopifySalesSkill().run({"window_days": 7, "_token_post": lambda s, i, c: "shpat_x",
                                    "_post": lambda q, v: _gql([_order("NL", 90, [("Groen", 1)])])}, ctx)
    assert live.get("stub") is None and live["pairs_sold"] == 1 and "stub" not in live["text"].lower()


def test_shopify_afgekapte_historie_zegt_dat():
    from nooch_village.skills_impl import shopify_sales as ss
    post = lambda q, v: _gql([_order("NL", 90, [("Groen", 1)])], has_next=True, cursor="c")
    orders, truncated = ss.fetch_orders_pages("x", "t", None, _post=post, max_pages=3)
    assert len(orders) == 3 and truncated is True
    with patch.object(ss, "MAX_PAGES", 2):
        r = ss.ShopifySalesSkill().run({"window_days": 0, "_post": post}, _shop_ctx())
    assert r["truncated"] is True and "Truncated" in r["text"]


# ══ 5. site_health ═══════════════════════════════════════════════════════════

def _resp(code, html):
    r = MagicMock(); r.status_code = code; r.encoding = "utf-8"
    r.raw.read.return_value = html.encode("utf-8")
    return r


@pytest.fixture
def _open_host():
    with patch("nooch_village.safe_fetch.controleer_url", lambda u: u):
        yield


def test_site_health_404_is_een_bevinding_geen_skill_fout(_open_host):
    from nooch_village.skills_impl.site_health import SiteHealthSkill
    with patch("nooch_village.skills_impl.site_health.requests.get", return_value=_resp(404, "<title>Not found</title>")) as g:
        r = SiteHealthSkill().run({"url": "https://nooch.earth/x"}, None)
    assert r["status_code"] == 404 and r["bereikbaar"] is False and "ok" not in r and "error" not in r
    assert r["text"] == "HTTP 404 for https://nooch.earth/x (title 'Not found', 0 KiB) — not reachable"
    assert C(r) == ("gelukt", ("text", "text"))                          # item afgevinkt, met de code erin
    assert g.call_args.kwargs["stream"] is True                          # byte-cap via raw.read
    with patch("nooch_village.skills_impl.site_health.requests.get", return_value=_resp(200, "<title> Nooch </title>" + "x" * 2048)):
        ok = SiteHealthSkill().run({}, SimpleNamespace(settings={"mobiel_audit_url": "https://nooch.earth/?preview_theme_id=1"}))
    assert ok["bereikbaar"] is True and ok["title"] == "Nooch" and ok["bytes"] > 2048
    assert ok["url"] == "https://nooch.earth/?preview_theme_id=1" and ok["text"].endswith("— reachable")


def test_site_health_netwerkfout_is_een_error_en_de_url_wordt_gecontroleerd(_open_host):
    from nooch_village import safe_fetch
    from nooch_village.skills_impl.site_health import SiteHealthSkill
    with patch("nooch_village.skills_impl.site_health.requests.get",
               side_effect=ConnectionError("dns https://x/?api_key=geheim12345")):
        r = SiteHealthSkill().run({"url": "https://nooch.earth/"}, None)
    assert C(r)[0] == "fout" and "ConnectionError" in r["error"] and "geheim12345" not in r["error"]
    assert r["status_code"] == 0 and r["bereikbaar"] is False
    # de SSRF-guard van safe_fetch, geen eigen kopie
    def weiger(u):
        raise safe_fetch.FetchGeweigerd("interne adressen worden niet gescand")
    with patch("nooch_village.safe_fetch.controleer_url", weiger), \
         patch("nooch_village.skills_impl.site_health.requests.get") as g:
        r2 = SiteHealthSkill().run({"url": "http://10.0.0.1/"}, None)
    assert "error" in r2 and "refused" in r2["error"] and not g.called
    s = SiteHealthSkill()
    assert s.validate_payload({"url": "PLACEHOLDER — url uit stap 1"}, None)
    assert s.validate_payload({"url": "https://nooch.earth/"}, None) == [] and s.validate_payload({}, None) == []
    assert s.description.startswith("Checks whether") and "url:" in s.input_schema


def test_site_audit_leest_site_health_nog(_open_host):
    from nooch_village.skills_impl.site_health import SiteHealthSkill
    reg = SkillRegistry(); reg.register(SiteHealthSkill())
    with patch("nooch_village.skills_impl.site_health.requests.get", return_value=_resp(404, "<title>x</title>")):
        lamp = site_audit._check_bereikbaar(reg, None, "https://nooch.earth/x", "rol")[0]
    assert lamp["kleur"] == "oranje" and lamp["waarde"] == "404"
    with patch("nooch_village.skills_impl.site_health.requests.get", side_effect=ConnectionError("dns")):
        lamp = site_audit._check_bereikbaar(reg, None, "https://nooch.earth/", "rol")[0]
    assert lamp["kleur"] == "rood" and "ConnectionError" in lamp["uitleg"]


# ══ 6. mobiel_audit ══════════════════════════════════════════════════════════

def test_mobiel_audit_rows_openen_met_de_scores():
    from test_mobiel_audit import _psi, _skill, _ctx, URL
    r = _skill(_psi()).run({"url": URL}, _ctx())
    assert C(r) == ("gelukt", ("list", "rows"))                          # niet meer `bevindingen`
    assert [x["metric"] for x in r["rows"][:4]] == ["performance", "accessibility", "best_practices", "seo"]
    assert r["rows"][0] == {"metric": "performance", "waarde": 72, "weergave": "72/100",
                            "text": "Lighthouse performance score 72 of 100 (mobile)"}
    lcp = next(x for x in r["rows"] if x.get("metric") == "lcp_ms")
    assert lcp["weergave"] == "3.2 s" and lcp["text"] == "LCP 3.2 s (lab, mobile)"
    assert any(x.get("key") == "third-party-cookies" and x["text"].startswith("best_practices:") for x in r["rows"])
    assert any(x.get("key") == "tap-targets" and "mobile check failed" in x["text"] for x in r["rows"])
    from nooch_village.skills_impl.mobiel_audit import MobielAuditSkill
    note = Inhabitant._deliverable_note(_inw(MobielAuditSkill()), {"text": "audit", "skill": "mobiel_audit"}, r, C(r)[1])
    assert "performance 72" in note.split("\n")[1] and "metric: performance | waarde: 72" in note
    assert "• performance — Lighthouse performance score 72 of 100" in project_verslag.inhoud_tekst(r)
    assert r["scores"]["performance"] == 72 and r["bevindingen"]                # site_audit leest deze nog


def test_mobiel_audit_strategie_strandt_bij_het_plannen():
    from nooch_village.skills_impl.mobiel_audit import MobielAuditSkill
    s = MobielAuditSkill()
    assert any("tablet" in f for f in s.validate_payload({"strategie": "tablet"}, None))
    assert s.validate_payload({"strategy": "desktop"}, None) == []


# ══ 7. co2_village ═══════════════════════════════════════════════════════════

def test_co2_factoren_komen_uit_config_met_bron_en_datum():
    from nooch_village import co2
    assert co2.EMISSION_FACTORS == {}                                       # écht leeg in code
    cfg = json.load(open(co2.FACTOREN_PAD, encoding="utf-8"))
    assert cfg["tredes"], "config/co2_factoren.json hoort tredes te kennen"
    for trede, regel in cfg["tredes"].items():
        assert ":" in trede and {"factor", "bron", "datum"} <= set(regel), trede
        assert isinstance(regel["factor"], (int, float)) and regel["bron"].strip() and regel["datum"][:4].isdigit()
    assert co2.factor_for("gemini:gemini-2.5-flash-lite") == cfg["tredes"]["gemini:gemini-2.5-flash-lite"]["factor"]
    assert co2.factor_for("Gemini:Gemini-2.5-Flash-Lite") == co2.factor_for("gemini:gemini-2.5-flash-lite")
    assert co2.factor_for("anthropic:claude-sonnet-5") is None            # premium: nog ongeschat, nooit nul
    assert co2.input_ratio() == cfg["input_ratio"]
    # de prijzen en de factoren spreken over dezelfde tredes
    prijzen = json.load(open(os.path.join(BASE, "config", "llm_prijzen.json"), encoding="utf-8"))["tredes"]
    assert set(cfg["tredes"]) <= set(prijzen)


def test_co2_zonder_log_of_zonder_calls_is_no_data(tmp_path):
    from nooch_village import llm_usage
    from nooch_village.skills_impl.co2_village import Co2VillageSource
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    r = Co2VillageSource().run({"datum": "2026-09-12"}, ctx)
    assert C(r)[0] == "leeg" and "no LLM usage log" in r["reason"]
    p = str(tmp_path / "llm_usage.jsonl")
    llm_usage.record("a", "gemini:gemini-2.5-flash-lite", 4000, 1000, ts=1_700_000_000.0, path=p)
    llm_usage.record("b", "anthropic:claude-sonnet-5", 100, 100, ts=1_700_000_000.0, path=p)
    dag = llm_usage._day(1_700_000_000.0)
    vol = Co2VillageSource().run({"datum": dag}, ctx)
    assert C(vol) == ("gelukt", ("text", "text")) and vol["calls"] == 2 and vol["ongeschat_calls"] == 1
    assert vol["text"].startswith(f"{vol['gram_co2e']} g CO2e over 2 LLM calls on {dag}")
    assert "1 LLM call / 200 tokens not estimated: no emission factor" in vol["text"]
    leeg = Co2VillageSource().run({"datum": "2020-01-01"}, ctx)
    assert C(leeg)[0] == "leeg" and leeg["reason"] == "no LLM calls logged on 2020-01-01"
    assert Co2VillageSource().run({"datum": "vorige week"}, ctx)["error"]
    assert Co2VillageSource().validate_payload({"datum": "vorige week"}, None)
    assert Co2VillageSource().validate_payload({"datum": "yesterday"}, None) == []
    assert Co2VillageSource().validate_payload({"datum": "2026-09-01"}, None) == []
    # de collector-kant blijft een kaal getal per veld (0 is daar een echte dagwaarde)
    assert Co2VillageSource().daily_values(ctx, "2020-01-01") == {"gram_co2e": 0.0, "calls": 0, "ongeschat_calls": 0}


def test_co2_tegel_zegt_hetzelfde_als_de_skill():
    from nooch_village.views.metrics import _SOURCE_GRONDSLAG
    defin, _eenheid, _bron, richting = _SOURCE_GRONDSLAG["co2|gram_co2e"]
    assert richting == "" and "not 'lower is better'" in defin
    defin2, _e, _b, _r = _SOURCE_GRONDSLAG["co2|ongeschat_calls"]
    assert "emission factor" in defin2 and "token count" not in defin2


# ══ 8. budget_adjust is weg ══════════════════════════════════════════════════

def test_budget_adjust_bestaat_niet_meer():
    from nooch_village.registry_factory import build_skill_registry
    assert not os.path.exists(os.path.join(BASE, "nooch_village", "skills_impl", "budget.py"))
    assert build_skill_registry().get("budget_adjust") is None
    readme = open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    assert "`budget_adjust` schrijft" not in readme and "BudgetSkill" not in readme
    src = open(os.path.join(BASE, "nooch_village", "definitions.py"), encoding="utf-8").read()
    assert "NIETS VULT DEZE REEKS" in src                                   # de belofte staat erbij


# ══ 9. de declaratie-sweep raakt geen netwerk en geen bestanden ══════════════

def test_sweep_is_offline_en_laat_geen_nota_achter(tmp_path, monkeypatch):
    from nooch_village.skills_impl.gsc_report import GscReportSkill
    from nooch_village.skills_impl.site_health import SiteHealthSkill
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network")))
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(socket.gaierror("no dns")))
    r = SiteHealthSkill().run({}, None)
    assert "error" in r and "rows" not in r                                # geen exceptie, geen GET
    assert "error" in GscReportSkill().run({}, None)
    assert not os.path.exists(tmp_path / "data")
    src = open(os.path.join(BASE, "tests", "test_payload_declaratie.py"), encoding="utf-8").read()
    assert "_geen_netwerk" in src and "monkeypatch.chdir(tmp_path)" in src
