"""Scope 50a (12 september 2026) — de leesketen: wat gelezen is, haalt de note, de conclusie en het verslag.

Het lijmvrij-verslag noemde vier merknamen en verder niets, terwijl web_zoek vijf pagina's van 3000
tekens had gelezen. De keten gooide het lezen in drie stappen weg (note 160 tekens per veld, conclusie
uit die note, verslag `str(dict)[:1200]`). Deze tests leggen de reparatie vast:

1. `leesextract.verrijk` zet per gelezen record een extract IN het record, één modelronde, fail-soft;
2. de note toont het extract direct na de titel en niet meer de afgekapte ruwe tekst;
3. de uitvoerlus doet dit vóór note en store, dus store en verslag zien hetzelfde;
4. het verslag rendert records (titel, adres, strekking) in plaats van een dict-repr, met de dekking.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from nooch_village import leesextract as le
from nooch_village import deliverable_kop as dk
from nooch_village import project_verslag as pv
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.projects import ProjectLedger
from nooch_village.skills import Skill, SkillRegistry

LANG = ("Kiilto Biomelt is the world's first biodegradable hot melt adhesive. It is made from renewable "
        "raw materials and is certified compostable. The product is used in packaging lines. ") * 6
KORT = "A snippet of three hundred characters at most, as the search engine gives it."


def _web_zoek_result(n_gelezen=2, n_totaal=3):
    treffers = []
    for i in range(n_totaal):
        gelezen = i < n_gelezen
        treffers.append({"titel": f"Page {i}", "url": f"https://example.org/{i}", "domein": "example.org",
                         "fragment": KORT, "tekst": LANG if gelezen else "", "gelezen": gelezen,
                         "reden": "" if gelezen else "niet opgehaald"})
    return {"ok": True, "term": "bio-based hot melt", "bron": "serpapi", "aantal_treffers": n_totaal,
            "treffers": treffers, "gelezen": n_gelezen, "volledig_gelezen": n_gelezen == n_totaal,
            "text": "Searched…"}


# ── 1: het extract komt in het record ────────────────────────────────────────

def test_alleen_gelezen_records_met_lange_tekst_worden_gelezen():
    r = _web_zoek_result(n_gelezen=2, n_totaal=3)
    paren = le.te_lezen(r, ("list", "treffers"))
    assert [p[0]["titel"] for p in paren] == ["Page 0", "Page 1"]
    assert all(veld == "tekst" for _, veld in paren)
    assert le.te_lezen({"hits": [{"title": "x", "abstract": "kort"}]}, ("list", "hits")) == []
    assert le.te_lezen({"t": LANG}, ("text", "t")) == []                     # geen lijst → niets
    assert le.te_lezen(r, None) == []


def test_verrijk_zet_extract_in_het_record_met_een_modelronde():
    r = _web_zoek_result()
    gezien = []

    def _model(prompt, **k):
        gezien.append((prompt, k))
        return json.dumps({"1": "Kiilto Biomelt is a biodegradable hot melt for packaging.",
                           "2": "Same product page, certified compostable."})
    assert le.verrijk("Find bio-based hot melts", r, ("list", "treffers"), reason_fn=_model) == 2
    assert r["treffers"][0]["extract"].startswith("Kiilto Biomelt is a biodegradable")
    assert r["treffers"][1]["extract"] == "Same product page, certified compostable."
    assert "extract" not in r["treffers"][2]                                  # ongelezen: geen extract
    assert r["treffers"][0]["tekst"] == LANG                                  # het ruwe materiaal blijft
    prompt, kw = gezien[0]
    assert len(gezien) == 1 and kw["call_site"] == "lees_extract" and kw["json_mode"] is True
    assert "only what is literally in the text" in prompt and "TEXT 2 (Page 1)" in prompt
    assert "Find bio-based hot melts" in prompt


def test_verrijk_is_fail_soft():
    r = _web_zoek_result()

    def _stuk(*a, **k):
        raise RuntimeError("geen krediet")
    assert le.verrijk("v", r, ("list", "treffers"), reason_fn=_stuk) == 0
    assert le.verrijk("v", r, ("list", "treffers"), reason_fn=lambda *a, **k: "geen json") == 0
    assert le.verrijk("v", r, ("list", "treffers"), reason_fn=lambda *a, **k: "") == 0
    assert all("extract" not in t for t in r["treffers"])
    # niets te lezen → het model wordt niet eens gevraagd
    assert le.verrijk("v", {"hits": [{"title": "x"}]}, ("list", "hits"), reason_fn=lambda *a, **k: 1 / 0) == 0


def test_verrijk_slaat_records_over_die_al_een_extract_hebben():
    r = _web_zoek_result()
    r["treffers"][0]["extract"] = "Al gedaan."
    n = le.verrijk("v", r, ("list", "treffers"), reason_fn=lambda *a, **k: json.dumps({"1": "Nieuw."}))
    assert n == 1 and r["treffers"][0]["extract"] == "Al gedaan." and r["treffers"][1]["extract"] == "Nieuw."


def test_extract_is_gecapt_en_fence_wordt_getolereerd():
    r = _web_zoek_result(n_gelezen=1, n_totaal=1)
    lang = "woord " * 200
    n = le.verrijk("v", r, ("list", "treffers"),
                   reason_fn=lambda *a, **k: "```json\n" + json.dumps({"1": lang}) + "\n```")
    assert n == 1 and len(r["treffers"][0]["extract"]) <= le.EXTRACT_MAX


# ── 2: de note toont het extract, niet de afgekapte ruwe tekst ───────────────

def _inwoner(tmp_path=None, ledger=None, reg=None):
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["web_zoek"]), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, rugzakken={},
                          data_dir=str(tmp_path) if tmp_path else None, projects=ledger, records=None)
    return Inhabitant(rec, EventBus(name="test"), reg or SkillRegistry(), ctx)








def test_de_conclusie_ziet_meer_dan_2000_tekens():
    """Vijf gelezen pagina's met extract zijn ~2500 tekens; bij 2000 zag de conclusie de laatste
    twee niet."""
    gezien = {}
    note = "📎 kop\n" + "\n".join(f"• titel: P{i} | extract: {'z' * 400}" for i in range(6))
    dk.conclusie("v", note, reason_fn=lambda p, **k: gezien.setdefault("p", p) or "ok")
    assert "• titel: P5" in gezien["p"]


# ── 3: de uitvoerlus leest vóór note en store ────────────────────────────────

class _ZoekSkill(Skill):
    name = "web_zoek"
    description = "fake"

    def run(self, payload, context):
        return _web_zoek_result()














