"""Scope 57 — schrijven, denken en overdragen (skill-review batch D, 12 september 2026).

Wat de mens merkt, per skill:

1. escaleer — een BESLISSING blijft open als mens-taak (niet afgevinkt, niet naar review), de vraag
   staat op de wall en de notificatie linkt naar het project; een BEVINDING is alleen nog de tekst.
2. projectverzoek/handoff — 'founder' en een unieke korte rolnaam landen bij de echte rol (één
   lezer, `rol_id_voor`); de planner ziet álle rollen; de tweede uitvoerlijst loopt langs dezelfde
   payload-poort als de eerste.
3. content_schrijven — de draft is het antwoord; geen model is een fout; een 'verified' die de
   kennisbank niet kent wordt bij het plannen geweigerd en bij het schrijven gedegradeerd.
4. bulletin_schrijven / field_note — zonder data wordt niets geschreven of overschreven; de note
   zelf is de inhoud; de Field-Note-ladder krijgt zijn context weer.
5. tegenspraak — het oordeel voorop op wall en verslag; placeholder-bewijs wordt geweigerd.
6. curate / verband_voorstel / kroniek_interpret / weten_we_dit_al / library_lookup — drie oorzaken,
   drie antwoorden: fout, gemeld-leeg, of inhoud; nooit een 'gelukt' met niets erin.
7. Eén ladder-helper voor de vijf schrijf-/oordeel-skills (`llm_keuze.skill_ladder`).
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village import project_verslag
from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.notifications import NotifStore
from nooch_village.projects import ProjectLedger, checklist_progress
from nooch_village.skills import Skill, SkillRegistry, ontbrekende_velden
from nooch_village.skills_impl.escaleer import EscaleerSkill, rol_id_voor

TODAY = "2026-09-12"


# ── gereedschap ──────────────────────────────────────────────────────────────

class _Onderzoek(Skill):
    name = "openalex_evidence"
    cost = "free"
    description = "nep-onderzoek"

    def run(self, payload, context):
        return {"term": payload.get("term"), "hits": [{"title": "Study", "year": 2021}]}


def _rol(tmp_path, ledger, skills, *, records=None, extra_skills=()):
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0",
                                    "deliverable_conclusie_enabled": "0",
                                    "lees_extract_enabled": "0", "ronde_twee_enabled": "0"},
                          data_dir=str(tmp_path), projects=ledger, records=records, rugzakken={})
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="waarheid", accountabilities=["research"],
                                           skills=[s.name for s in skills] + list(extra_skills)),
                 source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _prep(ledger, pid, items):
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for text, skill, payload in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, payload=payload, payload_ok=True)
    return cl


def _items(ledger, pid):
    return ledger.get(pid)["checklists"][0]["items"]


def _wall(ledger, pid) -> str:
    return " ".join(e["text"] for e in ledger.get(pid).get("log", []))


def _records(tmp_path, ids=()):
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="de cirkel")))
    for rid in ids:
        recs.put(Record(id=rid, type=RecordType.ROLE, parent="noochville",
                        definition=RoleDefinition(purpose=f"purpose of {rid}",
                                                  accountabilities=[f"doing {rid}"])))
    return recs


# ── 1. escaleer ──────────────────────────────────────────────────────────────

def test_bevinding_is_alleen_de_tekst(tmp_path):
    r = EscaleerSkill().run({"reden": "no alternative meets the requirements", "aard": "bevinding"},
                            SimpleNamespace(data_dir=str(tmp_path)))
    assert r["text"] == "no alternative meets the requirements"
    assert "samenvatting" not in r
    assert Inhabitant._classify_result(r) == ("gelukt", ("text", "text"))
    assert project_verslag.inhoud_tekst(r) == "no alternative meets the requirements"


def test_beslissing_draagt_de_vraag_en_het_project(tmp_path):
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    with patch("nooch_village.llm.reason", return_value=None):
        r = EscaleerSkill().run({"reden": "drop the elastane requirement: yes or no?",
                                 "naar": "founder", "_project_id": "p-123"}, ctx)
    assert r["wacht_op_mens"] is True and r["aard"] == "beslissing"
    assert r["text"] == "Decision requested from the_source: drop the elastane requirement: yes or no?"
    assert Inhabitant._classify_result(r)[1] == ("text", "text")        # de vraag wint, niet 'aard'
    n = NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "the_source")])
    assert n and n[0]["project_id"] == "p-123"


def test_aard_buiten_de_enum_wordt_bij_het_plannen_geweigerd():
    sk = EscaleerSkill()
    assert sk.validate_payload({"aard": "vraag", "reden": "x"}, None)
    assert sk.validate_payload({"aard": "bevinding", "reden": "x"}, None) == []
    assert sk.validate_payload({"reden": "x"}, None) == []              # leeg: de skill classificeert


def test_beslissing_blijft_open_als_mens_taak_en_gaat_niet_naar_review(tmp_path):
    """DE KERN. Live werden 20 beslissingen afgevinkt alsof de vraag beantwoord was. Nu: het item
    wordt een mens-taak (niet done, niet in de klaar-telling), de vraag staat op de wall, de
    notificatie draagt het project-id, en de volgende puls draait het item niet opnieuw."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    inw = _rol(tmp_path, led, [EscaleerSkill()])
    pid = led.create("harry_hemp", "find an elastane alternative", "human", status="running")
    _prep(led, pid, [("ask the founder", "escaleer",
                      {"aard": "beslissing", "reden": "drop the elastane requirement: yes or no?"})])
    with patch("nooch_village.llm.reason", return_value=None):
        inw._execute_checklist(led.get(pid), TODAY)
    it = _items(led, pid)[0]
    assert it.get("human_task") is True and not it.get("done")
    assert "drop the elastane requirement" in it.get("reason", "")
    assert checklist_progress(led.get(pid)["checklists"][0]) == (0, 0)  # telt niet mee
    p = led.get(pid)
    assert p["status"] == "running" and not p.get("review_raised")       # niet naar review
    assert "⤴" in _wall(led, pid) and "Decision requested from the_source" in _wall(led, pid)
    assert "beslissing\n" not in _wall(led, pid)
    notifs = NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "the_source")])
    assert len(notifs) == 1 and notifs[0]["project_id"] == pid
    # de volgende dag: geen tweede notificatie, het item blijft van de mens
    with patch("nooch_village.llm.reason", return_value=None):
        inw._execute_checklist(led.get(pid), "2026-09-13")
    assert len(NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "the_source")])) == 1


