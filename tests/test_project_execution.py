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
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE

TODAY = "2026-07-08"


def _dm_teksten(st_of_dd, rol_of_persoon=None):
    """Alle DM-teksten in een dorp, of die van één rol/persoon.

    Sinds B2 (20 sept 2026) landt een melding als DM bij de mens in plaats van als rij in
    `NotifStore`. De routering — wie het krijgt — is ongewijzigd; alleen de plek is verhuisd."""
    from nooch_village import channels, signaal
    st = st_of_dd
    if isinstance(st_of_dd, str):
        st = signaal._MiniStores(st_of_dd)
    if rol_of_persoon is None:
        return [e.get("text") or "" for k in st.channels.bestaande()
                if channels.soort_van(k) == channels.DM for e in st.channels.trail(k)]
    wie, _ = signaal.ontvangers(st, "role", rol_of_persoon)
    if not wie:
        wie = [rol_of_persoon]
    return [e.get("text") or "" for p in wie for k in st.channels.kanalen_van(p)
            for e in st.channels.trail(k)]

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
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
    for text, skill, query, reason in items:
        ledger.check_add(pid, cl["id"], text, skill=skill, query=query, reason=reason)
    return cl


















# h. ledger: fail-teller optellen en resetten
def test_h_note_en_reset_item_fails(tmp_path, ledger):
    pid = ledger.create("harry_hemp", "doel", "human", status="running")
    cl = ledger.checklist_add(pid, "cl")
    ledger.check_add(pid, cl["id"], "item", skill="openalex_evidence")
    iid = ledger.get(pid)["checklists"][0]["items"][0]["id"]
    assert ledger.note_item_fail(pid, cl["id"], iid) == 1
    assert ledger.note_item_fail(pid, cl["id"], iid) == 2
    ledger.reset_item_fails(pid, cl["id"], [iid])
    assert (ledger.get(pid)["checklists"][0]["items"][0].get("fails") or 0) == 0












def test_means_gap_escaleert_zichtbaar_naar_founder(tmp_path):
    """Taak 2: een means-gap zet nu óók een heads-up-notificatie voor de founder (geen approve-knop)."""
    # Een dorp is nodig: de heads-up is sinds B2 een DM en moet een mens vinden.
    from nooch_village import cockpit2
    cockpit2._bootstrap(str(tmp_path))
    from nooch_village.human_inbox import HumanInbox
    hi = HumanInbox(str(tmp_path / "human_inbox.json"))
    hi.add_means_gap("skill_ladder:openalex", "Skill-ladder uitgeput voor 'barefoot'",
                     role_id="harry_hemp", sensed_by="harry_hemp")
    fnd = _dm_teksten(str(tmp_path))
    assert len(fnd) == 1
    assert "Capaciteit ontbreekt" in fnd[0] and "nooch_village.inbox" in fnd[0]
    assert "approve" not in fnd[0].lower()                     # heads-up, geen beslis-knop
    # dedup: dezelfde gap opnieuw → geen tweede bericht
    hi.add_means_gap("skill_ladder:openalex", "nogmaals", role_id="harry_hemp")
    assert len(_dm_teksten(str(tmp_path))) == 1
