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

from nooch_village import cockpit2
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE
from nooch_village.deliverable_store import DeliverableStore
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.personas import PersonaStore


def _een_vervuller(dd, rol="mother_earth__nooch__website_developer") -> str:
    """Kies één van de vervullers van deze rol, als `trekker`-waarde.

    `website_developer` heeft in de fixture TWEE vervullers (test_poc_datamodel bevriest dat), en
    de cardinaliteitswet eist dan een expliciete keuze vóór een project op het bord mag. Deze tests
    gaan niet over eigenaarschap, dus ze kiezen er gewoon één — precies zoals de andere
    proj_add-tests `done_when` invullen sinds díe poort er is (zie test_proj_add_eist_done_when).
    """
    st = cockpit2._Stores(dd)
    f = st.assign.fillers_of(rol, record=st.records.get(rol))[0]
    return f"{'person' if f.type == 'person' else 'persona'}:{f.id}"

TODAY = "2026-07-11"
_REASON = "nooch_village.llm.reason"
def _synth_calls(m) -> int:
    """Hoe vaak draaide de EINDDOCUMENT-SYNTHESE? Niet: hoe vaak draaide er een LLM.

    Sinds 06-09-2026 zet elk opgeleverd item ook een conclusiezin boven zijn note (één goedkope
    call per item, schakelbaar via `deliverable_conclusie_enabled`). `m.call_count` telt die mee en
    zou deze tests laten falen op iets waar ze niet over gaan. De synthese is herkenbaar aan
    `return_tier=True` — zij is de enige die wil weten welk model schreef, om dat te markeren."""
    return sum(1 for c in m.call_args_list if c.kwargs.get("return_tier"))


def _reason_mock(tekst, tier="mistral:mistral-small-latest"):
    """`reason()` geeft `(tekst, trede)` terug zodra de aanroeper `return_tier=True` vraagt — de
    einddocument-synthese doet dat, om te kunnen markeren welk model schreef. Andere call-sites in
    dezelfde flow vragen gewoon de tekst. Eén mock die beide vormen bedient."""
    def _fake(prompt, *, return_tier=False, **kw):
        return (tekst, tier if tekst else None) if return_tier else tekst
    return _fake


class _ResearchSkill(Skill):
    name = "openalex_evidence"
    description = "fake research skill"

    def run(self, payload, context):
        term = (payload or {}).get("term", "")
        if term == "boom":
            raise RuntimeError("API kapot")
        return {"term": term, "total": 1, "hits": [{"title": f"Study on {term}"}]}



def _herkomst(docs, pid) -> dict:
    """De herkomst zonder het tijdstempel. `ts` kwam erbij toen de synthese moest weten wélk bewijs
    er sinds de vorige versie bij kwam (ze ziet haar eigen vorige proza niet meer) — dat is geen
    onderdeel van wat deze tests toetsen: wélk model schreef, en was dat een terugval."""
    return {k: v for k, v in (docs.meta(pid) or {}).items() if k != "ts"}

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
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    for text, skill, query in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query)
    return cl
















# 7. Atomic write: nooit een half bestand leesbaar; geen achtergebleven .tmp
def test_atomic_write_nooit_half_bestand(tmp_path):
    docs = ProjectDocStore(str(tmp_path))
    docs.write("p1", "eerste volledige versie")
    docs.write("p1", "tweede volledige versie" * 1000)         # grote overschrijf
    assert docs.read("p1") == "tweede volledige versie" * 1000  # volledig, nooit half
    leftovers = [f for f in os.listdir(os.path.join(str(tmp_path), "project_docs")) if f.endswith(".tmp")]
    assert leftovers == []                                     # temp is via os.replace opgeruimd




# ── cockpit-dispatch: edit-route-AUTHZ + delete-cascade (via de publieke dispatch) ────────────────
def _cockpit_project(dd):
    """Bootstrap + één actief project op een bemande rol; geef (pid, ProjectDocStore)."""
    from nooch_village import cockpit2
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add",
                      {"owner": [role], "scope": ["Doc-scope"],
                       "trekker": [_een_vervuller(dd)],
                       "done_when": ["af bij oplevering"], "col": ["actief"], "next": ["/"]},
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




# ── De terugval-markering: nooit stil doorgaan voor een premium exemplaar ────
# Een persona-voorkeur is sinds de zachte staart een KOP met de dorpsladder erachter. Valt de dure
# trede weg, dan komt er alsnog een document — van een goedkoper model. Dat mag zichtbaar zijn,
# anders leest zo'n document bij review als een premium exemplaar.

def _sid_met_voorkeur(tmp_path, ladder="anthropic:sonnet"):
    personas = PersonaStore(str(tmp_path / "personas.json"))
    sid = personas.add("Sid", mbti="INTP")
    personas.update(sid.id, llm={"default": "", "per_taak": {"einddocument": ladder}})
    return personas, sid


def _synth(tmp_path, ledger, ds, docs, personas, sid, pid, tier):
    """Draai één synthese waarbij `reason()` antwoordt vanaf trede `tier`."""
    from nooch_village.inhabitant import synthesize_einddocument
    rec = Record(id="sid", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p"), persona_id=sid.id)
    with patch(_REASON, side_effect=_reason_mock("## Conclusie\nKlaar.", tier)):
        return synthesize_einddocument(
            project_docs=docs, deliverables=ds, projects=ledger, personas=personas, record=rec,
            settings={}, project=ledger.get(pid), force_final=True,
            log=logging.getLogger("test.synth"))










def test_mens_edit_wist_de_herkomst(tmp_path):
    """Na een mens-edit is er geen model meer verantwoordelijk — dan hoort er ook geen model-chip
    te staan die suggereert dat dit nog het gegenereerde document is."""
    _, _, docs = _stores(tmp_path)
    docs.write("p1", "door het model", tier="mistral:m1", terugval=True)
    docs.write("p1", "door de mens")
    assert docs.meta("p1") == {}


# GUARD: de markering moet ook ECHT te zien zijn op de projectpagina (en dus bij review).
def test_terugval_is_zichtbaar_op_de_projectpagina(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views.projects import render_project
    dd = str(tmp_path / "poc")
    pid, docs = _cockpit_project(dd)
    st = cockpit2._Stores(dd)

    # Asserteer op de CHIP-opmaak, niet op het losse woord: de projectmuur bevat ook regels als
    # "via semscholar_tldr (fallback voor openalex_evidence)". Een guard die daarop kan slagen
    # bewijst niets over de markering.
    docs.write(pid, "# Rapport\nInhoud.", tier="anthropic:sonnet", terugval=False)
    html = render_project(st, pid)
    assert "<span class='chip outline' title='Model that wrote this document'>anthropic:sonnet</span>" in html
    assert "chip amber" not in html

    docs.write(pid, "# Rapport\nInhoud.", tier="mistral:m1", terugval=True)
    html = render_project(st, pid)
    assert "class='chip amber'" in html and "⚠ fallback: mistral:m1</span>" in html


def test_zonder_herkomst_geen_chip(tmp_path):
    """Documenten van vóór deze markering (en mens-edits) leveren geen lege of misleidende chip."""
    from nooch_village import cockpit2
    from nooch_village.views.projects import render_project
    dd = str(tmp_path / "poc")
    pid, docs = _cockpit_project(dd)
    docs.write(pid, "# Rapport\nInhoud.")
    assert "chip amber" not in render_project(cockpit2._Stores(dd), pid)
