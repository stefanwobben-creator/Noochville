"""IA-fase 1: de top-nav is één gedeelde, geslankte balk (Metrics · Deelnemers).
De Kennisbank woont onder de Librarian-rol (Tools-tab). Deze test bevriest het
contract: de inhoud én de single-source-regel (geen view hardcodeert de nav inline)."""
from __future__ import annotations

import glob
import re

from nooch_village.cockpit2_util import _nav


def test_nav_is_geslankt_tot_twee_ankers():
    h = _nav()
    # de twee ankers, met hun bestemming
    assert "<a href='/metrics2'>Metrics</a>" in h
    assert "<a href='/admin'>Deelnemers</a>" in h
    # de uit-de-nav-gehaalde items zijn weg (Kennisbank woont onder de Librarian-rol)
    for weg in ("/inbox", "/belofte", "/inzichten", "/signals", "/accountabilities",
                "/kennisbank"):
        assert weg not in h, f"{weg} hoort niet meer in de nav"
    assert ">home<" not in h and ">deelnemers<" not in h  # home weg; label nu 'Deelnemers'


def test_context_label_blijft_regelbaar():
    assert "cockpit 2 · projectdetail ·" in _nav("projectdetail")
    assert "cockpit 2 · patterns ·" in _nav("patterns")


def test_geen_view_hardcodeert_de_nav_nog_inline():
    # single-source: geen enkele view mag de oude inline nav-balk nog dragen.
    oud = re.compile(r"<div class='bar'>cockpit 2 · GlassFrog \(PoC\) · build \{_BUILD\}")
    overtreders = [f for f in glob.glob("nooch_village/views/*.py")
                   if oud.search(open(f).read())]
    assert not overtreders, f"nav nog inline in: {overtreders}"
