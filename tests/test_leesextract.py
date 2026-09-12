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


def test_format_record_zet_het_extract_na_de_titel_en_laat_de_ruwe_tekst_weg():
    rec = {"titel": "Page 0", "url": "https://example.org/0", "domein": "example.org", "fragment": KORT,
           "tekst": LANG, "gelezen": True, "extract": "Kiilto Biomelt is a biodegradable hot melt."}
    regel = Inhabitant._format_record(rec)
    assert regel.startswith("titel: Page 0 | extract: Kiilto Biomelt is a biodegradable hot melt.")
    assert "tekst:" not in regel and "url: https://example.org/0" in regel and "fragment:" in regel


def test_format_record_zonder_extract_is_het_oude_gedrag():
    rec = {"titel": "Page 0", "tekst": LANG}
    regel = Inhabitant._format_record(rec)
    assert regel.startswith("titel: Page 0 | tekst: ") and regel.endswith("…") and len(regel) < 200


def test_note_draagt_het_extract(monkeypatch):
    monkeypatch.setattr(dk, "conclusie", lambda *a, **k: "")
    r = _web_zoek_result()
    r["treffers"][0]["extract"] = "Kiilto Biomelt: biodegradable hot melt for packaging."
    note = _inwoner()._deliverable_note({"text": "Find hot melts", "skill": "web_zoek"}, r,
                                        ("list", "treffers"), source="web_zoek")
    regel0 = next(r for r in note.splitlines() if r.startswith("• titel: Page 0"))
    assert "extract: Kiilto Biomelt: biodegradable hot melt for packaging." in regel0
    assert "tekst:" not in regel0                                           # de ruwe 160 tekens zijn weg
    regel1 = next(r for r in note.splitlines() if r.startswith("• titel: Page 1"))
    assert "tekst:" in regel1                                               # zonder extract: oud gedrag


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


def test_uitvoerlus_verrijkt_voor_note_en_store(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    from nooch_village.deliverable_store import DeliverableStore

    def _model(prompt, **k):
        if k.get("call_site") == "lees_extract":
            return json.dumps({"1": "Extract one.", "2": "Extract two."})
        return "One sentence."
    monkeypatch.setattr(llm, "reason", _model)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    reg = SkillRegistry()
    reg.register(_ZoekSkill())
    inw = _inwoner(tmp_path, ledger, reg)
    inw.context.deliverables = DeliverableStore(str(tmp_path / "deliverables.json"))
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Find hot melts", skill="web_zoek", payload={"term": "bio-based hot melt"})
    inw._execute_checklist(ledger.get(pid), "2026-09-12")
    logtxt = " ".join(e["text"] for e in ledger.get(pid).get("log", []))
    assert "extract: Extract one." in logtxt and "extract: Extract two." in logtxt
    recs = inw.context.deliverables.for_project(pid)
    inhoud = inw.context.deliverables.content_for(recs[0]["id"])
    assert inhoud["treffers"][0]["extract"] == "Extract one."             # de store heeft hetzelfde
    assert inhoud["treffers"][0]["tekst"] == LANG                          # en nog steeds het ruwe materiaal


def test_uitvoerlus_zonder_extracten_is_het_oude_gedrag(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "")
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    reg = SkillRegistry()
    reg.register(_ZoekSkill())
    inw = _inwoner(tmp_path, ledger, reg)
    inw.context.settings["lees_extract_enabled"] = "0"
    aangeroepen = []
    monkeypatch.setattr(le, "verrijk", lambda *a, **k: aangeroepen.append(1) or 0)
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Find hot melts", skill="web_zoek", payload={"term": "x"})
    inw._execute_checklist(ledger.get(pid), "2026-09-12")
    assert not aangeroepen                                                 # uitgezet = niet gevraagd
    assert ledger.get(pid)["checklists"][0]["items"][0]["done"] is True    # en het werk ging gewoon door


# ── 4: het verslag rendert records, geen dict-repr ───────────────────────────

def test_inhoud_tekst_rendert_records_met_strekking_en_dekking():
    r = _web_zoek_result(n_gelezen=2, n_totaal=3)
    r["treffers"][0]["extract"] = "Kiilto Biomelt is a biodegradable hot melt for packaging."
    tekst = pv.inhoud_tekst(r)
    regels = tekst.splitlines()
    assert regels[0] == "Searched…"                        # de `text` van de skill is de leeswijzer (scope 53)
    assert regels[1] == ("• Page 0 (https://example.org/0) — Kiilto Biomelt is a biodegradable hot melt "
                         "for packaging.")
    assert regels[2].startswith("• Page 1 (https://example.org/1) — " + KORT[:40])   # geen extract → fragment
    assert regels[3].startswith("• Page 2 (https://example.org/2) — " + KORT[:40])
    assert regels[4].startswith("COVERAGE INCOMPLETE: 2 of 3")
    assert "{'ok': True" not in tekst and "'treffers'" not in tekst


def test_inhoud_tekst_zonder_records_geeft_compacte_json_en_respecteert_de_cap():
    assert pv.inhoud_tekst({"score": 88, "lcp_ms": 3200}) == '{"score": 88, "lcp_ms": 3200}'
    lang = {"hits": [{"title": f"T{i}", "abstract": "a" * 500} for i in range(30)]}
    tekst = pv.inhoud_tekst(lang)
    assert len(tekst) <= pv._DELIVERABLE_CAP + 20 and "… and 22 more record(s)" in tekst
    assert pv.inhoud_tekst({"_truncated": True, "preview": "x" * 10}) == "x" * 10


def test_deliverable_blokken_gebruikt_de_kop_van_de_note_en_de_records_uit_de_inhoud():
    r = _web_zoek_result(n_gelezen=1, n_totaal=1)
    r["treffers"][0]["extract"] = "The extract."
    summary = ("📎 Find hot melts — via web_zoek · usable (1)\n➜ One product found.\n"
               "• titel: Page 0 | extract: The extract. | url: https://example.org/0")

    class Store:
        def for_project(self, pid):
            return [{"id": "d1", "summary": summary}]

        def content_for(self, rid):
            return r
    blok = pv.deliverable_blokken(Store(), "p1")[0]
    assert blok.startswith("📎 Find hot melts — via web_zoek · usable (1)\n➜ One product found.")
    assert "• Page 0 (https://example.org/0) — The extract." in blok
    assert blok.count("The extract.") == 1                                  # niet dubbel (note én inhoud)
    assert "{'ok'" not in blok


def test_deliverable_blokken_zonder_records_houdt_de_oude_vorm():
    class Store:
        def for_project(self, pid):
            return [{"id": "d1", "summary": "📎 Audit — via mobiel_audit"}]

        def content_for(self, rid):
            return {"score": 45}
    blok = pv.deliverable_blokken(Store(), "p1")[0]
    assert blok == '📎 Audit — via mobiel_audit\n  {"score": 45}'


@pytest.mark.parametrize("inhoud", [None, "", {}])
def test_deliverable_blokken_zonder_inhoud_is_alleen_de_note(inhoud):
    class Store:
        def for_project(self, pid):
            return [{"id": "d1", "summary": "📎 X"}]

        def content_for(self, rid):
            return inhoud
    assert pv.deliverable_blokken(Store(), "p1") == ["📎 X"]
