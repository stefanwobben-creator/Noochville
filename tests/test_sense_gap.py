"""Tests voor _sense_gap deduplicatie in Inhabitant — thread-vrij.

Vier scenario's:
1. Verse gap → éénmalig emitteren.
2. Accountability al in DNA → onderdruk, emit niets.
3. Na emit + governance-verwerking → tweede aanroep zwijgt.
4. force=True, al in DNA → zwijgt ook (force ≠ "negeer dedup").
"""
from __future__ import annotations
import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry


def _make_inhabitant(tmp_path, accountabilities=None):
    bus      = EventBus(name="test")
    registry = SkillRegistry()
    context  = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        records=None,
    )
    record = Record(
        id="test_rol",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="test",
            accountabilities=list(accountabilities or []),
            domains=[],
            skills=[],
        ),
        source="seed",
    )
    return Inhabitant(record, bus, registry, context)


def _seed_reflect(tmp_path, gap_key: str, acc: str):
    """Schrijf een reflect-state alsof het gat al eerder gemeld en verwerkt is."""
    state = {gap_key: {"count": 1, "emitted": True,
                       "first_seen": 0.0, "last_seen": 0.0,
                       "acc": acc}}
    (tmp_path / "reflect_test_rol.json").write_text(json.dumps(state))


# ── 1. Verse gap → éénmalig emitteren ──────────────────────────────────────

def test_fresh_gap_emits_once(tmp_path):
    inh = _make_inhabitant(tmp_path)
    with patch.object(inh, "sense_tension") as st:
        result = inh._sense_gap("mijn_gat",
                                "accountability: doe iets — uitleg",
                                min_count=1)
    assert result is True
    st.assert_called_once()


# ── 2. Accountability al in DNA → onderdruk ─────────────────────────────────

def test_gap_suppressed_when_accountability_in_dna(tmp_path):
    acc = "doe iets"
    inh = _make_inhabitant(tmp_path, accountabilities=[acc])
    _seed_reflect(tmp_path, "mijn_gat", acc)

    with patch.object(inh, "sense_tension") as st:
        result = inh._sense_gap("mijn_gat",
                                "accountability: doe iets — uitleg",
                                min_count=1)
    assert result is False
    st.assert_not_called()


# ── 3. Na emit + governance → tweede aanroep zwijgt ─────────────────────────

def test_second_call_suppressed_after_governance(tmp_path):
    inh     = _make_inhabitant(tmp_path)
    emitted = []

    with patch.object(inh, "sense_tension", side_effect=lambda d, **_: emitted.append(d)):
        # Eerste aanroep: emitteert
        inh._sense_gap("gat2", "accountability: iets nieuws — detail", min_count=1)
        # Simuleer: governance heeft de accountability aan het DNA toegevoegd
        inh.dna.accountabilities.append("iets nieuws")
        # Tweede aanroep: zwijgt
        result2 = inh._sense_gap("gat2", "accountability: iets nieuws — detail", min_count=1)

    assert len(emitted) == 1, "verwacht exact één emit"
    assert result2 is False


# ── 4. force=True respecteert dedup ─────────────────────────────────────────

def test_force_gap_suppressed_when_in_dna(tmp_path):
    acc = "altijd aanwezig"
    inh = _make_inhabitant(tmp_path, accountabilities=[acc])
    _seed_reflect(tmp_path, "force_gat", acc)

    with patch.object(inh, "sense_tension") as st:
        result = inh._sense_gap("force_gat",
                                "accountability: altijd aanwezig — detail",
                                force=True)
    assert result is False
    st.assert_not_called()
