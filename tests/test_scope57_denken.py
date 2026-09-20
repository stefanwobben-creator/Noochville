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
from nooch_village.projects import ProjectLedger, checklist_progress, PREP_CHECKLIST_TITLE
from nooch_village.skills import Skill, SkillRegistry, ontbrekende_velden
from nooch_village.skills_impl.escaleer import EscaleerSkill, rol_id_voor

TODAY = "2026-09-12"


# ── gereedschap ──────────────────────────────────────────────────────────────

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
    cl = ledger.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
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




def test_beslissing_draagt_de_vraag_en_het_project(tmp_path):
    # Een dorp is nodig: de escalatie is sinds B2 een DM en moet dus een MENS vinden. Vroeger
    # schreef `NotifStore.add` een rij ongeacht of de doelrol bestond.
    from nooch_village import cockpit2
    cockpit2._bootstrap(str(tmp_path))
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    with patch("nooch_village.llm.reason", return_value=None):
        r = EscaleerSkill().run({"reden": "drop the elastane requirement: yes or no?",
                                 "naar": "founder", "_project_id": "p-123"}, ctx)
    assert r["wacht_op_mens"] is True and r["aard"] == "beslissing"
    assert r["text"] == "Decision requested from the_source: drop the elastane requirement: yes or no?"
    assert Inhabitant._classify_result(r)[1] == ("text", "text")        # de vraag wint, niet 'aard'
    # De vraag landt als DM bij een mens, met het project als herkomst — dat veld is het enige
    # dat B2 bewaarde, juist omdat de lezer anders niet ziet waar de vraag over gaat.
    from nooch_village import channels, signaal
    mini = signaal._MiniStores(str(tmp_path))
    entries = [e for k in mini.channels.bestaande()
               if channels.soort_van(k) == channels.DM for e in mini.channels.trail(k)]
    assert entries and (entries[-1].get("herkomst") or {}).get("project") == "p-123"


def test_aard_buiten_de_enum_wordt_bij_het_plannen_geweigerd():
    sk = EscaleerSkill()
    assert sk.validate_payload({"aard": "vraag", "reden": "x"}, None)
    assert sk.validate_payload({"aard": "bevinding", "reden": "x"}, None) == []
    assert sk.validate_payload({"reden": "x"}, None) == []              # leeg: de skill classificeert








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










# ── 5. tegenspraak ───────────────────────────────────────────────────────────

_OORDEEL = json.dumps({"verdict": "needs revision", "weakest_claim": "45% CO2 saving",
                       "unsupported": ["45% CO2 saving", "unanimous customers"],
                       "counter_argument": "no LCA", "revision": "cite the LCA or drop the number"})






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



def test_verband_call_site_is_bewust_goedkoop():
    from nooch_village import llm_keuze as lk
    assert "skill_verband" in lk.GOEDKOOP and lk.ladder_voor("skill_verband") is None




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




