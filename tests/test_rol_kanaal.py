"""Het @rol-kanaal: werk aan een AI-rol wordt een project, geen dead letter.

Wat er misging, gemeten op productie (11 aug 2026):

  1. `Inhabitant` LEEST NotifStore nooit — hij schrijft er alleen naar. Een notificatie aan een
     AI-bemande rol was dus een dead letter: 74 berichten aan `compliance`, 0 gelezen.
  2. De bemensings-check vroeg naar type "person". Elke AI-bemande rol las als onbemand, en kreeg
     een kopie naar de Circle Lead met "[rol X onbemand]" — 47 stuks, allemaal bij de founder.
  3. `compliance` zat alléén in de legacy `record.persona_id`-laag, dus `fillers_of(rol)` zonder
     `record=` zag zelfs de persona niet.

Samen: de founder besloot 7× "bank het bewijs", en dat werd een bericht aan een rol die niet
luistert plus een kopie aan zichzelf. Niets onderzocht, niets gebankt, status "in behandeling".

De guards staan onderaan: een persona-bemande rol leest nooit onbemand, en een werk-bericht aan
een AI-rol wordt een project op zijn bord.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from nooch_village import claims_board
from nooch_village.assignments import (Assignments, bemand, door_mens_bemand,
                                       migrate_persona_bindings)
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.notifications import NotifStore
from nooch_village.projects import ProjectLedger


def _omg(tmp_path, *, fillers=None, persona_id=None):
    """Een omgeving met echte stores. `fillers` gaat in de assignments-store, `persona_id` op het
    record — de twee lagen die uit elkaar liepen."""
    dd = str(tmp_path)
    recs = Records(os.path.join(dd, "governance_records.json"))
    recs.put(Record(id="cirkel", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="c"), members=["rolx"]))
    recs.put(Record(id="rolx", type=RecordType.ROLE, parent="cirkel",
                    definition=RoleDefinition(purpose="p"), persona_id=persona_id))
    asg = Assignments(os.path.join(dd, "assignments.json"))
    for t, i in (fillers or []):
        asg.assign("rolx", t, i)
    return SimpleNamespace(data_dir=dd, dd=dd, records=recs, assign=asg,
                           notif=NotifStore(os.path.join(dd, "notifications.json")),
                           projects=ProjectLedger(os.path.join(dd, "projects.json")))


def _snippets(omg):
    return [n.get("snippet", "") for n in omg.notif.all()] if hasattr(omg.notif, "all") else []


# ── De bemensings-check zelf ────────────────────────────────────────────────

def test_persona_in_de_assignments_store_telt_als_bemand(tmp_path):
    omg = _omg(tmp_path, fillers=[("persona", "a1")])
    assert bemand("rolx", omg.assign, omg.records) is True
    assert door_mens_bemand("rolx", omg.assign, omg.records) is False   # wél: geen mens


def test_persona_in_de_legacy_laag_telt_ook_als_bemand(tmp_path):
    """Compliance zat alléén hier. Zonder deze regel las de rol dubbel-onbemand."""
    omg = _omg(tmp_path, persona_id="a1")
    assert omg.assign.fillers_of("rolx") == []            # niets in de store...
    assert bemand("rolx", omg.assign, omg.records) is True  # ...maar wel bemand


def test_mens_telt_als_bemand_en_als_mens(tmp_path):
    omg = _omg(tmp_path, fillers=[("person", "p1")])
    assert bemand("rolx", omg.assign, omg.records) is True
    assert door_mens_bemand("rolx", omg.assign, omg.records) is True


def test_zonder_filler_is_onbemand(tmp_path):
    omg = _omg(tmp_path)
    assert bemand("rolx", omg.assign, omg.records) is False


def test_check_valt_zacht_bij_kapotte_stores():
    class _Stuk:
        def fillers_of(self, *a, **k):
            raise RuntimeError("stuk")
    assert bemand("x", _Stuk(), None) is False            # geen crash in het hete pad


# ── De migratie: één bron van waarheid ──────────────────────────────────────

def test_migratie_verplaatst_de_legacy_binding(tmp_path):
    omg = _omg(tmp_path, persona_id="a1")
    assert migrate_persona_bindings(omg.records, omg.assign) == 1
    assert [(f.type, f.id) for f in omg.assign.fillers_of("rolx")] == [("persona", "a1")]
    # ...en daarmee klopt de kale lezing, zónder record=. Dát is het punt van de migratie.
    assert bemand("rolx", omg.assign, None) is True


def test_migratie_is_idempotent(tmp_path):
    omg = _omg(tmp_path, persona_id="a1")
    assert migrate_persona_bindings(omg.records, omg.assign) == 1
    assert migrate_persona_bindings(omg.records, omg.assign) == 0      # tweede run kost niets
    assert len(omg.assign.fillers_of("rolx")) == 1                     # geen duplicaat


# ── Werk versus FYI ─────────────────────────────────────────────────────────

def test_guard_werk_aan_een_ai_rol_wordt_een_project(tmp_path):
    """DE guard. Een AI-rol leest zijn notificaties nooit; werk krijg je bij hem via het bord."""
    omg = _omg(tmp_path, fillers=[("persona", "a1")])
    doelen = claims_board.bericht_aan_rol(omg, "rolx", "Bank the evidence for: 100% plantaardig")
    assert doelen == ["rolx"]
    projecten = ProjectLedger(os.path.join(str(tmp_path), "projects.json")).all()
    assert len(projecten) == 1
    p = projecten[0]
    assert p["owner"] == "rolx" and p["status"] == "queued"
    assert p["origin"] == claims_board.ORIGIN_BERICHT
    assert "Bank the evidence" in str(p["scope"])


def test_fyi_over_bestaand_werk_maakt_geen_tweede_project(tmp_path):
    """Een aanroeper die een project_id meegeeft heeft het werk NET op het bord gezet; dit bericht
    maakt de rol alleen wakker. Nog een project zou het bord vervuilen met dubbelingen."""
    omg = _omg(tmp_path, fillers=[("persona", "a1")])
    bestaand = omg.projects.create("rolx", "Al op het bord", "role", status="future")
    claims_board.bericht_aan_rol(omg, "rolx", "Pak dit op", project_id=bestaand)
    assert len(omg.projects.all()) == 1                    # alleen het bestaande project


def test_expliciet_werk_false_maakt_nooit_een_project(tmp_path):
    omg = _omg(tmp_path, fillers=[("persona", "a1")])
    claims_board.bericht_aan_rol(omg, "rolx", "Puur ter info", werk=False)
    assert omg.projects.all() == []


def test_mens_bemande_rol_krijgt_geen_project(tmp_path):
    """Een mens leest zijn inbox wél. Werk als project op zijn bord zetten zou het bord vullen met
    dingen die hij al in zijn inbox ziet."""
    omg = _omg(tmp_path, fillers=[("person", "p1")])
    claims_board.bericht_aan_rol(omg, "rolx", "Doe dit even")
    assert omg.projects.all() == []


def test_hetzelfde_verzoek_twee_keer_geeft_een_project(tmp_path):
    """De site-scan en de founder-flow herhalen zich per puls; zonder dedup groeit het bord."""
    omg = _omg(tmp_path, fillers=[("persona", "a1")])
    for _ in range(3):
        claims_board.bericht_aan_rol(omg, "rolx", "Bank the evidence for: 100% plantaardig")
    assert len(omg.projects.all()) == 1


# ── Het onbemand-vangnet, op de juiste vraag ────────────────────────────────

def test_guard_persona_bemande_rol_leest_nooit_onbemand(tmp_path):
    """DE tweede guard, in beide lagen: geen '[rol X onbemand]'-kopie naar de Circle Lead."""
    for kw in ({"fillers": [("persona", "a1")]}, {"persona_id": "a1"}):
        omg = _omg(tmp_path / f"v{list(kw)[0]}", **kw)
        doelen = claims_board.bericht_aan_rol(omg, "rolx", "Doe dit")
        assert "cirkel__circle_lead" not in doelen, kw
        assert not any("onbemand" in s for s in _snippets(omg)), kw


def test_echt_onbemande_rol_valt_nog_steeds_aan_de_circle_lead(tmp_path):
    """Het vangnet blijft: accountabilities van een onbemande rol vallen aan de Circle Lead."""
    omg = _omg(tmp_path)
    doelen = claims_board.bericht_aan_rol(omg, "rolx", "Doe dit")
    assert "cirkel__circle_lead" in doelen
    assert any("onbemand" in s for s in _snippets(omg))


def test_bericht_faalt_nog_steeds_zacht():
    assert claims_board.bericht_aan_rol(SimpleNamespace(), "rolx", "x") in ([], ["rolx"])


def test_notificatie_blijft_de_audittrail(tmp_path):
    """Het project is het werk; de notificatie blijft staan als 'dit is doorgegeven', met een
    verwijzing naar het project dat eruit ontstond."""
    omg = _omg(tmp_path, fillers=[("persona", "a1")])
    claims_board.bericht_aan_rol(omg, "rolx", "Bank the evidence")
    snips = _snippets(omg)
    assert snips and "Als project op je bord gezet" in snips[0]
