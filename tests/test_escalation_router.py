"""Deel 4 — de escalatie-router: rollen laten samenwerken i.p.v. alles naar de mens te sturen.

De twee niet-onderhandelbare guards staan bovenaan:
  1. HOP-TELLER — A→B→A kan niet ontstaan; bij de limiet eindigt het bij de mens.
  2. ZICHTBAAR DOODLOPEN — loopt een doorverwezen item dood bij B, dan parkeert het daar zichtbaar
     via dezelfde klep, mét gat-record. Nooit stil sterven.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import gap_ledger
from nooch_village.escalation_router import escaleer, kies_ontvanger, roster, route_item, trail_of
from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.projects import ProjectLedger
from nooch_village.skills import Skill, SkillRegistry


def _records(tmp_path):
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="harry", type=RecordType.ROLE, parent="dorp",
                    definition=RoleDefinition(purpose="wetenschappelijke onderbouwing",
                                              accountabilities=["onderzoek doen"])))
    recs.put(Record(id="website_dev", type=RecordType.ROLE, parent="dorp",
                    definition=RoleDefinition(purpose="de website bouwen en onderhouden",
                                              accountabilities=["pagina's bouwen"])))
    recs.put(Record(id="dorp", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="de cirkel")))
    return recs


def _antwoord(role="NONE", kind="missing_capability", capability=""):
    def _fn(prompt, **kw):
        return json.dumps({"role": role, "kind": kind, "capability": capability})
    return _fn


def _project(ledger, owner="harry", tekst="bouw de QR-landingspagina", trail=None):
    pid = ledger.create(owner, "QR-codes op de schoenen", "human", status="queued")
    ledger.start(pid)
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], tekst, skill=None, reason="geen skill hiervoor")
    if trail:
        ledger.set_handoff_trail(pid, trail)
    return pid, cl["id"]


def _item(ledger, pid, clid):
    p = ledger.get(pid)
    cl = next(c for c in p["checklists"] if c["id"] == clid)
    return cl["items"][0]


# ── GUARD 1: de hop-teller ─────────────────────────────────────────────────────

def test_nooit_terug_naar_een_rol_die_het_al_zag(tmp_path):
    """A→B→A wordt geblokkeerd: ook al wijst de router A aan, A staat in het spoor."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    # het werk zat al bij harry, is doorgegeven aan website_dev, en die loopt nu vast
    pid, clid = _project(ledger, owner="website_dev", trail=["harry"])

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="website_dev", reason_fn=_antwoord(role="harry"))

    assert res["actie"] != "handoff"                       # geen terugkaats naar harry
    assert res["naar_rol"] is None
    assert not [p for p in ledger.all() if p["owner"] == "harry" and p["id"] != pid]


def test_op_de_hop_limiet_gaat_het_naar_de_mens(tmp_path):
    """Twee bureaus verder en nog steeds niet geland: dat is een mens-beslissing, geen derde gok."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="website_dev", trail=["harry", "iemand_anders"])
    gemeld = []

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="website_dev", settings={"escalation_max_hops": "2"},
                     reason_fn=_antwoord(role="harry"), notify=lambda p, t: gemeld.append(t))

    assert res["actie"] == "human"
    # DE VAGE PING IS EEN VANGNET, GEEN ROUTE. Hij vuurt alleen als `naar_mens` het NIET kwijt kan.
    # Sinds `route_werk` naar de vervuller kijkt landt dit hier wél — en dan is een tweede,
    # vagere melding erbij precies de dubbele ping die we elders hebben weggehaald.
    assert res["geland"], "de laatste meter landde niet"
    assert res["gap"] is not None                          # ook hier wordt het gat geoogst


def test_het_spoor_reist_mee_naar_het_nieuwe_project(tmp_path):
    """De teller moet de herplanning bij de ontvanger overleven — daarom hangt hij aan het PROJECT,
    niet aan het item (dat krijgt bij B nieuwe id's)."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="harry")

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="harry", reason_fn=_antwoord(role="website_dev"))

    assert res["actie"] == "handoff" and res["naar_rol"] == "website_dev"
    nieuw = ledger.get(res["pid"])
    assert trail_of(nieuw) == ["harry"]
    assert nieuw["owner"] == "website_dev" and nieuw["status"] == "queued"


# ── GUARD 2: zichtbaar doodlopen ───────────────────────────────────────────────

def test_doodgelopen_handoff_parkeert_zichtbaar_bij_de_ontvanger(tmp_path):
    """B kan het ook niet en niemand anders bezit het: dan parkeert B's project zichtbaar via de
    klep, mét gat-record. Nooit stil sterven."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="website_dev", trail=["harry"])
    inh = _inhabitant(tmp_path, ledger, recs, "website_dev")

    inh._execute_checklist(ledger.get(pid), "2026-07-30")

    p = ledger.get(pid)
    assert p["status"] == "blocked"                        # zichtbaar geparkeerd bij B
    assert "vastgelopen" in (p["blocked_on"] or "")
    gaten = gap_ledger.alle(str(tmp_path))
    assert len(gaten) == 1 and gaten[0]["role"] == "website_dev"
    assert gaten[0]["hop_trail"] == ["harry"]              # de keten is terug te lezen


# ── de beslisvolgorde ──────────────────────────────────────────────────────────

def test_handoff_naar_een_skill_loze_rol_mag(tmp_path):
    """Het hele punt: eigenaarschap gaat vóór gereedschap. Een rol die het werk bezit maar de skill
    mist is de juiste ontvanger — daar hoort het gat te landen."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    assert not recs.get("website_dev").definition.skills      # géén skills
    pid, clid = _project(ledger, owner="harry")

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="harry", reason_fn=_antwoord(role="website_dev"))

    assert res["actie"] == "handoff"
    assert _item(ledger, pid, clid)["skipped"] is True        # telt hier niet meer mee
    assert "accountability" in _item(ledger, pid, clid)["skip_reason"]


