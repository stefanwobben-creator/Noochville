"""IA-fase 1 + de header-opruiming (23 jul): de bovenrand draagt logo, globale zoekbalk en
begroeting; de meta-links (Metrics · Deelnemers) staan in de gedeelde footer en de breadcrumb
is weg. De Kennisbank woont onder de Librarian-rol (Tools-tab). Deze test bevriest het
contract: de inhoud én de single-source-regel (geen view hardcodeert de nav inline)."""
from __future__ import annotations

import glob
import re

from nooch_village.cockpit2_util import _footer, _nav


def test_topbar_is_logo_plus_zoek_zonder_meta_links():
    """De bovenrand is rustig: logo + globale zoekbalk + begroeting. De meta-links zijn naar de
    footer verhuisd, dus ze horen hier NIET meer te staan."""
    h = _nav()
    assert "c2-logo" in h and "class='c2-search'" in h and "c2-greet" in h
    assert "/metrics2" not in h and "/admin" not in h        # meta-links: footer, niet topbar
    # de uit-de-nav-gehaalde items zijn weg (Kennisbank woont onder de Librarian-rol)
    for weg in ("/inbox", "/belofte", "/inzichten", "/signals", "/accountabilities",
                "/kennisbank"):
        assert weg not in h, f"{weg} hoort niet meer in de nav"


def test_meta_links_staan_in_de_footer():
    """Metrics en People blijven bereikbaar — één bron (_NAV_ITEMS), gerenderd in de footer
    die _send op elke pagina injecteert."""
    f = _footer()
    assert "<a href='/metrics2'>Metrics</a>" in f
    assert "<a href='/admin'>People</a>" in f


def test_context_label_wordt_niet_meer_getoond():
    """De breadcrumb is uit de header gehaald; `context` blijft alleen in de signatuur voor compat,
    zodat de ~18 aanroepen niet hoefden te wijzigen. Geen enkele waarde lekt nog naar de HTML."""
    assert "projectdetail" not in _nav("projectdetail")
    assert _nav("patterns") == _nav("projectdetail") == _nav()


def test_geen_view_hardcodeert_de_nav_nog_inline():
    # single-source: geen enkele view mag de oude inline nav-balk nog dragen.
    oud = re.compile(r"<div class='bar'>cockpit 2 · GlassFrog \(PoC\) · build \{_BUILD\}")
    overtreders = [f for f in glob.glob("nooch_village/views/*.py")
                   if oud.search(open(f).read())]
    assert not overtreders, f"nav nog inline in: {overtreders}"
