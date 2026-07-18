"""Taak 0 — stabiele accountability-ids.

De kern: een koppeling (AI-taak, skill-link) hangt aan het ID van een belofte, niet aan zijn
positie. Een governance-ronde die accountabilities toevoegt of verwijdert hersorteert de lijst;
zonder stabiel id wijst een bestaande koppeling daarna naar de VERKEERDE belofte.
"""
from __future__ import annotations

from nooch_village import acc_ids
from nooch_village.ai_tasks import AITaskStore
from nooch_village.governance import Records, Secretary
from nooch_village.event_bus import EventBus
from nooch_village.models import (
    Record, RecordType, RoleDefinition, Proposal, GovernanceChange, ChangeKind,
)


def _records(tmp_path, accs):
    r = Records(str(tmp_path / "rec.json"))
    r.put(Record(id="rol_x", type=RecordType.ROLE, parent="wortel",
                 definition=RoleDefinition(purpose="p", accountabilities=list(accs))))
    return r


def _amend(records, add=(), remove=()):
    """Draai een echte adoptie via de Secretary — geen nagebouwde mutatie."""
    sec = Secretary(records, EventBus())
    sec._adopt(Proposal(
        proposer_role="rol_x",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="rol_x",
                                add_accountabilities=list(add),
                                remove_accountabilities=list(remove)),
        tension="t", trigger_example="e", rationale="r"))


# ── De ids zelf ───────────────────────────────────────────────────────────────

def test_ids_worden_bijgemunt_en_migratie_is_idempotent(tmp_path):
    recs = _records(tmp_path, ["beta", "alfa"])
    defn = recs.get("rol_x").definition
    assert len(defn.accountability_ids) == 2
    assert len(set(defn.accountability_ids)) == 2      # uniek
    before = list(defn.accountability_ids)

    # Tweede load muteert niets: de migratie is idempotent.
    assert Records(str(tmp_path / "rec.json")).get("rol_x").definition.accountability_ids == before


def test_ensure_vult_alleen_de_gaten(tmp_path):
    defn = RoleDefinition(purpose="p", accountabilities=["a", "b", "c"],
                          accountability_ids=["id_a", "", "id_c"])
    assert acc_ids.ensure_acc_ids(defn) is True
    assert defn.accountability_ids[0] == "id_a" and defn.accountability_ids[2] == "id_c"
    assert defn.accountability_ids[1]                     # bijgemunt
    assert acc_ids.ensure_acc_ids(defn) is False          # tweede keer: niets te doen


def test_duplicaten_worden_opgeheven():
    defn = RoleDefinition(purpose="p", accountabilities=["a", "b"],
                          accountability_ids=["zelfde", "zelfde"])
    acc_ids.ensure_acc_ids(defn)
    assert len(set(defn.accountability_ids)) == 2


# ── De acceptatie: koppelingen overleven een herordening ──────────────────────

def test_koppeling_blijft_aan_juiste_accountability_na_toevoegen(tmp_path):
    """Adoptie sorteert de lijst. 'zebra' verschuift van index 1 naar index 2 zodra 'midden'
    erbij komt — de koppeling moet aan 'zebra' blijven hangen, niet meeschuiven naar 'midden'."""
    recs = _records(tmp_path, ["alfa", "zebra"])
    defn = recs.get("rol_x").definition
    zebra_id = acc_ids.acc_id_at(defn, defn.accountabilities.index("zebra"))

    ai = AITaskStore(str(tmp_path / "ai.json"))
    ai.add("rol_x", zebra_id, "persona_1", "doet iets met zebra")

    _amend(recs, add=["midden"])

    defn2 = Records(str(tmp_path / "rec.json")).get("rol_x").definition
    assert defn2.accountabilities == ["alfa", "midden", "zebra"]   # index verschoven
    assert acc_ids.text_for(defn2, zebra_id) == "zebra"            # id niet
    assert [t.acc_id for t in ai.for_acc("rol_x", zebra_id)] == [zebra_id]


