"""Scope 52 (12 september 2026) — onderzoek per vraagtype: wat er nog ontbrak na het barefoot-project.

Stefan legde het nieuwe einddocument naast het oude: "Shopify hield ik eruit, wij verkopen nog geen
barefoot schoenen; dit project is om te onderzoeken óf we dat moeten ontwikkelen" en "voor onderzoek
hoeft het niet langs de vijf kernwaarden van Nooch". Wat hieronder vastligt:

1. community_listening geeft de nieuwe observaties zelf mee (het document zei letterlijk "no further
   breakdown ... was provided"); gecapt, de rest staat in de store;
2. het einddocument leest deliverables via dezelfde renderer als het verslag, niet als dict-repr;
3. ronde twee start zodra de rol niets meer zelf kan draaien, ook met open mens-items (de barefoot-
   lijst raakte nooit "af"), en het bericht noemt wat open blijft;
4. een go ahead wist de dagrem, zodat een net goedgekeurde lijst dezelfde dag draait;
5. `topic` (competitor_discover) telt als zoekterm voor de 🔎-stap;
6. de prompts: vraagtype-frame in planner en wizard, geen synthese-stap, geen interne cijfers voor
   iets wat we nog niet doen, en criteria uit de vraag, niet uit merkwaarden.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import mens_zoekstap as mz
from nooch_village import ronde_twee as rt
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger, uitvoerlijst
from nooch_village.skills import Skill, SkillRegistry

TODAY = "2026-09-12"


# ── 1: de observaties reizen mee ─────────────────────────────────────────────

def test_community_listening_geeft_de_observaties_mee(tmp_path, monkeypatch):
    from nooch_village.skills_impl import community_listening as cl
    rijen = [{"platform": "youtube", "permalink": f"https://www.youtube.com/watch?v=v&lc={i}",
              "title": "", "fragment": f"Comment {i}: my feet never felt better", "score": i,
              "context_id": "v", "context_title": "Barefoot review", "query": "barefoot sneakers",
              "query_set_id": "discover:x"} for i in range(35)]

    class _Fetcher:
        def fetch(self, set_id, cfg, context, cache, opts):
            return {"rows": rijen, "refuse": None, "requests": 1, "short": 3}
    monkeypatch.setattr("nooch_village.skills_impl.buzz_fetchers.FETCHERS", {"youtube": _Fetcher()})
    skill = cl.CommunityListeningSkill()
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path), library=None)
    uit = skill.run({"queries": ["barefoot sneakers"], "focus": "barefoot"}, ctx)
    assert uit["ok"] is True and uit["new"] == 35
    assert len(uit["observaties"]) == cl._MAX_OBSERVATIES and uit["observaties_afgekapt"] == 5
    o = uit["observaties"][0]
    # scope 55: `context` heet `title` — de videotitel is de titel van het record, zodat de
    # verslagregel ermee begint i.p.v. met de zoekterm
    assert o == {"platform": "youtube", "title": "Barefoot review",
                 "fragment": "Comment 0: my feet never felt better",
                 "url": "https://www.youtube.com/watch?v=v&lc=0",
                 "score": 0, "query": "barefoot sneakers"}
    # en het verslag/einddocument kan ze lezen: records met titel, adres en strekking
    from nooch_village.project_verslag import inhoud_tekst
    t = inhoud_tekst(uit)
    assert "• Barefoot review (https://www.youtube.com/watch?v=v&lc=0) — Comment 0: my feet never felt better" in t


# ── 2: het einddocument op dezelfde renderer ─────────────────────────────────

def test_einddocument_leest_records_en_geen_dict_repr(tmp_path, monkeypatch):
    from nooch_village import inhabitant as inh
    from nooch_village.deliverable_store import DeliverableStore
    from nooch_village.project_doc_store import ProjectDocStore
    gezien = {}

    def _model(prompt, *, return_tier=False, **k):
        gezien["p"] = prompt
        return ("## Task\nfindings", "mock") if return_tier else "## Task\nfindings"
    monkeypatch.setattr("nooch_village.llm.reason", _model)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    pid = ledger.create("r", "Market potential of barefoot sneakers", "human", status="running")
    store = DeliverableStore(str(tmp_path / "deliverables.json"))
    store.add(project_id=pid, role="r", skill="competitor_discover", checklist_item="x", title="Brands",
              content={"results": [{"brand": "Vivobarefoot", "url": "https://vivobarefoot.com",
                                    "extract": "UK barefoot brand, own retail, from £120."}]},
              summary="📎 Brands — via competitor_discover")
    docs = ProjectDocStore(str(tmp_path))
    ok = inh.synthesize_einddocument(project_docs=docs, deliverables=store, projects=ledger, personas=None,
                                     record=None, settings={}, project=ledger.get(pid), force_final=False,
                                     log=inh.logging.getLogger("t"), data_dir=str(tmp_path))
    assert ok is True
    assert "• Vivobarefoot (https://vivobarefoot.com) — UK barefoot brand, own retail, from £120." in gezien["p"]
    assert "{'results'" not in gezien["p"] and '{"results"' not in gezien["p"]


# ── 3 en 4: ronde twee zodra de rol klaar is, en go ahead wist de dagrem ─────

LEADS = {"leads": [{"naam": "Vivobarefoot", "soort": "brand", "url": "https://vivobarefoot.com", "waarom": "leader"},
                   {"naam": "Xero Shoes", "soort": "brand", "url": "", "waarom": "leader"}],
         "criteria": ["price range", "positioning", "production country"]}


class _DiscoverSkill(Skill):
    name = "competitor_discover"
    description = "fake"

    def run(self, payload, context):
        return {"ok": True, "results": [{"brand": "Vivobarefoot", "url": "https://vivobarefoot.com",
                                         "extract": "UK barefoot brand."},
                                        {"brand": "Xero Shoes", "url": "https://xeroshoes.com",
                                         "extract": "US barefoot brand."}]}


class _BeoordelingSkill(Skill):
    name = "lead_beoordeling"
    description = "fake"

    def run(self, payload, context):
        return {"ok": True, "naam": payload.get("naam"), "oordeel": "high",
                "beoordeling": [{"criterium": "price range", "oordeel": "yes", "citaat": "from £120"}]}


def _inw(tmp_path, ledger):
    reg = SkillRegistry()
    reg.register(_DiscoverSkill())
    reg.register(_BeoordelingSkill())
    rec = Record(id="strategic_lead", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["competitor_discover", "lead_beoordeling"]),
                 source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", "lees_extract_enabled": "0",
                                    "deliverable_conclusie_enabled": "0", "item_fail_limit": "3"},
                          rugzakken={}, data_dir=str(tmp_path), projects=ledger, records=None)
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


def _model(prompt, **k):
    if k.get("call_site") == "ronde_twee_leads":
        return json.dumps(LEADS)
    return ""


def _barefoot_project(ledger):
    """De lijst van 12 september: twee skill-items en twee zonder skill (Shopify, synthese)."""
    pid = ledger.create("strategic_lead", "Determine the long term market potential of barefoot sneakers",
                        "human", status="running", description="we sell no barefoot shoes yet")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Discover competitor brands", skill="competitor_discover",
                     payload={"topic": "barefoot sneaker brands"})
    ledger.check_add(pid, cl["id"], "Cross-check Shopify sales", skill=None, reason="no such data")
    ledger.check_add(pid, cl["id"], "Synthesize all research", skill=None, reason="no skill")
    return pid, cl["id"]


def test_ronde_twee_start_ook_met_open_mens_items(tmp_path, monkeypatch):
    monkeypatch.setattr("nooch_village.llm.reason", _model)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, clid = _barefoot_project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "running"                                      # niet geparkeerd
    assert len(p["checklists"]) == 2 and p["checklists"][1]["ronde_twee_van"] == clid
    assert uitvoerlijst(p)["id"] == p["checklists"][1]["id"]
    assert [it["payload"]["naam"] for it in p["checklists"][1]["items"]] == ["Vivobarefoot", "Xero Shoes"]
    assert p["checklists"][1]["items"][0]["payload"]["criteria"] == ["price range", "positioning", "production country"]
    bericht = next(e["text"] for e in p["log"] if e["text"].startswith("🔁"))
    assert "2 item(s) on the first list stay open for a human: Cross-check Shopify sales; Synthesize all research." in bericht
    # de open items staan nog op de eerste lijst, zichtbaar
    assert [it["done"] for it in p["checklists"][0]["items"]] == [True, False, False]


def test_go_ahead_wist_de_dagrem_en_ronde_twee_draait_dezelfde_dag(tmp_path, monkeypatch):
    monkeypatch.setattr("nooch_village.llm.reason", _model)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, _ = _barefoot_project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    assert ledger.get(pid)["last_tended"] == TODAY
    twee = ledger.get(pid)["checklists"][1]
    assert ledger.plan_akkoord(pid, twee["id"], door="stefan") is True
    assert "last_tended" not in ledger.get(pid)                          # de rem is weg
    inw._execute_checklist(ledger.get(pid), TODAY)                       # zelfde dag: draait wél
    p = ledger.get(pid)
    assert all(it["done"] for it in p["checklists"][1]["items"])
    logtxt = " ".join(e["text"] for e in p["log"])
    assert "Assess lead: Vivobarefoot" in logtxt and "price range | oordeel: yes" in logtxt
    assert p["status"] == "blocked" and p["blocked_on"] == "review"      # ronde twee af → review
    assert len(p["checklists"]) == 2                                     # geen ronde drie


def test_zonder_leads_parkeert_het_project_zoals_altijd(tmp_path, monkeypatch):
    monkeypatch.setattr("nooch_village.llm.reason",
                        lambda p, **k: json.dumps({"leads": [], "criteria": []})
                        if k.get("call_site") == "ronde_twee_leads" else "Can someone check Shopify?")
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, _ = _barefoot_project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "blocked" and "vastgelopen" in (p.get("blocked_on") or "")
    assert len(p["checklists"]) == 1


# ── 5: topic telt als zoekterm ───────────────────────────────────────────────

def test_topic_telt_als_zoekterm_voor_de_mens_zoekstap():
    items = [{"text": "brands", "skill": "competitor_discover", "payload": {"topic": "barefoot sneaker brands"}}]
    assert mz.is_onderzoeksplan(items)
    assert mz.item_voor_de_mens(items) is not None
    assert mz.queries(items) == []                                       # geen open-web/corpus-term: geen query
    items.append({"text": "web", "skill": "web_zoek", "payload": {"term": "barefoot sneakers market size"}})
    assert mz.queries(items) == ["barefoot sneakers market size"]


# ── 6: de prompts ────────────────────────────────────────────────────────────

def test_planner_kent_het_vraagtype_en_plant_geen_synthese(tmp_path, monkeypatch):
    gezien = {}

    def _plan(prompt, **k):
        gezien["p"] = prompt
        a = '{"deliverable":"x","items":[{"text":"t","skill":null,"payload":{},"reason":"r"}]}'
        return (a, "mock") if k.get("return_tier") else a
    monkeypatch.setattr("nooch_village.llm.reason", _plan)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    inw._plan_checklist("Determine the market potential of barefoot sneakers")
    p = gezien["p"]
    assert "RESEARCH FRAME" in p and "An ASSESSMENT" in p
    assert "for something we do not make or sell yet there is nothing internal to check" in p
    assert "NEVER plan a step that synthesizes, summarizes or reports on the other steps" in p
    assert "not by our own brand values unless the assignment names them" in p


def test_wizard_planner_kent_het_vraagtype():
    from nooch_village.wizard import plan_items
    gezien = {}

    def _plan(prompt, **k):
        gezien["p"] = prompt
        return '{"items":[{"tekst":"search the web for market size","skill":null,"payload":{}}]}'
    plan_items("Market potential of barefoot sneakers", [], reason_fn=_plan)
    assert "RESEARCH FRAME" in gezien["p"] and "Never plan a step that synthesizes" in gezien["p"]


def test_ronde_twee_en_lead_beoordeling_oordelen_naar_de_vraag_niet_naar_merkwaarden():
    p = rt._prompt("Market potential of barefoot sneakers", "", "materiaal", 5)
    assert "price range, positioning, materials, production country" in p
    assert "Do not add our own brand values unless the assignment names them" in p
    from nooch_village.skills_impl.lead_beoordeling import _prompt
    q = _prompt("Vivobarefoot", "https://vivobarefoot.com", "Market potential", "", ["price range"], "tekst")
    assert "FIT means how much this lead helps answer the QUESTION" in q
    assert "not by any brand values of your own" in q
