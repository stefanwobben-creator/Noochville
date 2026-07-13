"""feat/einddocument — de constitutie-plicht op de Inhabitant-basis.

Elke puls met ≥1 geslaagd checklist-item werkt het levende einddocument bij via ÉÉN LLM-synthese-call
(geen call per item), in de persona-stem; finale pass + note bij review; fail-closed (LLM stuk →
document intact); harde input-cap fail-loud. Plus de atomic-write-garantie van de store en dat
#task-regels IN de documenttekst niet als sturing worden geparseerd.
"""
from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger
from nooch_village.deliverable_store import DeliverableStore
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.personas import PersonaStore

TODAY = "2026-07-11"
_REASON = "nooch_village.llm.reason"


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        if term == "boom":
            raise RuntimeError("API kapot")
        return {"term": term, "total": 1, "hits": [{"title": f"Study on {term}"}]}


def _stores(tmp_path):
    return (ProjectLedger(str(tmp_path / "projects.json")),
            DeliverableStore(str(tmp_path / "deliverables.json")),
            ProjectDocStore(str(tmp_path)))


def _inh(tmp_path, ledger, dstore, docstore, *, persona_id="", personas=None, cap="20000"):
    reg = SkillRegistry()
    reg.register(_ResearchSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", "einddocument_input_max_chars": cap},
                          data_dir=str(tmp_path), projects=ledger, deliverables=dstore,
                          project_docs=docstore, personas=personas, records=None)
    rec = Record(id="sid", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="w", accountabilities=["research"], domains=[],
                                           skills=["openalex_evidence"]), source="sensed",
                 persona_id=persona_id)
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _prep(ledger, pid, items):
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for text, skill, query in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query)
    return cl


# 1. Item slaagt → document bijgewerkt (één reguliere pass; niet alle items af)
@pytest.mark.smoke
def test_item_slaagt_document_bijgewerkt(tmp_path):
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    _prep(ledger, pid, [("s", "openalex_evidence", "barefoot"), ("mens-taak", None, "")])   # 2e blijft open
    with patch(_REASON, return_value="# Einddocument\nEerste bevindingen.") as m:
        inh._execute_checklist(ledger.get(pid), TODAY)
    assert m.call_count == 1                                     # reguliere pass, één call
    assert docs.read(pid) == "# Einddocument\nEerste bevindingen."


# 2. Twee geslaagde items in dezelfde puls → géén tweede call (rem op call-per-item)
def test_twee_items_zelfde_puls_een_call(tmp_path):
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    _prep(ledger, pid, [("a", "openalex_evidence", "x"), ("b", "openalex_evidence", "y"),
                        ("open", None, "")])                     # 2 slagen, 1 blijft open → niet all-done
    with patch(_REASON, return_value="doc") as m:
        inh._execute_checklist(ledger.get(pid), TODAY)
    assert m.call_count == 1                                     # één synthese, niet twee


# 3. LLM faalt (geen antwoord) → document INTACT + logregel
def test_llm_faalt_document_intact(tmp_path, caplog):
    ledger, ds, docs = _stores(tmp_path)
    docs.write("p", "OUD DOCUMENT")                             # bestaand document
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    # gebruik hetzelfde pid als het voorgeschreven document
    docs.write(pid, "OUD DOCUMENT")
    _prep(ledger, pid, [("s", "openalex_evidence", "x"), ("open", None, "")])
    with caplog.at_level(logging.INFO), patch(_REASON, return_value=None):
        inh._execute_checklist(ledger.get(pid), TODAY)
    assert docs.read(pid) == "OUD DOCUMENT"                     # ongewijzigd
    assert "document ongewijzigd" in caplog.text                # logregel


# 4. Alle items af → finale pass + note "📄 …", document geschreven, status WACHT
def test_awaiting_review_finale_pass_en_note(tmp_path):
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    _prep(ledger, pid, [("s", "openalex_evidence", "barefoot")])   # één item → all-done
    with patch(_REASON, return_value="# Afgerond\nKlaar.") as m:
        inh._execute_checklist(ledger.get(pid), TODAY)
    assert m.call_count == 1
    assert docs.read(pid) == "# Afgerond\nKlaar."
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review"
    assert any(e.get("text", "").startswith("📄 Einddocument bijgewerkt") for e in p.get("log", []))


# 5. Input-cap fail-loud: kleine cap → DOC_INPUT_CAP-logregel, geen stille truncatie
def test_cap_fail_loud(tmp_path, caplog):
    ledger, ds, docs = _stores(tmp_path)
    docs_pid_seed = "x" * 500
    inh = _inh(tmp_path, ledger, ds, docs, cap="50")           # heel kleine cap
    pid = ledger.create("sid", "doel", "human", status="queued")
    docs.write(pid, docs_pid_seed)                             # groot huidig document → input > 50
    _prep(ledger, pid, [("s", "openalex_evidence", "x"), ("open", None, "")])
    with caplog.at_level(logging.WARNING), patch(_REASON, return_value="doc"):
        inh._execute_checklist(ledger.get(pid), TODAY)
    assert "DOC_INPUT_CAP" in caplog.text