def test_geen_zekere_eigenaar_forceert_geen_gok(tmp_path):
    """Fail-closed: 'NONE' → niemand krijgt het werk toegeschoven."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="harry")

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="harry", reason_fn=_antwoord(role="NONE"))

    assert res["actie"] == "park" and res["naar_rol"] is None
    assert len(ledger.all()) == 1                            # geen nieuw project ergens


def test_verzonnen_rol_wordt_geweigerd(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="harry")

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="harry", reason_fn=_antwoord(role="afdeling_qr_stickers"))

    assert res["actie"] == "park"


def test_fysiek_werk_gaat_naar_de_mens(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="harry", tekst="plak de sticker op de schoen")
    gemeld = []

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="harry", reason_fn=_antwoord(role="NONE", kind="human_external"),
                     notify=lambda p, t: gemeld.append(t))

    assert res["actie"] == "human" and res["reason"] == gap_ledger.HUMAN_EXTERNAL
    # DE VAGE PING IS EEN VANGNET, GEEN ROUTE. Hij vuurt alleen als `naar_mens` het NIET kwijt kan.
    # Sinds `route_werk` naar de vervuller kijkt landt dit hier wél — en dan is een tweede,
    # vagere melding erbij precies de dubbele ping die we elders hebben weggehaald.
    assert res["geland"] or (gemeld and "mens of externe partij" in gemeld[0])
    assert gap_ledger.alle(str(tmp_path))[0]["reason"] == gap_ledger.HUMAN_EXTERNAL


def test_llm_weg_is_geen_handoff_maar_wel_een_gat(tmp_path):
    """Fail-soft: het dorp mag langzamer worden als de LLM wegvalt, niet stiller."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="harry")

    def _kapot(prompt, **kw):
        raise RuntimeError("geen sleutel")

    res = route_item(ledger=ledger, records=recs, data_dir=str(tmp_path),
                     project=ledger.get(pid), clid=clid, item=_item(ledger, pid, clid),
                     from_role="harry", reason_fn=_kapot)

    assert res["actie"] == "park" and res["gap"] is not None


def test_router_vuurt_maar_een_keer_per_item(tmp_path):
    """Anders doet elke reactivering dezelfde LLM-call op hetzelfde vastgelopen item."""
    ledger = ProjectLedger(str(tmp_path / "p.json"))
    recs = _records(tmp_path)
    pid, clid = _project(ledger, owner="harry")
    calls = []

    def _tel(prompt, **kw):
        calls.append(1)
        return json.dumps({"role": "NONE", "kind": "missing_capability", "capability": "x"})

    for _ in range(3):
        p = ledger.get(pid)
        cl = next(c for c in p["checklists"] if c["id"] == clid)
        escaleer(ledger=ledger, records=recs, data_dir=str(tmp_path), project=p, clid=clid,
                 items=cl["items"], from_role="harry", reason_fn=_tel)

    assert len(calls) == 1
    assert len(gap_ledger.alle(str(tmp_path))) == 1


def test_roster_laat_cirkels_en_zichzelf_weg(tmp_path):
    recs = _records(tmp_path)
    ids = {k["id"] for k in roster(recs, exclude={"harry"})}
    assert ids == {"website_dev"}                            # geen 'dorp' (cirkel), geen 'harry'


def test_kies_ontvanger_is_fail_closed():
    kand = [{"id": "a"}, {"id": "b"}]
    assert kies_ontvanger(None, kand, [], "a") is None
    assert kies_ontvanger({"role": ""}, kand, [], "a") is None
    assert kies_ontvanger({"role": "none"}, kand, [], "a") is None
    assert kies_ontvanger({"role": "zzz"}, kand, [], "a") is None
    assert kies_ontvanger({"role": "a"}, kand, [], "a") is None          # zichzelf
    assert kies_ontvanger({"role": "b"}, kand, ["b"], "a") is None       # zag het al
    assert kies_ontvanger({"role": "b"}, kand, [], "a") == "b"


# ── hulpjes ────────────────────────────────────────────────────────────────────

class _Dummy(Skill):
    name = "niets"
    description = "doet niets"

    def run(self, payload, context):
        return {"ok": True}


def _inhabitant(tmp_path, ledger, recs, rol_id):
    reg = SkillRegistry()
    reg.register(_Dummy())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, records=recs)
    rec = recs.get(rol_id)
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)