def test_koppeling_blijft_juist_na_verwijderen(tmp_path):
    recs = _records(tmp_path, ["alfa", "beta", "gamma"])
    defn = recs.get("rol_x").definition
    gamma_id = acc_ids.acc_id_at(defn, 2)

    _amend(recs, remove=["alfa"])

    defn2 = Records(str(tmp_path / "rec.json")).get("rol_x").definition
    assert defn2.accountabilities == ["beta", "gamma"]
    assert acc_ids.text_for(defn2, gamma_id) == "gamma"
    assert acc_ids.index_of(defn2, gamma_id) == 1


def test_verwijderde_accountability_laat_andere_ids_ongemoeid(tmp_path):
    recs = _records(tmp_path, ["alfa", "beta"])
    defn = recs.get("rol_x").definition
    alfa_id, beta_id = defn.accountability_ids[0], defn.accountability_ids[1]

    _amend(recs, remove=["alfa"])

    defn2 = Records(str(tmp_path / "rec.json")).get("rol_x").definition
    assert defn2.accountability_ids == [beta_id]
    assert acc_ids.index_of(defn2, alfa_id) == -1      # weg, niet hergebruikt
    assert acc_ids.text_for(defn2, alfa_id) == ""


# ── Migratie van bestaande index-koppelingen ──────────────────────────────────

def test_migratie_index_naar_acc_id(tmp_path):
    recs = _records(tmp_path, ["alfa", "beta"])
    defn = recs.get("rol_x").definition

    # Simuleer een store zoals hij op prod staat: nog met acc_index, zonder acc_id.
    import json
    path = str(tmp_path / "ai.json")
    json.dump({"t1": {"id": "t1", "role": "rol_x", "acc_index": 1,
                      "agent": "persona_1", "wat": "iets"}}, open(path, "w"))

    ai = AITaskStore(path)
    assert ai.migrate_acc_ids(recs) == 1
    assert ai.migrate_acc_ids(recs) == 0                     # idempotent
    beta_id = acc_ids.acc_id_at(defn, 1)
    assert [t.id for t in ai.for_acc("rol_x", beta_id)] == ["t1"]
    assert ai.all()[0].kind == "autonoom"                    # default bij lezen


def test_migratie_van_onbekende_index_verplaatst_niet_stilzwijgend(tmp_path):
    recs = _records(tmp_path, ["alfa"])
    import json
    path = str(tmp_path / "ai.json")
    json.dump({"t1": {"id": "t1", "role": "rol_x", "acc_index": 7,
                      "agent": "persona_1", "wat": "iets"}}, open(path, "w"))
    ai = AITaskStore(path)
    assert ai.migrate_acc_ids(recs) == 0          # fail-soft: blijft zichtbaar kapot
    assert ai.all()[0].acc_id == ""


def test_migratie_is_deterministisch_over_processen(tmp_path):
    """Op prod laden daemon én cockpit dezelfde records-file. Met willekeurige uuid's zou elk
    proces zijn eigen ids munten en de laatste schrijver winnen — koppelingen naar de
    verliezende set zijn dan stil kapot. Het id wordt daarom uit de tekst afgeleid."""
    import json
    import shutil
    recs = _records(tmp_path, ["alfa", "beta"])
    path = str(tmp_path / "rec.json")

    # Zet de file terug in de staat zoals prod hem vandaag heeft: zonder ids.
    raw = json.load(open(path))
    raw["rol_x"]["definition"]["accountability_ids"] = []
    json.dump(raw, open(path, "w"))
    kopie = path + ".kopie"
    shutil.copy(path, kopie)

    a = Records(path).get("rol_x").definition.accountability_ids
    b = Records(kopie).get("rol_x").definition.accountability_ids
    assert a == b and all(a)


def test_zelfde_tekst_geeft_zelfde_id_in_elke_rol(tmp_path):
    from nooch_village.models import RoleDefinition
    d1 = RoleDefinition(purpose="p", accountabilities=["site monitoren"])
    d2 = RoleDefinition(purpose="q", accountabilities=["site monitoren"])
    acc_ids.ensure_acc_ids(d1)
    acc_ids.ensure_acc_ids(d2)
    # Uniek hoeft alleen binnen een rol: elke query is role + acc_id.
    assert d1.accountability_ids == d2.accountability_ids