# 6. Persona-stem: de prompt bevat de persona-context (assert op de prompt, niet op de stijl)
def test_persona_stem_in_prompt(tmp_path):
    ledger, ds, docs = _stores(tmp_path)
    personas = PersonaStore(str(tmp_path / "personas.json"))
    sid = personas.add("Sid", mbti="INTP", instructions="Wees bondig en warm.")
    inh = _inh(tmp_path, ledger, ds, docs, persona_id=sid.id, personas=personas)
    pid = ledger.create("sid", "doel", "human", status="queued")
    _prep(ledger, pid, [("s", "openalex_evidence", "x"), ("open", None, "")])
    with patch(_REASON, return_value="doc") as m:
        inh._execute_checklist(ledger.get(pid), TODAY)
    prompt = m.call_args[0][0]
    assert "Sid" in prompt and m.call_args[1]["call_site"] == "einddocument"


# 6b. Rapport-kwaliteit: volledige deliverable-inhoud (niet op 500 afgekapt) + taak/bevindingen-structuur
#     + hogere output-cap → rapporten worden niet meer stil afgekapt en beantwoorden de taak.
def test_volledige_inhoud_en_structuur_en_hogere_cap(tmp_path):
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    big = "BEVINDING-" + "x" * 1200            # > 500 (oude preview-cap), < 3000 (nieuwe per-deliverable cap)
    ds.add(project_id=pid, role="sid", skill="openalex_evidence", checklist_item="i1",
           title="Zoek X", content={"detail": big},
           summary="📎 Zoek X — via openalex_evidence: 1 resultaat")
    with patch(_REASON, return_value="doc") as m:
        inh._synthesize_einddocument(ledger.get(pid), done=1, total=1, force_final=True)
    prompt = m.call_args[0][0]
    assert big in prompt                                          # volledige inhoud, niet op 500 afgekapt
    assert "FEITELIJKE BEVINDINGEN" in prompt and "elke taak" in prompt.lower()   # taak/bevindingen-structuur
    assert m.call_args[1]["max_tokens"] == 4000                   # hogere output-cap (default)


# 7. Atomic write: nooit een half bestand leesbaar; geen achtergebleven .tmp
def test_atomic_write_nooit_half_bestand(tmp_path):
    docs = ProjectDocStore(str(tmp_path))
    docs.write("p1", "eerste volledige versie")
    docs.write("p1", "tweede volledige versie" * 1000)         # grote overschrijf
    assert docs.read("p1") == "tweede volledige versie" * 1000  # volledig, nooit half
    leftovers = [f for f in os.listdir(os.path.join(str(tmp_path), "project_docs")) if f.endswith(".tmp")]
    assert leftovers == []                                     # temp is via os.replace opgeruimd


# 8. #task IN de documenttekst → geen parsing (niet gelift naar sturing)
def test_task_in_documenttekst_geen_parsing(tmp_path):
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    docs.write(pid, "# Doc\n#task herschrijf de intro")        # #task in het document, GEEN comment
    _prep(ledger, pid, [("s", "openalex_evidence", "x"), ("open", None, "")])
    with patch(_REASON, return_value="doc") as m:
        inh._execute_checklist(ledger.get(pid), TODAY)
    prompt = m.call_args[0][0]
    assert "#task herschrijf de intro" in prompt               # verschijnt als HUIDIG DOCUMENT
    assert "STURING VAN DE MENS" not in prompt                 # maar NIET geparseerd tot sturing


# ── cockpit-dispatch: edit-route-AUTHZ + delete-cascade (via de publieke dispatch) ────────────────
def _cockpit_project(dd):
    """Bootstrap + één actief project op een bemande rol; geef (pid, ProjectDocStore)."""
    from nooch_village import cockpit2
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add",
                      {"owner": [role], "scope": ["Doc-scope"], "col": ["actief"], "next": ["/"]},
                      username="guest")
    pid = next(p["id"] for p in cockpit2._Stores(dd).projects.all() if p.get("scope") == "Doc-scope")
    return pid, ProjectDocStore(dd)


# 9. Edit-route-AUTHZ: ingelogde-onbekende geweigerd (geen schrijf); guest (auth uit) mag wél
def test_doc_edit_route_authz(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    pid, docs = _cockpit_project(dd)
    cockpit2.dispatch(dd, "proj_doc_edit", {"pid": [pid], "doc": ["geheim"], "next": ["/"]},
                      username="onbekend@x")                 # ingelogde-maar-onbekende → _role_gate weigert
    assert docs.read(pid) == ""                              # niets geschreven
    cockpit2.dispatch(dd, "proj_doc_edit", {"pid": [pid], "doc": ["# Doc"], "next": ["/"]},
                      username="guest")                       # auth uit → toegestaan
    assert docs.read(pid) == "# Doc"


# 10. Doc-delete-cascade: project-delete verwijdert ook het einddocument-.md
def test_doc_delete_cascade(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    pid, docs = _cockpit_project(dd)
    docs.write(pid, "# Doc")
    assert docs.read(pid) == "# Doc"
    cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/"]}, username="guest")
    assert docs.read(pid) == ""                              # sidecar mee-verwijderd door de cascade


# 11. Cockpit-actie: rapport handmatig opnieuw genereren (zelfde synthese als de puls)
def test_regen_doc_action(tmp_path):
    from unittest.mock import patch
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    pid, docs = _cockpit_project(dd)
    with patch("nooch_village.llm.reason", return_value="## Conclusie\nAlles klaar."):
        cockpit2.dispatch(dd, "proj_regen_doc", {"pid": [pid], "next": ["/"]}, username="guest")
    assert "Conclusie" in docs.read(pid)            # verse synthese geschreven via de herbruikbare functie
