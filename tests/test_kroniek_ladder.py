"""De Kroniek fase 1 — skill-ladder (leren via alternatief pad). Dode route → volgende tree; bevestigd
stopt direct; escaleren is de LÁÁTSTE tree (alleen bij een fout, niet bij legitiem leeg)."""
from __future__ import annotations

from nooch_village.evidence_ledger import EvidenceLedger, run_with_ladder, classify_result


def _led(tmp_path):
    return EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))


def test_classify_result():
    assert classify_result({"patents": [{"x": 1}]}) == "bevestigd"
    assert classify_result({"no_data": True}) == "leeg"
    assert classify_result({"patents": []}) == "leeg"
    assert classify_result({"error": "HTTP 500"}) == "fout"
    assert classify_result(None) == "leeg"


def test_dode_route_dan_alternatief_pad(tmp_path):
    led = _led(tmp_path)
    calls = []
    def epo():    calls.append("epo");    return {"error": "HTTP 500"}
    def google(): calls.append("google"); return {"patents": [{"title": "x"}]}
    res = run_with_ladder(led, role_id="harry_hemp", skill="patents", query="PHA",
                          rungs=[("epo", epo), ("google", google)])
    assert res["status"] == "bevestigd" and res["source"] == "google" and not res["escalated"]
    assert calls == ["epo", "google"]                                  # A vast → B geprobeerd
    assert [r["status"] for r in led.all_records()] == ["fout", "bevestigd"]   # beide gelogd


def test_bevestigd_stopt_de_ladder(tmp_path):
    led = _led(tmp_path)
    later = []
    def epo():    return {"patents": [{"title": "x"}]}
    def google(): later.append(1); return {"patents": []}
    res = run_with_ladder(led, role_id="r", skill="patents", query="q",
                          rungs=[("epo", epo), ("google", google)])
    assert res["status"] == "bevestigd" and res["source"] == "epo"
    assert later == [] and len(led.all_records()) == 1                 # tweede tree niet aangeroepen


def test_alles_fout_escaleert_precies_een_keer(tmp_path):
    led = _led(tmp_path)
    esc = []
    def epo():    return {"error": "down"}
    def google(): raise RuntimeError("boom")                          # raise → fout
    res = run_with_ladder(led, role_id="r", skill="patents", query="q",
                          rungs=[("epo", epo), ("google", google)],
                          escalate=lambda **kw: esc.append(kw))
    assert res["status"] == "fout" and res["escalated"] and len(esc) == 1
    assert [r["status"] for r in led.all_records()] == ["fout", "fout"]


def test_alles_leeg_is_legitiem_no_data_geen_escalatie(tmp_path):
    led = _led(tmp_path)
    esc = []
    res = run_with_ladder(led, role_id="r", skill="patents", query="q",
                          rungs=[("epo", lambda: {"no_data": True}), ("google", lambda: {"patents": []})],
                          escalate=lambda **kw: esc.append(kw))
    assert res["status"] == "leeg" and not res["escalated"] and esc == []


def test_leeg_wint_van_latere_fout_geen_escalatie(tmp_path):
    """Bron 1 geeft een écht 'niets gevonden' (leeg), bron 2 is stuk (fout) → uitkomst = leeg (er ís een
    no-data-antwoord), géén escalatie. De kapotte fallback blokkeert het echte feit niet."""
    led = _led(tmp_path)
    esc = []
    res = run_with_ladder(led, role_id="harry_hemp", skill="openalex_evidence", query="niche",
                          rungs=[("openalex_evidence", lambda: {"no_data": True}),
                                 ("semscholar_tldr", lambda: {"error": "HTTP 429"})],
                          escalate=lambda **kw: esc.append(kw))
    assert res["status"] == "leeg" and res["source"] == "openalex_evidence" and not res["escalated"]
    assert esc == [] and [r["status"] for r in led.all_records()] == ["leeg", "fout"]   # beide onthouden