def test_beslissing_naast_afgerond_werk_staat_als_open_mens_taak_in_de_review_melding(tmp_path):
    """Is de rest van de lijst af, dan geldt de bestaande mens-taak-regel: het project meldt zich
    voor review MET de open vraag in de melding ('NOT answered') — niet als schone 2/2."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    inw = _rol(tmp_path, led, [EscaleerSkill(), _Onderzoek()])
    pid = led.create("harry_hemp", "doel", "human", status="running")
    _prep(led, pid, [("studies", "openalex_evidence", {"term": "x"}),
                     ("ask", "escaleer", {"aard": "beslissing", "reden": "which of the two?"})])
    with patch("nooch_village.llm.reason", return_value=None):
        inw._execute_checklist(led.get(pid), TODAY)
    wall = _wall(led, pid)
    assert "human task(s) still open" in wall and "which of the two?" in wall
    assert "NOT answered" in wall


def test_bevinding_in_de_uitvoerlaag_vinkt_af_met_de_tekst_op_de_wall(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    inw = _rol(tmp_path, led, [EscaleerSkill()])
    pid = led.create("harry_hemp", "doel", "human", status="running")
    _prep(led, pid, [("conclude", "escaleer",
                      {"aard": "bevinding", "reden": "no alternative meets the requirements"})])
    inw._execute_checklist(led.get(pid), TODAY)
    assert _items(led, pid)[0]["done"] is True
    wall = _wall(led, pid)
    assert "no alternative meets the requirements" in wall
    assert "vastgelegd als projectuitkomst" not in wall


# ── 2. projectverzoek / handoff / roster / herplan ───────────────────────────

def test_rol_id_voor_kent_aliassen_exacte_ids_en_een_unieke_suffix(tmp_path):
    recs = _records(tmp_path, ["compliance", "mother_earth__nooch__noochville__copywriter",
                               "a__x__editor", "b__y__editor"])
    assert rol_id_voor("founder", recs) == "the_source"
    assert rol_id_voor("The Source", None) == "the_source"
    assert rol_id_voor("compliance", recs) == "compliance"
    assert rol_id_voor("copywriter", recs) == "mother_earth__nooch__noochville__copywriter"
    assert rol_id_voor("mother_earth__nooch__copywriter", recs) == ""   # geen suffix-match, geen gok
    assert rol_id_voor("editor", recs) == ""                            # twee treffers = geen keuze
    assert rol_id_voor("verzonnen", recs) == ""


def test_projectverzoek_en_handoff_lezen_dezelfde_rol(tmp_path):
    from nooch_village.project_items import handoff
    from nooch_village.skills_impl.projectverzoek import ProjectverzoekSkill
    recs = _records(tmp_path, ["compliance", "mother_earth__nooch__noochville__copywriter"])
    ctx = SimpleNamespace(records=recs, projects=ProjectLedger(str(tmp_path / "p.json")))
    sk = ProjectverzoekSkill()
    assert sk.validate_payload({"naar_rol": "founder", "titel": "x"}, ctx) == []
    assert sk.validate_payload({"naar_rol": "copywriter", "titel": "x"}, ctx) == []
    assert sk.validate_payload({"naar_rol": "verzonnen_rol", "titel": "x"}, ctx)
    uit = sk.run({"naar_rol": "copywriter", "titel": "write the FAQ line", "_project_id": "p-1"}, ctx)
    assert uit["ok"] and uit["naar_rol"] == "mother_earth__nooch__noochville__copywriter"
    p = ctx.projects.get(uit["pid"])
    assert p["owner"] == "mother_earth__nooch__noochville__copywriter"
    assert "p-1" in (p.get("links") or [])                              # terugverwijzing
    assert handoff(ctx.projects, "founder", "decide", records=recs)["naar_rol"] == "the_source"
    assert "error" in handoff(ctx.projects, "verzonnen_rol", "x", records=recs)


def test_de_planner_ziet_alle_rollen_niet_de_eerste_achttien(tmp_path, monkeypatch):
    import nooch_village.llm as llm
    ids = [f"rol_{i:02d}" for i in range(26)] + ["mother_earth__nooch__noochville__copywriter"]
    recs = _records(tmp_path, ids)
    recs.put(Record(id="slaper", type=RecordType.ROLE, parent="noochville", slaapt=True,
                    definition=RoleDefinition(purpose="slaapt")))
    led = ProjectLedger(str(tmp_path / "p.json"))
    from nooch_village.skills_impl.projectverzoek import ProjectverzoekSkill
    inw = _rol(tmp_path, led, [ProjectverzoekSkill(), _Onderzoek()], records=recs)
    gezien = {}

    def _vang(prompt, **kw):
        gezien["p"] = prompt
        plan = json.dumps({"deliverable": "d", "accountability": "a",
                           "items": [{"text": "t", "skill": "openalex_evidence",
                                      "payload": {"term": "x"}, "reason": ""}]})
        return (plan, "stub") if kw.get("return_tier") else plan
    monkeypatch.setattr(llm, "reason", _vang)
    inw._plan_checklist("goal")
    p = gezien["p"]
    assert "OTHER ROLES" in p
    assert all(f"- {rid}:" in p for rid in ids)                         # alle 27, ook #26 en #27
    assert "- slaper:" not in p and "- harry_hemp:" not in p            # slapend en ikzelf niet


def test_herplan_loopt_langs_validate_payload(tmp_path, monkeypatch):
    """De tweede uitvoerlijst weigert een verzonnen ontvanger bij het PLANNEN, zoals de eerste."""
    from nooch_village.skills_impl.projectverzoek import ProjectverzoekSkill
    recs = _records(tmp_path, ["compliance"])
    led = ProjectLedger(str(tmp_path / "p.json"))
    inw = _rol(tmp_path, led, [ProjectverzoekSkill()], records=recs, extra_skills=["zoekstrategie"])
    monkeypatch.setattr(Inhabitant, "_plan_checklist", lambda self, goal, **kw: {"items": [
        {"text": "hand over", "skill": "projectverzoek",
         "payload": {"naar_rol": "verzonnen_rol", "titel": "x"}},
        {"text": "hand over ok", "skill": "projectverzoek",
         "payload": {"naar_rol": "compliance", "titel": "y"}}]})
    pid = led.create("harry_hemp", "doel", "role", status="running")
    cl = led.checklist_add(pid, title="Strategie")
    led.check_add(pid, cl["id"], "strategie", skill="zoekstrategie")
    item = led.get(pid)["checklists"][0]["items"][0]
    inw._herplan_na_strategie(pid, item, {"ok": True, "stappen": [
        {"bron": "projectverzoek", "term": "x", "taal": "en"}]}, led)
    nieuw = led.get(pid)["checklists"][1]["items"]
    assert nieuw[0]["payload_ok"] is False and "verzonnen_rol" in nieuw[0]["reason"]
    assert nieuw[1].get("payload_ok") is not False


# ── 3. content_schrijven ─────────────────────────────────────────────────────

def _notes(tmp_path):
    from nooch_village.insight import EvidenceType, GroundingStatus, Insight
    from nooch_village.notes_store import NotesStore
    ns = NotesStore(str(tmp_path / "notes.json"))
    ns.add(Insight(id="echt", claim="Barefoot demand rises.", source="t", word="barefoot",
                   status=GroundingStatus.VERIFIED, grounds="trend data", warrant="three sources",
                   rebuttal="unless the trend is seasonal", evidence_type=EvidenceType.MEASURED))
    ns.add(Insight(id="zwak", claim="Price stalls intent.", source="t", word="price"))
    return ns


def test_content_schrijven_weigert_verzonnen_verified_en_een_soort_buiten_de_enum(tmp_path):
    from nooch_village.skills_impl.content_schrijven import ContentSchrijvenSkill
    sk = ContentSchrijvenSkill()
    ctx = SimpleNamespace(notes=_notes(tmp_path), copy_rules="")
    goed = [{"id": "echt", "claim": "Barefoot demand rises.", "status": "verified"}]
    assert sk.validate_payload({"cards": goed, "kind": "sales_page"}, ctx) == []
    fout = [{"id": "conscious_actie_1", "claim": "Made of 100% mycelium", "status": "verified"}]
    redenen = sk.validate_payload({"cards": fout, "kind": "sales_page"}, ctx)
    assert redenen and "conscious_actie_1" in redenen[0] and "verified" in redenen[0]
    assert sk.validate_payload({"cards": goed, "kind": "faq_page"}, ctx)
    assert sk.validate_payload({"cards": "tekst"}, ctx)
    assert ContentSchrijvenSkill.required_payload == ("cards",)


def test_content_schrijven_degradeert_een_status_die_de_store_niet_kent(tmp_path):
    from nooch_village.skills_impl.content_schrijven import ContentSchrijvenSkill
    ctx = SimpleNamespace(notes=_notes(tmp_path), copy_rules="")
    cards = [{"id": "echt", "claim": "Barefoot demand rises.", "status": "unresolved"},
             {"id": "nep", "claim": "Made of 100% mycelium", "status": "verified"}]
    with patch("nooch_village.llm.reason", return_value="Draft.") as m:
        uit = ContentSchrijvenSkill().run({"cards": cards, "kind": "sales_page"}, ctx)
    prompt = m.call_args[0][0]
    assert "- (verified) Barefoot demand rises." in prompt              # uit de store, niet de payload
    assert "- (unverified) Made of 100% mycelium" in prompt
    assert m.call_args.kwargs["max_tokens"] == 2500
    assert Inhabitant._classify_result(uit) == ("gelukt", ("text", "text"))
    assert Inhabitant._classify_result({"error": "no draft"})[0] == "fout"


# ── 4. bulletin_schrijven / field_note ───────────────────────────────────────

def test_bulletin_zonder_events_schrijft_niets(tmp_path):
    from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    with patch("nooch_village.llm.reason", return_value="# Village bulletin") as m:
        uit = BulletinSchrijvenSkill().run({"thema": "x", "doel": "y"}, ctx)
    assert uit["no_data"] is True and not m.called
    assert not os.path.exists(os.path.join(str(tmp_path), "bulletins"))
    assert ontbrekende_velden(BulletinSchrijvenSkill.required_payload, {"thema": "x"}) == ["events"]
    with patch("nooch_village.llm.reason", return_value="# Village bulletin\ntext"):
        uit = BulletinSchrijvenSkill().run({"events": [{"name": "dag_begint", "by": "clock"}]}, ctx)
    assert uit["text"].startswith("# Village bulletin") and os.path.exists(uit["path"])
    assert Inhabitant._classify_result(uit)[1] == ("text", "text")     # de note, niet het pad


def test_field_note_zonder_data_schrijft_niets_en_de_ladder_krijgt_zijn_context(tmp_path, monkeypatch):
    import nooch_village.skills_impl.field_note as fn
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    uit = fn.FieldNoteSkill().run({"topic": "traffic", "content": "x"}, ctx)
    assert uit["no_data"] is True and uit["path"] is None
    assert not os.path.exists(os.path.join(str(tmp_path), "output"))
    assert not os.path.exists(os.path.join(str(tmp_path), "last_pulse.json"))
    assert ontbrekende_velden(fn.FieldNoteSkill.required_payload, {}) == ["plausible"]
    # de ladder-keuze draait nu écht (was een NameError op `context`, stil gevangen)
    gezien = {}
    import nooch_village.llm_keuze as lk
    monkeypatch.setattr(lk, "llm_voorkeur", lambda omg, rid, site: gezien.update(omg=omg, site=site))
    monkeypatch.setattr(fn, "reason", lambda *a, **k: "Quiet week. Visitors (7d): 107.")
    uit = fn.FieldNoteSkill().run({"plausible": {"results": {"visitors": {"value": 107}}}}, ctx)
    assert gezien["omg"] is ctx and gezien["site"] == "skill_field_note"
    assert uit["text"].startswith("# Field Note") and "Quiet week" in uit["text"]


# ── 5. tegenspraak ───────────────────────────────────────────────────────────

_OORDEEL = json.dumps({"verdict": "needs revision", "weakest_claim": "45% CO2 saving",
                       "unsupported": ["45% CO2 saving", "unanimous customers"],
                       "counter_argument": "no LCA", "revision": "cite the LCA or drop the number"})


def test_tegenspraak_zet_het_oordeel_voorop_op_wall_en_verslag():
    from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
    with patch("nooch_village.llm.reason", return_value=_OORDEEL):
        uit = TegenspraakSkill().run({"tekst": "We save 45% CO2.", "bewijs": "a sole weighs 200 g"}, None)
    assert uit["oordeel"] == "needs revision"
    assert uit["text"].startswith("VERDICT: needs revision — 2 unsupported claims: 45% CO2 saving; "
                                  "unanimous customers; revision: cite the LCA")
    assert uit["bevindingen"] == [{"label": "unsupported", "claim": "45% CO2 saving"},
                                  {"label": "unsupported", "claim": "unanimous customers"}]
    assert uit["ongegrond"] == ["45% CO2 saving", "unanimous customers"]  # alias voor de critic
    status, arch = Inhabitant._classify_result(uit)
    assert status == "gelukt" and arch == ("list", "bevindingen")
    note = Inhabitant._leeswijzer(uit, arch)
    assert note.startswith("VERDICT: needs revision")
    verslag = project_verslag.inhoud_tekst(uit)
    assert verslag.startswith("VERDICT: needs revision") and "• unsupported — 45% CO2 saving" in verslag


def test_tegenspraak_leest_beide_talen_en_de_critic_leest_het_engelse_oordeel():
    from nooch_village import missie_critic as mc
    from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
    with patch("nooch_village.llm.reason", return_value='{"oordeel":"houdt stand","ongegrond":[]}'):
        uit = TegenspraakSkill().run({"tekst": "x"}, None)
    assert uit["oordeel"] == "holds" and uit["text"].startswith("VERDICT: holds")

    class _Sug:
        def run(self, payload, context=None):
            return {"ok": True, "oordeel": "needs revision", "ongegrond": [], "revisie": "add a line"}
    ok, waarom = mc._gegrond("doc", ["d1"], {}, skill=_Sug())
    assert ok is True and "add a line" in waarom

    class _Ok:
        def run(self, payload, context=None):
            return {"ok": True, "oordeel": "holds", "ongegrond": [], "text": "VERDICT: holds"}
    assert mc._gegrond("doc", ["d1"], {}, skill=_Ok()) == (True, "VERDICT: holds")


def test_tegenspraak_weigert_placeholder_bewijs():
    from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
    sk = TegenspraakSkill()
    with patch("nooch_village.llm.reason", return_value=_OORDEEL) as m:
        uit = sk.run({"tekst": "Bamboo is confirmed as suitable.",
                      "bewijs": "To be populated from claim_evidence results"}, None)
    assert "error" in uit and "placeholder" in uit["error"] and not m.called
    assert sk.validate_payload({"tekst": "x", "bewijs": "TODO: add evidence"}, None)
    assert sk.validate_payload({"tekst": "x", "bewijs": "ISO 14855 test report, 91% in 180 days"}, None) == []
    assert sk.validate_payload({"tekst": "x"}, None) == []


# ── 6. drie oorzaken, drie antwoorden ────────────────────────────────────────

def test_curate_onderscheidt_geen_model_rommel_en_niets_geldig(tmp_path):
    from nooch_village.skills_impl.curate import CurateSkill
    ctx = SimpleNamespace(notes=None)
    sk = CurateSkill()
    with patch("nooch_village.llm.reason", return_value=None):
        geen = sk.run({"input": "consument daalt"}, ctx)                 # alias-sleutel
    assert "error" in geen and Inhabitant._classify_result(geen)[0] == "fout"
    with patch("nooch_village.llm.reason", return_value="Sure, here you go"):
        rommel = sk.run({"data": ["claim one", "claim two"]}, ctx)
    assert "error" in rommel and "JSON" in rommel["error"]
    with patch("nooch_village.llm.reason", return_value='[{"id":"a","claim":"x"}]'):
        leeg = sk.run({"text": "x"}, ctx)
    assert leeg["no_data"] is True and "none complete" in leeg["reason"]
    with patch("nooch_village.llm.reason", return_value='[{"id":"a","claim":"x","grounds":"y"}]') as m:
        goed = sk.run({"fuzzy": "x"}, ctx)
    assert goed["cards"][0]["id"] == "a" and Inhabitant._classify_result(goed)[0] == "gelukt"
    assert m.call_args.kwargs["max_tokens"] == 2000 and m.call_args.kwargs["json_mode"] is True
    assert ontbrekende_velden(CurateSkill.required_payload, {"context": "x"}) == ["fuzzy|text|input|data"]
    assert ontbrekende_velden(CurateSkill.required_payload, {"input": "x"}) == []


def test_verband_call_site_is_bewust_goedkoop():
    from nooch_village import llm_keuze as lk
    assert "skill_verband" in lk.GOEDKOOP and lk.ladder_voor("skill_verband") is None


def test_kroniek_interpret_nul_records_is_gemeld_leeg(tmp_path):
    from nooch_village.evidence_ledger import EvidenceLedger
    from nooch_village.skills_impl.kroniek_interpret import KroniekInterpretSkill
    led = EvidenceLedger(str(tmp_path / "ev.jsonl"))
    ctx = SimpleNamespace(evidence_ledger=led, data_dir=str(tmp_path))
    uit = KroniekInterpretSkill().run({"onderwerp": "Green Claims Directive prohibited terms"}, ctx)
    assert uit["ok"] and uit["no_data"] is True and "never investigated" in uit["reason"]
    assert Inhabitant._classify_result(uit)[0] == "leeg" and Inhabitant._leeg_bron(uit) == "gemeld"
    led.record(role_id="c", skill="claim_evidence", query="Veja — biodegradable", source="https://a",
               status="bevestigd", result_ref="ISO")
    led.record(role_id="c", skill="epo_patents", query="biodegradable sole", source="epo",
               status="leeg")
    uit = KroniekInterpretSkill().run({"onderwerp": "biodegradable"}, ctx)
    assert uit["text"].startswith("1 confirmed record(s) for 'biodegradable' (sources: https://a)")
    assert "1 knowledge gap(s)" in uit["text"] and Inhabitant._classify_result(uit)[0] == "gelukt"
    assert "1-2 words" in KroniekInterpretSkill.input_schema


def test_weten_we_dit_al_kent_acroniemen_en_engelse_stopwoorden(tmp_path):
    from nooch_village.kennisbank import KennisbankStore
    from nooch_village.skills_impl.weten_we_dit_al import WetenWeDitAlSkill, _woorden
    assert _woorden("What do we already know about MOQ for EVA soles?") == ["moq", "eva", "soles"]
    assert _woorden("PHA PLA TPU") == ["pha", "pla", "tpu"]
    assert "what" not in _woorden("what about anything") and _woorden("what about anything") == []
    dd = str(tmp_path)
    KennisbankStore(f"{dd}/kennisbank.json").add("MOQ for EVA soles is 500 pairs",
                                                  why="supplier quote", subject="EVA")
    ctx = SimpleNamespace(data_dir=dd)
    ja = WetenWeDitAlSkill().run({"vraag": "What do we already know about MOQ for EVA soles?"}, ctx)
    assert ja["bekend"] is True and ja["text"].startswith("Yes")
    assert "kroniek" in ja and ja["kroniek"] == {}                       # geen lege bakken
    nee = WetenWeDitAlSkill().run({"vraag": "quantum computers for laces"}, ctx)
    assert nee["ok"] and nee["no_data"] is True and nee["bekend"] is False
    assert Inhabitant._classify_result(nee)[0] == "leeg"
    assert "error" in WetenWeDitAlSkill().run({"vraag": "what about"}, ctx)


def test_library_lookup_onbekend_is_gemeld_leeg_en_list_leest_een_string():
    from nooch_village.skills_impl.library_skills import LibraryListSkill, LibraryLookupSkill

    class _Lib:
        def status(self, w):
            return {"status": "approved", "rationale": "mission core"} if w == "plastic-free" else None

        def all(self):
            return {"plastic-free": {"status": "approved"}, "leer": {"status": "forbidden"},
                    "vegan": {"status": "escalated"}}
    ctx = SimpleNamespace(library=_Lib())
    onb = LibraryLookupSkill().run({"word": "regeneratieve revolutie"}, ctx)
    assert onb["no_data"] is True and onb["status"] == "unknown"
    assert Inhabitant._classify_result(onb)[0] == "leeg"
    bek = LibraryLookupSkill().run({"word": "plastic-free"}, ctx)
    assert bek["text"] == "'plastic-free' is approved: mission core"
    assert Inhabitant._classify_result(bek)[1] == ("text", "text")
    ls = LibraryListSkill()
    assert {t["term"] for t in ls.run({"statuses": "forbidden, escalated"}, ctx)["terms"]} == {"leer", "vegan"}
    assert {t["term"] for t in ls.run({"statuses": "approved"}, ctx)["terms"]} == {"plastic-free"}
    assert ls.validate_payload({"statuses": ["approved", "rejected"]}, ctx)
    assert ls.validate_payload({"statuses": "forbidden"}, ctx) == []
    assert "approved | forbidden | avoid | escalated | insight_statement" in LibraryListSkill.input_schema


# ── 7. metadata en de gedeelde helper ────────────────────────────────────────

def test_voorstel_en_synthesize_declareren_hun_contract():
    from nooch_village.registry_factory import build_skill_registry
    from nooch_village.skills_impl.synthesize import SynthesizeCardsSkill
    from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
    assert VoorstelSchrijvenSkill.required_payload == ("tension",)
    assert ontbrekende_velden(VoorstelSchrijvenSkill.required_payload, {}) == ["tension"]
    assert SynthesizeCardsSkill.cost == "free"
    assert SynthesizeCardsSkill.required_payload == ("card_a", "card_b")
    assert build_skill_registry().get("synthesize_cards") is None      # CLI-pad, geen dorpsskill


def test_engelse_descriptions_dragen_de_kern_in_160_tekens():
    from nooch_village.registry_factory import build_skill_registry
    reg = build_skill_registry()
    for naam, woord in (("escaleer", "DECISION"), ("projectverzoek", "ANOTHER role"),
                        ("content_schrijven", "brand voice"), ("voorstel_schrijven", "SCOPE"),
                        ("tegenspraak", "weakest"), ("curate", "atomic English"),
                        ("verband_voorstel", "connection"), ("kroniek_interpret", "Chronicle"),
                        ("weten_we_dit_al", "Memory first"), ("library_lookup", "status of ONE word"),
                        ("library_list", "statuses"), ("bulletin_schrijven", "bulletin"),
                        ("field_note", "Field Note")):
        assert woord in reg.get(naam).description[:160], naam
        assert reg.get(naam).input_schema, naam
