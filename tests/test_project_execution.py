"""Uitvoer-primitief (Fase 1): TOEKOMST=voorbereiden, ACTIEF=uitvoeren, DONE=af. Thread-vrij.
Dekt: voorbereiding genereert een skill-gekoppelde checklist zonder uit te voeren; uitvoering vinkt af met
een note; alleen alles-af → DONE; ACTIEF zonder checklist → signaal (geen valse done); idempotentie;
skill-fout → item open + reden."""
from __future__ import annotations
import pytest
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger

TODAY = "2026-07-08"


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill (term → hits)"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        if term == "boom":
            raise RuntimeError("API kapot")
        if term == "leeg":
            return {"term": term, "total": 0, "no_data": True, "reason": "niets gevonden", "hits": []}
        return {"term": term, "total": 2,
                "hits": [{"title": f"Study on {term}", "year": 2021, "citations": 7, "topic": "footwear"}]}


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def _inhabitant(tmp_path, ledger, skills=("openalex_evidence",)):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="waarheid",
                                           accountabilities=["research studies by openalex, delivering evidence"],
                                           domains=[], skills=list(skills)), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _prep(ledger, pid, items):
    """items: list van (text, skill|None, query, reason)."""
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for text, skill, query, reason in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query, reason=reason)
    return cl


# a. TOEKOMST → checklist gegenereerd (skill-gekoppeld of open-met-reden); project NIET uitgevoerd
def test_a_voorbereiding_genereert_checklist(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    plan = ('{"deliverable":"evidence-dossier","accountability":"research studies","items":['
            '{"text":"wetenschappelijke studies","skill":"openalex_evidence","query":"barefoot shoes","reason":""},'
            '{"text":"patenten","skill":null,"query":"","reason":"geen patent-skill"}]}')
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (plan, "mock") if k.get("return_tier") else plan)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "Patents and scientific studies on barefoot shoes", "human", status="future")
    inh.prepare_project(pid)
    p = ledger.get(pid)
    assert p["status"] == "future"                                   # niet uitgevoerd, blijft TOEKOMST
    cl = inh._project_checklist(p)
    assert cl and len(cl["items"]) == 2
    skilled = [it for it in cl["items"] if it.get("skill")]
    open_it = [it for it in cl["items"] if not it.get("skill")]
    assert skilled[0]["skill"] == "openalex_evidence" and skilled[0]["query"] == "barefoot shoes"
    assert open_it[0]["reason"] == "geen patent-skill"


def test_a2_voorgestelde_skill_buiten_dna_wordt_geen_skill(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    plan = '{"deliverable":"x","items":[{"text":"t","skill":"patent_api","query":"q","reason":""}]}'
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (plan, "mock") if k.get("return_tier") else plan)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="future")
    inh.prepare_project(pid)
    it = inh._project_checklist(ledger.get(pid))["items"][0]
    assert it.get("skill") is None and "niet in DNA" in it["reason"]   # machine-check tegen DNA


def test_a3_geen_llm_geen_checklist_blijft_toekomst(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (None, None) if k.get("return_tier") else None)  # geen key → None
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="future")
    inh.prepare_project(pid)
    p = ledger.get(pid)
    assert inh._project_checklist(p) is None and p["status"] == "future"   # geen valse voorbereiding


# b. ACTIEF met checklist → afvinkbaar item uitgevoerd, note per item, afgevinkt
def test_b_uitvoering_vinkt_af_met_note(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("studies", "openalex_evidence", "barefoot", "")])
    inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert inh._project_checklist(p)["items"][0]["done"] is True
    logtxt = " ".join(e["text"] for e in p.get("log", []))
    assert "Study on barefoot" in logtxt                              # de deliverable-note


# c. alle items af → DONE; open item → blijft ACTIEF (eerlijke voortgang)
def test_c_alle_af_done_open_blijft_actief(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    pid1 = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid1, [("s", "openalex_evidence", "x", "")])
    inh._claim_run_complete(pid1)
    p1 = ledger.get(pid1)
    assert p1["status"] == "blocked" and p1["blocked_on"] == "review"  # review-gate: alles af → WACHT, niet done

    pid2 = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid2, [("s", "openalex_evidence", "x", ""), ("p", None, "", "geen patent-skill")])
    inh._claim_run_complete(pid2)
    p2 = ledger.get(pid2)
    assert p2["status"] != "done"                                     # open item → blijft ACTIEF
    cl2 = inh._project_checklist(p2)
    assert sum(1 for it in cl2["items"] if it.get("done")) == 1 and len(cl2["items"]) == 2   # 1/2


