"""Guard: de design-systeem-bouwstenen (interactieve chip/pill + wrap-rij + schuif-toggle) staan als
echte klassen in het cockpit2-design-systeem, en zijn gedocumenteerd. Scope 1 van de metrics-UI
visuele pariteit — nog geen scherm gekoppeld, alleen de bouwstenen + doc."""
from __future__ import annotations
import os

from nooch_village.cockpit2_util import _EXTRA_CSS


def test_chip_pill_component_met_wrap():
    for sel in (".chip-wrap{", ".chip-opt{", ".chip-opt.on{"):
        assert sel in _EXTRA_CSS, sel
    wrap = _EXTRA_CSS.split(".chip-wrap{", 1)[1].split("}", 1)[0]
    assert "flex-wrap:wrap" in wrap                       # rij chips breekt netjes af binnen de kaart


def test_schuif_toggle():
    for sel in (".switch{", ".switch::after{", ".switch.on{", ".switch.on::after{", ".switch-field{"):
        assert sel in _EXTRA_CSS, sel


def test_gedocumenteerd_in_ux_patterns():
    doc = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "UX_PATTERNS.md")).read()
    for k in (".chip-opt", ".chip-wrap", ".switch", ".switch-field"):
        assert k in doc, k
