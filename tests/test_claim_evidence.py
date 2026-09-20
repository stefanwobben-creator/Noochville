"""claim_evidence — bewijs-controle per merk tegen de merksites. SerpAPI + fetch + LLM volledig gemockt.

Kern: de grondings-poort. Een citaat dat niet LETTERLIJK in de opgehaalde paginatekst staat, valt af —
zo kan de autonome (merknaam → webzoek) variant geen bewijs hallucineren."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill, _grounded

# De skill slaat pagina's < 200 tekens over als 'niet leesbaar'; vul testpagina's aan met neutrale
# vultekst zodat ze de drempel halen (het gegronde citaat blijft letterlijk aanwezig).
_PAD = (" Deze webpagina bevat verder algemene informatie over verzending, retourbeleid, "
        "klantenservice, maatvoering en de geschiedenis van het merk, puur als context. " * 2)


def _ctx(key="k"):
    return SimpleNamespace(settings=({"SERPAPI_API_KEY": key} if key else {}))


def _reason(claim_aanwezig, onderbouwd, citaat):
    payload = json.dumps({"claim_aanwezig": claim_aanwezig, "onderbouwd": onderbouwd, "citaat": citaat})
    def fake(prompt, **kw):
        return payload
    return fake


def _search(*links):
    def fake(query, key, num=10):
        return [{"title": f"t{i}", "link": l} for i, l in enumerate(links)]
    return fake


# ── payload-poort ─────────────────────────────────────────────────────────────

def test_zonder_brands_of_claim_faalt():
    assert ClaimEvidenceSkill().run({"brands": [], "claim": "afbreekbaar"}, _ctx())["ok"] is False
    assert ClaimEvidenceSkill().run({"brands": ["Veja"], "claim": ""}, _ctx())["ok"] is False


def test_zonder_key_faalt_closed():
    res = ClaimEvidenceSkill().run({"brands": ["Veja"], "claim": "afbreekbaar"}, _ctx(key=""))
    assert res["ok"] is False and "SERPAPI" in res["error"]


# ── status-paden ──────────────────────────────────────────────────────────────

def test_bevestigd_bij_claim_met_onderbouwing():
    page = "Onze zolen zijn gecertificeerd biodegradable volgens ISO 14855, labresultaat bijgevoegd." + _PAD
    with patch("nooch_village.web_read.serpapi_search", _search("https://veja.example/duurzaam")), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(True, True, "gecertificeerd biodegradable volgens ISO 14855")):
        res = ClaimEvidenceSkill().run({"brands": ["Veja"], "claim": "biodegradable"}, _ctx())
    row = res["rows"][0]
    assert res["ok"] and row["status"] == "bevestigd"
    assert "ISO 14855" in row["evidence"] and row["source"].startswith("https://veja")


def test_onduidelijk_bij_claim_zonder_onderbouwing():
    page = "Wij geloven in afbreekbare schoenen voor een betere wereld, dat is onze missie." + _PAD
    with patch("nooch_village.web_read.serpapi_search", _search("https://merk.example")), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(True, False, "Wij geloven in afbreekbare schoenen voor een betere wereld")):
        res = ClaimEvidenceSkill().run({"brands": ["MerkX"], "claim": "afbreekbaar"}, _ctx())
    assert res["rows"][0]["status"] == "onduidelijk"


def test_leeg_als_geen_claim_gevonden():
    page = "Wij verkopen sneakers in vele kleuren. Gratis verzending vanaf 50 euro. Retourneren kan." + _PAD
    with patch("nooch_village.web_read.serpapi_search", _search("https://merk.example")), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(False, False, "")):
        res = ClaimEvidenceSkill().run({"brands": ["MerkX"], "claim": "afbreekbaar"}, _ctx())
    assert res["rows"][0]["status"] == "leeg"


def test_fout_als_geen_pagina_leesbaar():
    with patch("nooch_village.web_read.serpapi_search", _search("https://merk.example")), \
         patch("nooch_village.web_read.fetch_text", return_value=""), \
         patch("nooch_village.llm.reason", _reason(True, True, "iets")):
        res = ClaimEvidenceSkill().run({"brands": ["MerkX"], "claim": "afbreekbaar"}, _ctx())
    assert res["rows"][0]["status"] == "fout"


# ── de grondings-poort: gehallucineerd citaat valt af ─────────────────────────

def test_gehallucineerd_citaat_wordt_afgewezen():
    page = "Wij verkopen duurzame schoenen. Onze zolen zijn afbreekbaar getest." + _PAD
    # LLM beweert claim + onderbouwing, maar het citaat staat NIET in de pagina → moet afvallen → leeg
    with patch("nooch_village.web_read.serpapi_search", _search("https://merk.example")), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(True, True, "gecertificeerd door TÜV met labrapport nummer 12345")):
        res = ClaimEvidenceSkill().run({"brands": ["MerkX"], "claim": "afbreekbaar"}, _ctx())
    assert res["rows"][0]["status"] == "leeg"           # bewijs niet gegrond → niet doorgelaten


def test_grounded_helper_direct():
    text = "Onze zolen zijn gecertificeerd biodegradable volgens ISO 14855."
    assert _grounded("gecertificeerd biodegradable volgens ISO 14855", text) is True
    assert _grounded("labrapport nummer 99999", text) is False      # niet in tekst
    assert _grounded("ISO", text) is False                          # te kort (< 20 tekens)


# ── meerdere merken: counts aggregeren ────────────────────────────────────────

def test_counts_over_meerdere_merken():
    page = "Onze zolen zijn gecertificeerd biodegradable volgens ISO 14855." + _PAD
    with patch("nooch_village.web_read.serpapi_search", _search("https://a.example")), \
         patch("nooch_village.web_read.fetch_text", return_value=page), \
         patch("nooch_village.llm.reason", _reason(True, True, "gecertificeerd biodegradable volgens ISO 14855")):
        res = ClaimEvidenceSkill().run({"brands": ["A", "B", "C"], "claim": "biodegradable"}, _ctx())
    assert res["counts"]["bevestigd"] == 3 and len(res["rows"]) == 3


# ── De verzamelaar (pijplijn stap 2, 20 sept 2026) ──────────────────────────
#
# Deze adapter is de makkelijkste van de vijf, en om een reden die het noteren waard is: de skill
# was al side-effect-free (de rol/dispatch-laag schreef de Kroniek-records, niet de skill). De
# verzamelaar leest dezelfde Kroniek terug en hoeft dus niets te ontvlechten.
#
# En hij vraagt GEEN model. Bij de andere vier beoordeelt een model iets; hier is het oordeel al
# geveld en vastgelegd tijdens de run. Nog een keer vragen zou een tweede oordeel over hetzelfde
# feit zijn — precies wat de Kroniek moet voorkomen.

def _ledger(tmp_path):
    from nooch_village.evidence_ledger import EvidenceLedger
    return EvidenceLedger(str(tmp_path / "evidence.jsonl"))


def test_verzamel_leest_de_kroniek_en_vraagt_geen_model(tmp_path, monkeypatch):
    from nooch_village.skills_impl.claim_evidence import verzamel
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("de verzamelaar riep een model aan")))

    led = _ledger(tmp_path)
    led.record(role_id="r", skill="claim_evidence", query="carbon neutral",
               source="https://veja.com/x", status="bevestigd",
               meta={"brand": "Veja", "citaat": "certified by SGS"})
    uit = verzamel(led)
    assert len(uit) == 1
    s = uit[0]
    assert s.bron == "bewijs"
    assert "Veja" in s.tekst and "carbon neutral" in s.tekst and "bevestigd" in s.tekst
    assert s.vindplaats == "https://veja.com/x"
    assert s.extra["status"] == "bevestigd" and s.extra["citaat"] == "certified by SGS"


def test_leeg_haalt_de_memo_niet(tmp_path):
    """"We vonden de claim niet" is de normale uitkomst van een scan. Die in de memo zetten vult
    hem met afwezigheid, en dan leest niemand hem nog. `bevestigd` en `fout` zeggen wél iets: het
    eerste is een claim die staat, het tweede dat we het niet konden nakijken."""
    from nooch_village.skills_impl.claim_evidence import verzamel
    led = _ledger(tmp_path)
    led.record(role_id="r", skill="claim_evidence", query="vegan", source="https://a", status="leeg")
    led.record(role_id="r", skill="claim_evidence", query="bio", source="https://b", status="fout")
    assert [s.extra["status"] for s in verzamel(led)] == ["fout"]


def test_alleen_de_eigen_skill(tmp_path):
    """De Kroniek is van het hele dorp. Zonder dit filter zou deze adapter de records van elke
    andere skill als bewijs-signaal doorgeven."""
    from nooch_village.skills_impl.claim_evidence import verzamel
    led = _ledger(tmp_path)
    led.record(role_id="r", skill="claim_evidence", query="a", source="x", status="bevestigd")
    led.record(role_id="r", skill="claims_check", query="b", source="y", status="bevestigd")
    assert [s.extra["claim"] for s in verzamel(led)] == ["a"]


def test_sinds_kapt_de_geschiedenis_af(tmp_path):
    from nooch_village.skills_impl.claim_evidence import verzamel
    led = _ledger(tmp_path)
    led.record(role_id="r", skill="claim_evidence", query="oud", source="x",
               status="bevestigd", ts=1000.0)
    led.record(role_id="r", skill="claim_evidence", query="nieuw", source="y",
               status="bevestigd", ts=9000.0)
    assert [s.extra["claim"] for s in verzamel(led, sinds=5000.0)] == ["nieuw"]
    assert [s.extra["claim"] for s in verzamel(led)] == ["nieuw", "oud"]    # nieuwste eerst


def test_de_drempel_staat_op_de_bron():
    from nooch_village.skills_impl.claim_evidence import DREMPEL
    from nooch_village.weekmemo import DREMPELS
    assert DREMPEL == "precisie" and DREMPEL in DREMPELS
