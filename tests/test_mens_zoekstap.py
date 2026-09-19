"""Scope 50c (12 september 2026) — de zoekopdrachten voor de mens staan op het project.

Stefan: "als dit niet automatisch kan, is het ook prima dat je in het project een prompt voorstelt.
Bijv. ga naar Google en typ dit in, of vul deze prompt in in Gemini." Wat hieronder vastligt:

1. een onderzoeksplan (een zoekstap met een term) krijgt één mens-taak erbij, deterministisch;
2. de queries komen uit het plan zelf (open web eerst, dan de brede vorm, dan de corpus-termen);
3. het wall-bericht draagt de queries en de deep-research-prompt met het doel en de opdracht, en
   past binnen de bericht-cap;
4. via `prepare_project`: het item telt niet mee voor done, het bericht staat op de wall, een plan
   zonder zoekstap krijgt niets, en het plan wordt er geen mens-project van.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village import mens_zoekstap as mz
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger, checklist_progress
from nooch_village.skills import SkillRegistry

PLAN = [
    {"text": "trade", "skill": "web_zoek", "payload": {"term": "bio-based hot melt adhesive footwear"}},
    {"text": "buyer", "skill": "web_zoek", "payload": {"term": "glue-free sneakers"}},
    {"text": "market", "skill": "web_zoek", "payload": {"term": "plastikfrei Barfußschuhe rahmengenäht",
                                                        "taal": "de", "land": "de"}},
    {"text": "papers", "skill": "openalex_evidence", "payload": {"term": "adhesives footwear"}},
    {"text": "call", "skill": None, "payload": {}, "kind": "human_external", "reason": "phone"},
]


# ── 1 en 2: het item en de queries ───────────────────────────────────────────

def test_onderzoeksplan_krijgt_een_mens_item():
    it = mz.item_voor_de_mens(PLAN)
    assert it and it["skill"] is None and it["kind"] == "human_external" and it["text"].startswith("🔎")
    assert mz.item_voor_de_mens([{"text": "x", "skill": "content_schrijven", "payload": {"onderwerp": "y"}}]) is None
    assert mz.item_voor_de_mens([]) is None
    assert mz.item_voor_de_mens(PLAN + [mz.item_voor_de_mens(PLAN)]) is None       # niet dubbel


def test_een_zoekstap_zonder_term_is_geen_onderzoek():
    assert not mz.is_onderzoeksplan([{"text": "x", "skill": "web_zoek", "payload": {}}])
    assert mz.is_onderzoeksplan([{"text": "x", "skill": "epo_patents", "query": "shoe sole"}])   # legacy query


def test_queries_komen_uit_het_plan_open_web_eerst_dan_breed_dan_corpus():
    q = mz.queries(PLAN)
    assert q[:3] == ["bio-based hot melt adhesive footwear", "glue-free sneakers",
                     "plastikfrei Barfußschuhe rahmengenäht"]
    assert "adhesives footwear" in q
    assert len(q) == len({x.lower() for x in q}) <= mz.MAX_QUERIES


def test_queries_bevatten_de_brede_vorm_van_een_te_smalle_term():
    items = [{"text": "t", "skill": "web_zoek",
              "payload": {"term": "Savon de Potasse fabricant fournisseur Europe savon liquide industriel"}}]
    q = mz.queries(items)
    assert q[0].startswith("Savon de Potasse fabricant") and q[1] == "Savon de Potasse"


def test_queries_ontdubbelen_en_cappen():
    items = [{"text": "t", "skill": "web_zoek", "payload": {"term": f"term {i % 4}"}} for i in range(12)]
    q = mz.queries(items)
    assert q == ["term 0", "term 1", "term 2", "term 3"]
    items = [{"text": "t", "skill": "web_zoek", "payload": {"term": f"term {i}"}} for i in range(12)]
    assert len(mz.queries(items)) == mz.MAX_QUERIES


# ── 3: het bericht ───────────────────────────────────────────────────────────

def test_bericht_draagt_queries_prompt_doel_en_opdracht():
    b = mz.bericht_voor_de_mens("Glue-free bio-based joining for our sneakers",
                                "Must be plastic-free and vegan.", mz.queries(PLAN))
    assert b.startswith(mz.MARKER)
    assert "   • bio-based hot melt adhesive footwear" in b and "   • plastikfrei Barfußschuhe rahmengenäht" in b
    assert "Research this: Glue-free bio-based joining for our sneakers." in b
    assert "The assignment: Must be plastic-free and vegan." in b
    assert "three vocabularies" in b and "'unknown' is a valid answer" in b
    assert b.endswith("the role reads them in the next round.")
    assert len(b) <= mz._MAX_BERICHT


def test_bericht_blijft_binnen_de_cap_bij_een_lange_opdracht():
    b = mz.bericht_voor_de_mens("doel", "opdracht " * 400, mz.queries(PLAN))
    assert len(b) <= mz._MAX_BERICHT and "   • glue-free sneakers" in b and "Paste this into Gemini" in b


# ── 4: via prepare_project ───────────────────────────────────────────────────

def _inw(tmp_path, ledger, skills=("web_zoek", "openalex_evidence")):
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=list(skills)), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", "deliverable_context_enabled": "0"},
                          rugzakken={}, data_dir=str(tmp_path), projects=ledger, records=None)
    return Inhabitant(rec, EventBus(name="t"), SkillRegistry(), ctx)


def _plan_antwoord(items):
    import json
    return json.dumps({"deliverable": "d", "accountability": "a", "items": items})










# ── en via de wizard, de andere weg naar het bord ────────────────────────────

def test_de_wizard_zet_de_mens_zoekstap_ook_op_het_project(tmp_path, monkeypatch):
    """De daemon zet hem bij het voorbereiden; een project uit de wizard heeft zijn checklist al en
    wordt niet meer voorbereid. Zonder deze regel had een wizard-onderzoek geen queries voor de mens."""
    import json
    from tests.test_wizard import _post, _st
    from nooch_village import cockpit2
    monkeypatch.setattr("nooch_village.llm.reason", lambda *a, **k: "")
    st = _st(tmp_path)
    rid = "mother_earth__nooch__website_developer"
    wie = f"person:{st.people.all()[0].id}"
    items = [{"tekst": "search the web for bio-based glues", "skill": "web_zoek",
              "payload": {"term": "bio-based glue footwear"}, "ok": True},
             {"tekst": "call a supplier", "skill": None, "payload": {}, "ok": False}]
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Glue-free joining", "trekker": wie,
                                        "items": json.dumps(items)})
    p = cockpit2._Stores(st.dd).projects.get(r["pid"])
    cl = p["checklists"][0]["items"]
    assert [it["text"][:1] for it in cl] == ["s", "c", "🔎"] and cl[2]["human_task"] is True
    assert checklist_progress(cl) == (0, 2)
    bericht = next(e["text"] for e in p["log"] if e["text"].startswith(mz.MARKER))
    assert "   • bio-based glue footwear" in bericht and "Research this: Glue-free joining." in bericht
    # zonder zoekstap: niets extra's
    r2 = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Header af", "trekker": wie,
                                         "items": json.dumps([items[1]])})
    p2 = cockpit2._Stores(st.dd).projects.get(r2["pid"])
    assert len(p2["checklists"][0]["items"]) == 1
