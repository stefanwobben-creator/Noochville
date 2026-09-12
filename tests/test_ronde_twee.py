"""Scope 51b (12 september 2026) — ronde twee: de namen uit de vondsten nalopen, als voorstel.

Wat hieronder vastligt:

1. het materiaal komt uit de deliverables (met extracten) of, zonder store, uit de oogst van de puls;
2. de leads komen uit één modelronde, ontdubbeld en gecapt, met de criteria van de opdracht; een
   verzonnen url wordt leeg (de skill zoekt dan zelf);
3. per lead één `lead_beoordeling`-item met naam, url, vraag, opdracht en criteria;
4. in de uitvoerlus: pas als de lijst af is, één keer, als voorstel (akkoord=False), de rol werkt
   daarna díe lijst, en het project gaat nog niet naar review; zonder leads, zonder skill, uitgezet
   of ná review: gewoon naar review zoals altijd;
5. het verslag toont een beoordeling met oordeel en citaat.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import project_verslag as pv
from nooch_village import ronde_twee as rt
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger, plan_wacht_op_akkoord, uitvoerlijst
from nooch_village.skills import Skill, SkillRegistry

TODAY = "2026-09-12"
LANG = "Kiilto Biomelt is the world's first biodegradable hot melt adhesive. " * 12


def _web_zoek_result():
    return {"ok": True, "term": "bio-based hot melt", "bron": "serpapi", "aantal_treffers": 2,
            "treffers": [{"titel": "Kiilto Biomelt", "url": "https://www.kiilto.com/industry/kiilto-biomelt/",
                          "domein": "kiilto.com", "fragment": "s", "tekst": LANG, "gelezen": True,
                          "extract": "Kiilto Biomelt is a biodegradable hot melt for packaging (product page)."},
                         {"titel": "Bio-based glues for natural bonding", "url": "https://www.acib.at/bio-based-glues/",
                          "domein": "acib.at", "fragment": "s", "tekst": LANG, "gelezen": True,
                          "extract": "acib (Graz) developed an enzymatic lignin glue at TRL 4 (institute)."}],
            "gelezen": 2, "volledig_gelezen": True, "text": "…"}


LEADS_ANTWOORD = {"leads": [{"naam": "Kiilto Biomelt", "soort": "product",
                             "url": "https://www.kiilto.com/industry/kiilto-biomelt/", "waarom": "biodegradable hot melt"},
                            {"naam": "acib", "soort": "institute", "url": "", "waarom": "lignin glue, seeks partners"},
                            {"naam": "acib", "soort": "institute", "url": "", "waarom": "dubbel"},
                            {"naam": "Ghost Corp", "soort": "company", "url": "PLACEHOLDER", "waarom": "x"}],
                  "criteria": ["plastic-free", "vegan", "proven in footwear", "Vegan"]}


# ── 1 en 2: materiaal en leads ───────────────────────────────────────────────

def test_materiaal_uit_resultaten_rendert_records_met_extract_en_partijen():
    m = rt.materiaal_uit_resultaten([("Search the web", _web_zoek_result()),
                                     ("Patents", {"patents": [{"title": "Shoe sole", "applicants": ["ASICS CORP"]}]}),
                                     ("Audit", {"score": 45})])
    assert "[Search the web]" in m and "• Kiilto Biomelt — <https://www.kiilto.com/industry/kiilto-biomelt/> — Kiilto Biomelt is a biodegradable" in m
    assert "• Shoe sole — applicants: ASICS CORP" in m
    assert "[Audit]" not in m                                        # geen records → geen materiaal
    assert rt.materiaal_uit_resultaten([]) == ""


def test_materiaal_uit_store_leest_de_deliverables_fail_soft():
    class Store:
        def for_project(self, pid):
            return [{"id": "d1", "title": "Search", "skill": "web_zoek"}, {"id": "d2", "title": "T", "skill": "x"}]

        def content_for(self, rid):
            return _web_zoek_result() if rid == "d1" else {"_truncated": True, "preview": "…"}
    m = rt.materiaal_uit_store(Store(), "p1")
    assert "[Search]" in m and "Kiilto Biomelt" in m and "[T]" not in m

    class Stuk:
        def for_project(self, pid):
            raise RuntimeError("stuk")
    assert rt.materiaal_uit_store(Stuk(), "p1") == "" and rt.materiaal_uit_store(None, "p1") == ""


def test_leads_uit_ontdubbelt_capt_en_leegt_een_verzonnen_url():
    gezien = {}

    def _model(prompt, **k):
        gezien["p"], gezien["k"] = prompt, k
        return json.dumps(LEADS_ANTWOORD)
    leads, criteria = rt.leads_uit("Glue-free joining", "plastic-free and vegan", "materiaal",
                                   reason_fn=_model, max_leads=3)
    assert [l["naam"] for l in leads] == ["Kiilto Biomelt", "acib", "Ghost Corp"]
    assert leads[0]["url"].startswith("https://") and leads[2]["url"] == ""     # placeholder → leeg
    assert criteria == ["plastic-free", "vegan", "proven in footwear"]          # 'Vegan' is een dubbel
    assert gezien["k"]["call_site"] == "ronde_twee_leads"
    assert "GOAL: Glue-free joining" in gezien["p"] and "Skip the project owner's own brand" in gezien["p"]


def test_leads_uit_is_fail_soft():
    def _stuk(*a, **k):
        raise RuntimeError("geen krediet")
    assert rt.leads_uit("g", "d", "materiaal", reason_fn=_stuk) == ([], [])
    assert rt.leads_uit("g", "d", "materiaal", reason_fn=lambda *a, **k: "geen json") == ([], [])
    assert rt.leads_uit("g", "d", "", reason_fn=lambda *a, **k: 1 / 0) == ([], [])   # zonder materiaal geen vraag


# ── 3: de items ──────────────────────────────────────────────────────────────

def test_plan_items_een_beoordeling_per_lead():
    items = rt.plan_items([{"naam": "acib", "soort": "institute", "url": "", "waarom": "lignin glue"}],
                          "Glue-free joining", "plastic-free", ["plastic-free", "vegan"])
    assert items == [{"text": "Assess lead: acib (institute)", "skill": "lead_beoordeling",
                      "payload": {"naam": "acib", "url": "", "vraag": "Glue-free joining",
                                  "opdracht": "plastic-free", "criteria": ["plastic-free", "vegan"]},
                      "reason": "lignin glue"}]


# ── 4: in de uitvoerlus ──────────────────────────────────────────────────────

class _ZoekSkill(Skill):
    name = "web_zoek"
    description = "fake"

    def run(self, payload, context):
        return _web_zoek_result()


class _BeoordelingSkill(Skill):
    name = "lead_beoordeling"
    description = "fake"

    def run(self, payload, context):
        return {"ok": True, "naam": payload.get("naam"), "oordeel": "high",
                "beoordeling": [{"criterium": "what is this", "oordeel": "institute", "citaat": ""},
                                {"criterium": "plastic-free", "oordeel": "yes", "citaat": "no plastic"}]}


def _inw(tmp_path, ledger, skills=("web_zoek", "lead_beoordeling"), store=None):
    reg = SkillRegistry()
    reg.register(_ZoekSkill())
    reg.register(_BeoordelingSkill())
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=list(skills)), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", "lees_extract_enabled": "0",
                                    "deliverable_conclusie_enabled": "0"},
                          rugzakken={}, data_dir=str(tmp_path), projects=ledger, records=None)
    if store is not None:
        ctx.deliverables = store
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


def _model_met_leads(prompt, **k):
    if k.get("call_site") == "ronde_twee_leads":
        return json.dumps(LEADS_ANTWOORD)
    return ""


def _project(ledger):
    pid = ledger.create("harry_hemp", "Glue-free joining", "human", status="running",
                        description="plastic-free and vegan")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Search the web", skill="web_zoek", payload={"term": "bio glue"})
    return pid, cl["id"]


def test_lijst_af_geeft_ronde_twee_als_voorstel_en_nog_geen_review(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", _model_met_leads)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, clid = _project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "running" and not p.get("review_raised")      # geen review-gate
    assert len(p["checklists"]) == 2
    twee = p["checklists"][1]
    assert twee["title"] == rt.TITEL and twee["ronde_twee_van"] == clid and twee["akkoord"] is False
    assert uitvoerlijst(p)["id"] == twee["id"] and plan_wacht_op_akkoord(twee)
    namen = [it["payload"]["naam"] for it in twee["items"]]
    assert namen == ["Kiilto Biomelt", "acib", "Ghost Corp"] and all(it["skill"] == "lead_beoordeling" for it in twee["items"])
    assert twee["items"][0]["payload"]["criteria"] == ["plastic-free", "vegan", "proven in footwear"]
    assert twee["items"][0]["payload"]["vraag"] == "Glue-free joining"
    logtxt = " ".join(e["text"] for e in p.get("log", []))
    assert "🔁 Round one done as far as I can take it. Names worth a closer look: Kiilto Biomelt, acib, Ghost Corp" in logtxt
    assert "Checklist complete" not in logtxt


def test_ronde_twee_wacht_op_akkoord_en_draait_daarna_naar_review(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", _model_met_leads)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, _ = _project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    twee = ledger.get(pid)["checklists"][1]
    inw._execute_checklist(ledger.get(pid), "2026-09-13")              # wacht op akkoord: niets
    assert not any(it.get("done") for it in ledger.get(pid)["checklists"][1]["items"])
    assert ledger.plan_akkoord(pid, twee["id"], door="stefan") is True      # de mens klikt go ahead
    inw._execute_checklist(ledger.get(pid), "2026-09-14")
    p = ledger.get(pid)
    assert all(it.get("done") for it in p["checklists"][1]["items"])
    assert p["status"] == "blocked" and p["blocked_on"] == "review"     # nu wél de review-gate
    assert len(p["checklists"]) == 2                                     # geen ronde drie
    logtxt = " ".join(e["text"] for e in p.get("log", []))
    assert "Assess lead: Kiilto Biomelt" in logtxt and "plastic-free | oordeel: yes" in logtxt


def test_zonder_leads_gewoon_naar_review(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: json.dumps({"leads": [], "criteria": []}))
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, _ = _project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review" and len(p["checklists"]) == 1


def test_zonder_de_skill_of_uitgezet_geen_ronde_twee(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", _model_met_leads)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    # de rol heeft lead_beoordeling niet
    inw = _inw(tmp_path, ledger, skills=("web_zoek",))
    pid, _ = _project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    assert ledger.get(pid)["blocked_on"] == "review" and len(ledger.get(pid)["checklists"]) == 1
    # uitgezet
    inw2 = _inw(tmp_path, ledger)
    inw2.context.settings["ronde_twee_enabled"] = "0"
    pid2, _ = _project(ledger)
    inw2._execute_checklist(ledger.get(pid2), TODAY)
    assert len(ledger.get(pid2)["checklists"]) == 1


def test_een_project_terug_van_review_mag_zijn_leads_alsnog_nalopen(tmp_path, monkeypatch):
    """`review_raised` is geen rem: die vlag wist elke item-toggle, en een project dat de mens
    terugstuurde omdat het verslag te dun was, is precies het project dat ronde twee nodig heeft.
    De rem is `ronde_twee_van`: één keer."""
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", _model_met_leads)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    pid, clid = _project(ledger)
    ledger.mark_awaiting_review(pid)                                     # ooit naar review geweest
    ledger.unblock(pid)                                                  # de mens sleept hem terug naar Active
    assert ledger.get(pid)["status"] == "running" and ledger.get(pid).get("review_raised")
    inw._execute_checklist(ledger.get(pid), TODAY)
    assert len(ledger.get(pid)["checklists"]) == 2


def test_materiaal_komt_uit_de_store_als_die_er_is(tmp_path, monkeypatch):
    """Ook wat op een eerdere dag gelezen is telt mee: de store, niet alleen de oogst van vandaag."""
    import nooch_village.llm as llm
    from nooch_village.deliverable_store import DeliverableStore
    gezien = {}

    def _model(prompt, **k):
        if k.get("call_site") == "ronde_twee_leads":
            gezien["p"] = prompt
            return json.dumps({"leads": [{"naam": "acib", "soort": "institute", "url": "", "waarom": "w"}],
                               "criteria": []})
        return ""
    monkeypatch.setattr(llm, "reason", _model)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    store = DeliverableStore(str(tmp_path / "deliverables.json"))
    inw = _inw(tmp_path, ledger, store=store)
    pid, _ = _project(ledger)
    store.add(project_id=pid, role="harry_hemp", skill="epo_patents", checklist_item="x", title="Patents",
              content={"patents": [{"title": "Stitched sole", "applicants": ["Vivobarefoot Ltd"]}]}, summary="s")
    inw._execute_checklist(ledger.get(pid), TODAY)
    assert "[Patents]" in gezien["p"] and "Vivobarefoot Ltd" in gezien["p"]
    assert "[Search the web]" in gezien["p"]                             # de oogst van vandaag staat er ook


def test_ronde_twee_max_capt_het_aantal_leads(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    gezien = {}

    def _model(prompt, **k):
        gezien["p"] = prompt
        return json.dumps(LEADS_ANTWOORD)
    monkeypatch.setattr(llm, "reason", _model)
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    inw = _inw(tmp_path, ledger)
    inw.context.settings["ronde_twee_max"] = "2"
    pid, _ = _project(ledger)
    inw._execute_checklist(ledger.get(pid), TODAY)
    assert len(ledger.get(pid)["checklists"][1]["items"]) == 2 and "at most 2 leads" in gezien["p"]


# ── 5: het verslag ───────────────────────────────────────────────────────────

def test_verslag_toont_een_beoordeling_met_oordeel_en_citaat():
    inhoud = {"ok": True, "naam": "nahtur-design", "oordeel": "high",
              "beoordeling": [{"criterium": "what is this", "oordeel": "German barefoot brand", "citaat": ""},
                              {"criterium": "plastic-free", "oordeel": "yes",
                               "citaat": "Die Sohle besteht aus Eco-Rubber."},
                              {"criterium": "fit", "oordeel": "high — stitched on natural rubber",
                               "citaat": "Die Schuhe sind rahmengenäht.", "volgende_stap": "contact"}]}
    t = pv.inhoud_tekst(inhoud)
    assert "• what is this — German barefoot brand" in t
    assert "• plastic-free — yes — “Die Sohle besteht aus Eco-Rubber.”" in t
    assert "• fit — high — stitched on natural rubber — “Die Schuhe sind rahmengenäht.” (next: contact)" in t
