"""R3-hardening: een skill-aanroep buiten het DNA mag NOOIT stil falen.

Achtergrond: verband_voorstel en curate waren maandenlang dode features omdat
use_skill een error-dict teruggaf zonder log. Deze test borgt dat (a) een
DNA-miss luid wordt gelogd en (b) dode capabilities statisch zichtbaar zijn via
dormant_capabilities(). Thread-vrij, geen netwerk."""
from __future__ import annotations
import logging
import sys, os
import pytest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry


def _make(skills):
    rec = Record(
        id="tester", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="test", skills=list(skills)),
        source="seed",
    )
    ctx = SimpleNamespace(settings={})
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)


class _DemoRole(Inhabitant):
    """Rol die twee skills aanroept; één zit in DNA, één niet."""
    def doe_werk(self):
        self.use_skill("alpha", {})
        self.use_skill("beta", {})


def _make_demo(skills):
    rec = Record(
        id="demo", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="test", skills=list(skills)),
        source="seed",
    )
    ctx = SimpleNamespace(settings={})
    return _DemoRole(rec, EventBus(name="test"), SkillRegistry(), ctx)


def test_dna_miss_geeft_error_en_logt_warning(caplog):
    inw = _make(skills=[])
    with caplog.at_level(logging.WARNING):
        out = inw.use_skill("verband_voorstel", {})
    assert "error" in out
    # Luide log met de naam van de dode skill
    assert any("verband_voorstel" in r.getMessage() for r in caplog.records)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_referenced_capabilities_scant_broncode():
    inw = _make_demo(skills=["alpha"])
    refs = inw.referenced_capabilities()
    assert "alpha" in refs
    assert "beta" in refs


def test_dormant_capabilities_toont_alleen_ongegrante():
    inw = _make_demo(skills=["alpha"])
    dormant = inw.dormant_capabilities()
    assert dormant == {"beta"}        # alpha is gegrant, beta niet


def test_geen_dormant_als_alles_gegrant():
    inw = _make_demo(skills=["alpha", "beta"])
    assert inw.dormant_capabilities() == set()
