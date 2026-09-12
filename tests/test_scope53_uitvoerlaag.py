"""Scope 53 — de uitvoerlaag leest eerlijk (skill-review 12 september 2026).

Vijf reviewers lazen alle 55 skills en vonden vier patronen die niet bij één skill horen maar bij
de laag die hun antwoord leest. Dit bestand bewaakt die laag:

1. Een API-sleutel komt nooit op de wall, in de store of in het log (`sleutelmasker`, web_read,
   `_foutreden`, `_execute_skill`).
2. "Vol maar leeg" leest als leeg: rijen die zelf `no_data` zeggen, dicts vol None, echo's van de
   invoer en run-administratie zijn geen resultaat (`_classify_result`).
3. De `text` van een skill is de leeswijzer boven zijn records — in de note én in het verslag.
4. Een skill zonder sleutel wordt niet gepland (`_config_ontbreekt`), en een `reden` wordt gelezen
   als een `reason`.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from nooch_village import project_verslag, sleutelmasker, web_read
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.skills import Skill, SkillRegistry


# ── gereedschap ──────────────────────────────────────────────────────────────

class _Skill(Skill):
    cost = "free"

    def __init__(self, naam, *, desc="doet iets", insch="term: str", required_env=(), configured=True):
        self.name = naam
        self.description = desc
        self.input_schema = insch
        self.required_env = tuple(required_env)
        self._configured = configured

    def is_configured(self, context) -> bool:
        return self._configured

    def run(self, payload, context):
        return {"ok": True}


def _inw(*skills, rugzakken=None):
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    rec = Record(id="rol_a", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test", skills=[s.name for s in skills]),
                 source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0",
                                    "deliverable_conclusie_enabled": "0"},
                          rugzakken=rugzakken or {})
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


_GEHEIM = "SECRETKEY1234567890abc"
_POOL_FOUT = ("HTTPSConnectionPool(host='serpapi.com', port=443): Max retries exceeded with url: "
              f"/search.json?engine=google&q=barefoot&num=10&api_key={_GEHEIM} (Caused by …)")


# ── 1. de sleutelmasker ──────────────────────────────────────────────────────

def test_masker_haalt_parameter_sleutels_uit_een_requests_fout():
    uit = sleutelmasker.masker(_POOL_FOUT)
    assert _GEHEIM not in uit
    assert "api_key=***" in uit and "q=barefoot" in uit        # de rest van de melding blijft leesbaar


def test_masker_kent_bearer_key_en_apikey_varianten():
    s = f"Authorization: Bearer {_GEHEIM} · key={_GEHEIM} · apikey={_GEHEIM} · token: {_GEHEIM}"
    uit = sleutelmasker.masker(s)
    assert _GEHEIM not in uit and uit.count("***") == 4


def test_masker_laat_korte_note_velden_met_rust():
    """'key: youtube' in een dictlist-note is een veldnaam, geen sleutel."""
    assert sleutelmasker.masker("key: youtube | value: 0") == "key: youtube | value: 0"


def test_masker_kent_de_echte_sleutelwaarden_uit_de_omgeving(monkeypatch):
    monkeypatch.setenv("VOORBEELD_API_KEY", _GEHEIM)
    assert _GEHEIM not in sleutelmasker.masker(f"Brave gaf 422 — body: {_GEHEIM} ongeldig")


def test_http_fout_draagt_status_en_body_maar_geen_url():
    resp = SimpleNamespace(status_code=401, reason="Unauthorized",
                           text='{"error": "Invalid API key"}',
                           url=f"https://serpapi.com/search.json?api_key={_GEHEIM}")
    m = sleutelmasker.http_fout(resp, "SerpAPI")
    assert m.startswith("SerpAPI gaf HTTP 401 Unauthorized") and "Invalid API key" in m
    assert _GEHEIM not in m and "serpapi.com/search.json" not in m


# ── 2. web_read bouwt de fout zonder URL ─────────────────────────────────────

def test_serpapi_search_fout_zonder_sleutel(monkeypatch):
    class _Resp:
        status_code = 429
        reason = "Too Many Requests"
        text = "rate limited"
        url = f"https://serpapi.com/search.json?q=x&api_key={_GEHEIM}"

        def json(self):
            return {}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError) as e:
        web_read.serpapi_search("x", _GEHEIM)
    assert "429" in str(e.value) and _GEHEIM not in str(e.value)


def test_serpapi_search_stub_zonder_statuscode_werkt_als_voorheen(monkeypatch):
    class _Resp:
        def json(self):
            return {"organic_results": [{"title": "T", "link": "https://a.example", "snippet": "s"}]}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    assert web_read.serpapi_search("x", "k")[0]["link"] == "https://a.example"


# ── 3. de executor maskeert elke foutreden en leest 'reden' ──────────────────

def test_foutreden_maskeert_en_leest_reden():
    assert _GEHEIM not in Inhabitant._foutreden({"ok": False, "error": _POOL_FOUT})
    assert Inhabitant._foutreden({"ok": False, "reden": "week al gescand"}) == "week al gescand"
    assert Inhabitant._foutreden({"ok": False}) == "skill meldde ok=False zonder reden"
    assert Inhabitant._foutreden("skill 'x' niet geregistreerd") == "skill 'x' niet geregistreerd"


def test_execute_skill_geeft_gemaskeerde_fout_terug():
    class _Kapot(_Skill):
        def run(self, payload, context):
            raise RuntimeError(_POOL_FOUT)

    inw = _inw(_Kapot("kapot"))
    ok, uit = inw._execute_skill("kapot", {})
    assert ok is False and _GEHEIM not in uit and "api_key=***" in uit


# ── 4. vol maar leeg ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("result", [
    # ngram / google_trends: elke term een time-out → rijen die zelf no_data zeggen
    {"rows": [{"term": "a", "no_data": True, "reason": "timeout"},
              {"term": "b", "no_data": True, "reason": "timeout"}],
     "terms": {"a": {"corpus": 26, "error": "timeout"}, "b": {"corpus": 26, "error": "timeout"}},
     "year_start": 1990, "year_end": 2019},
    # trends_categorie: een dict vol None
    {"datum": "2026-09-12", "values": {"x": None, "y": None}},
    # competitor_news: alleen de echo van de invoer
    {"ok": True, "items": [], "brands": ["Veja", "Moea"], "windows": [30, 90, 365]},
    # gsc: nul rijen, de site-id als enige tekst
    {"ok": True, "site": "sc-domain:nooch.earth", "rows": [], "bucket_counts": {}, "period": "28d"},
    # gsc_report / field_note: een bestandspad
    {"path": "data/output/gsc_nota_2026-09-12.md", "today": "2026-09-12"},
    # keywords_everywhere: configuratie-echo
    {"data": [], "currency": "eur", "data_source": "gkp", "credits_remaining": 812},
    # community_listening: louter nullen
    {"ok": True, "counts": {"youtube": 0, "bluesky": 0}, "observaties": []},
    # escaleer-beslissing: alleen administratie
    {"aard": "beslissing", "naar": "the_source", "reden": "kies", "notif_id": "N-1"},
])
def test_vol_maar_leeg_leest_als_leeg(result):
    assert Inhabitant._classify_result(result)[0] == "leeg"


def test_een_rij_met_inhoud_tussen_lege_rijen_telt_wel():
    r = {"rows": [{"term": "a", "no_data": True}, {"term": "b", "signal": {"direction": "stijgend"}}]}
    assert Inhabitant._classify_result(r) == ("gelukt", ("list", "rows"))


def test_expliciete_signalen_blijven_leidend():
    assert Inhabitant._classify_result({"ok": False, "rows": [{"a": 1}]})[0] == "fout"
    assert Inhabitant._classify_result({"no_data": True, "rows": [{"a": 1}]})[0] == "leeg"


# ── 5. de text als leeswijzer ────────────────────────────────────────────────

def test_note_toont_de_text_van_de_skill_boven_de_records():
    inw = _inw(_Skill("web_zoek"))
    result = {"text": "3 of 9 results read in full; nothing can be said about the other 6.",
              "treffers": [{"title": "A", "url": "https://a.example", "fragment": "aa"},
                           {"title": "B", "url": "https://b.example", "fragment": "bb"}]}
    note = inw._deliverable_note({"text": "zoek", "skill": "web_zoek"}, result, ("list", "treffers"))
    regels = note.split("\n")
    assert regels[1].startswith("3 of 9 results read in full")
    assert "title: A" in note and "title: B" in note


def test_leeswijzer_niet_dubbel_bij_tekst_archetype():
    inw = _inw(_Skill("x"))
    result = {"text": "Alleen deze tekst."}
    note = inw._deliverable_note({"text": "t", "skill": "x"}, result, ("text", "text"))
    assert note.count("Alleen deze tekst.") == 1


def test_verslag_zet_de_text_eerst_en_kent_de_nieuwe_veldnamen():
    inhoud = {"text": "performance 58 · LCP 20.3 s", "rows": [
        {"keyword": "barefoot shoes", "evidence": "12100 searches per month", "permalink": "https://k.example"}]}
    t = project_verslag.inhoud_tekst(inhoud)
    assert t.splitlines()[0] == "performance 58 · LCP 20.3 s"
    assert "• barefoot shoes (https://k.example) — 12100 searches per month" in t


def test_verslag_geeft_tekst_terug_in_plaats_van_json():
    inhoud = {"voorstel": "SCOPE: a\nAPPROACH: b\nTRADE-OFF: c", "ok": True}
    t = project_verslag.inhoud_tekst(inhoud)
    assert t == "SCOPE: a\nAPPROACH: b\nTRADE-OFF: c"
    reeks = project_verslag.inhoud_tekst({"results": {"visitors": 312, "pageviews": 900}, "period": "7d"})
    assert reeks == "results: visitors=312; pageviews=900"
    assert project_verslag.inhoud_tekst({"a": 1}) == json.dumps({"a": 1})


# ── 6. de configuratiepoort ──────────────────────────────────────────────────

def test_skill_zonder_sleutel_staat_niet_in_de_catalogus_en_is_niet_uitvoerbaar():
    los = _Skill("shopify_sales", required_env=("SHOPIFY_TOKEN",), configured=False)
    goed = _Skill("plausible_stats", required_env=("PLAUSIBLE_API_KEY",), configured=True)
    inw = _inw(los, goed)
    assert inw._config_ontbreekt("shopify_sales").startswith("shopify_sales is not configured")
    assert "SHOPIFY_TOKEN" in inw._config_ontbreekt("shopify_sales")
    assert inw._config_ontbreekt("plausible_stats") == ""
    assert inw._payload_issues("shopify_sales", {"window_days": 30})[0].startswith("shopify_sales is not configured")
    assert inw._payload_issues("plausible_stats", {"period": "7d"}) == []


def test_configuratiepoort_is_fail_soft_zonder_required_env():
    inw = _inw(_Skill("web_zoek", configured=False))              # geen required_env → geen oordeel
    assert inw._config_ontbreekt("web_zoek") == ""
    assert inw._config_ontbreekt("bestaat_niet") == ""


# ── 7. periodieke skills uit de gedeelde rugzak ──────────────────────────────

def test_periodieke_schrijvers_zitten_niet_in_de_rugzak_schrijven():
    with open("config/rugzakken.json", encoding="utf-8") as f:
        rz = json.load(f)
    assert set(rz["schrijven"]["skills"]) == {"content_schrijven", "voorstel_schrijven"}