# d. ACTIEF zonder checklist → signaal, geen uitvoering, geen stub:done
def test_d_geen_checklist_signaal_geen_valse_done(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    signals = []
    inh.bus.subscribe("project_needs_preparation", lambda e: signals.append(e.data))
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    inh._claim_run_complete(pid)
    p = ledger.get(pid)
    assert p["status"] != "done" and p.get("outcome") != "stub:done"
    assert signals and signals[0]["project_id"] == pid                # luid signaal


# e. idempotent: tweede puls dezelfde dag dupliceert niets
def test_e_idempotent_tweede_puls(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("s", "openalex_evidence", "x", ""), ("p", None, "", "geen skill")])
    inh._execute_checklist(ledger.get(pid), TODAY)
    n1 = len(ledger.get(pid).get("log", []))
    inh._execute_checklist(ledger.get(pid), TODAY)                    # tweede puls zelfde dag
    assert len(ledger.get(pid).get("log", [])) == n1                  # geen dubbele notes


# f. skill-fout → item open + reden zichtbaar, geen stille skip
def test_f_skill_fout_item_open_met_reden(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("boom-item", "openalex_evidence", "boom", "")])
    inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert inh._project_checklist(p)["items"][0]["done"] is False     # blijft open
    logtxt = " ".join(e["text"] for e in p.get("log", []))
    assert "niet gelukt" in logtxt                                    # reden in de note, geen stille skip


# h. ledger: fail-teller optellen en resetten
def test_h_note_en_reset_item_fails(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, "cl")
    ledger.check_add(pid, cl["id"], "item", skill="openalex_evidence")
    iid = ledger.get(pid)["checklists"][0]["items"][0]["id"]
    assert ledger.note_item_fail(pid, cl["id"], iid) == 1
    assert ledger.note_item_fail(pid, cl["id"], iid) == 2
    ledger.reset_item_fails(pid, cl["id"], [iid])
    assert (ledger.get(pid)["checklists"][0]["items"][0].get("fails") or 0) == 0


# i. vastgelopen item → na de retry-grens naar WAITING met een concrete hulpvraag (niet eeuwig ACTIEF)
def test_i_vastgelopen_na_grens_naar_waiting(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: "Kan iemand een alternatieve bron voor 'boom' aandragen?")
    inh = _inhabitant(tmp_path, ledger)
    inh.context.settings["item_fail_limit"] = "3"
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("boom-item", "openalex_evidence", "boom", "")])
    events = []
    inh.bus.subscribe("project_stuck", lambda e: events.append(e.data))

    for day in ("2026-07-08", "2026-07-09"):                       # 2 pogingen < grens 3
        inh._execute_checklist(ledger.get(pid), day)
    p = ledger.get(pid)
    assert p["status"] == "queued" and p["checklists"][0]["items"][0]["fails"] == 2

    inh._execute_checklist(ledger.get(pid), "2026-07-10")          # 3e poging → grens geraakt → WAITING
    p = ledger.get(pid)
    assert p["status"] == "blocked" and "wacht op antwoord" in (p.get("blocked_on") or "")
    assert p["checklists"][0]["items"][0]["fails"] == 0            # gereset → verse pogingen na reactivering
    assert events and events[-1]["vraag"] and events[-1]["items"] == 1
    logtxt = " ".join(e["text"] for e in p.get("log", []))
    assert "⏸️" in logtxt and "alternatieve bron" in logtxt        # de concrete hulpvraag staat op de wall


# j. grens 0 zet de klep uit → eeuwig herproberen (ongewijzigd oud gedrag)
def test_j_grens_nul_zet_klep_uit(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    inh.context.settings["item_fail_limit"] = "0"
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("boom-item", "openalex_evidence", "boom", "")])
    for day in ("2026-07-08", "2026-07-09", "2026-07-10"):
        inh._execute_checklist(ledger.get(pid), day)
    assert ledger.get(pid)["status"] == "queued"                  # nooit geblokkeerd, blijft ACTIEF


# g. skill uitgevoerd maar leeg → item AF (no-data is een uitkomst), 📭 op de wall zodat de mens kan
#    beoordelen of het project klaar is (De Kroniek B3: leeg is een feit, geen mislukking).
def test_g_leeg_is_afgerond_op_de_wall(tmp_path, ledger):
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    _prep(ledger, pid, [("leeg-item", "openalex_evidence", "leeg", "")])
    inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert inh._project_checklist(p)["items"][0]["done"] is True      # leeg = uitgevoerd → afgevinkt
    logtxt = " ".join(e["text"] for e in p.get("log", []))
    assert "📭" in logtxt and "geen resultaat" in logtxt              # wegschreven op de wall
    assert "niet gelukt" not in logtxt                               # geen ⚠️: het is geen mislukking


# ── fix-brief: active-without-checklist herstel + zichtbare founder-escalatie ──

def test_tend_prepareert_actief_zonder_checklist(tmp_path, ledger, monkeypatch):
    """Root cause: een project dat ACTIEF werd zonder voorbereide checklist zat permanent stil
    (prepare_project weigerde niet-future). De tend bereidt het nu alsnog voor én voert het uit."""
    import nooch_village.llm as llm
    plan = ('{"deliverable":"dossier","items":['
            '{"text":"studies","skill":"openalex_evidence","query":"barefoot","reason":""}]}')
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (plan, "mock") if k.get("return_tier") else plan)
    inh = _inhabitant(tmp_path, ledger)
    # simuleer een bord-drag: project staat 'running' zonder checklist
    pid = ledger.create("harry_hemp", "onderzoek barefoot", "human", status="queued")
    ledger.start(pid)
    assert ledger.get(pid)["status"] == "running" and inh._project_checklist(ledger.get(pid)) is None
    inh._tend_projects(None)                                   # de dagelijkse verzorging
    p = ledger.get(pid)
    cl = inh._project_checklist(p)
    assert cl is not None and cl["items"][0]["done"] is True   # voorbereid ÉN uitgevoerd


def test_prepare_project_verruimd_voor_actief_zonder_checklist(tmp_path, ledger, monkeypatch):
    import nooch_village.llm as llm
    plan = '{"deliverable":"x","items":[{"text":"t","skill":"openalex_evidence","query":"q","reason":""}]}'
    monkeypatch.setattr(llm, "reason", lambda *a, **k: (plan, "mock") if k.get("return_tier") else plan)
    inh = _inhabitant(tmp_path, ledger)
    pid = ledger.create("harry_hemp", "doel", "human", status="queued")
    ledger.start(pid)                                          # → running, geen checklist
    inh.prepare_project(pid)
    assert inh._project_checklist(ledger.get(pid)) is not None
    # idempotent: mét checklist doet prepare niets (geen tweede checklist)
    inh.prepare_project(pid)
    assert len(ledger.get(pid).get("checklists", [])) == 1


def test_means_gap_escaleert_zichtbaar_naar_founder(tmp_path):
    """Taak 2: een means-gap zet nu óók een heads-up-notificatie voor de founder (geen approve-knop)."""
    from nooch_village.human_inbox import HumanInbox, FOUNDER_ROLE_ID
    from nooch_village.notifications import NotifStore
    hi = HumanInbox(str(tmp_path / "human_inbox.json"))
    hi.add_means_gap("skill_ladder:openalex", "Skill-ladder uitgeput voor 'barefoot'",
                     role_id="harry_hemp", sensed_by="harry_hemp")
    notif = NotifStore(str(tmp_path / "notifications.json"))
    fnd = notif.for_targets([("role", FOUNDER_ROLE_ID)])
    assert len(fnd) == 1
    assert "Capaciteit ontbreekt" in fnd[0]["snippet"] and "nooch_village.inbox" in fnd[0]["snippet"]
    assert "approve" not in fnd[0]["snippet"].lower()          # heads-up, geen beslis-knop
    # dedup: dezelfde gap opnieuw → geen tweede notificatie
    hi.add_means_gap("skill_ladder:openalex", "nogmaals", role_id="harry_hemp")
    assert len(NotifStore(str(tmp_path / "notifications.json")).for_targets([("role", FOUNDER_ROLE_ID)])) == 1
