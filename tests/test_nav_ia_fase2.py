"""IA-fase 2: tools wonen onder hun eigenaar-rol (kaart op de Tools-tab). De keyword-tools
zijn sinds fase 3 lenzen op één datalaag; de kaarten wijzen naar /keywords?lens=… (getest hier)."""
from __future__ import annotations

import types

from nooch_village.views.overview import _role_tools_html, _ROLE_TOOLS


def _rec(rid):
    return types.SimpleNamespace(id=rid)


def test_role_tools_kaarten_per_eigenaar_rol():
    marketing = _role_tools_html(_rec("mother_earth__nooch__marketing_lead"))
    assert "Linkbuilding" in marketing and "/linkbuilding" in marketing and "tile-grid" in marketing
    assert "/keywords?lens=marketing" in marketing
    lara = _role_tools_html(_rec("librarian"))
    assert "Woordenschat" in lara and "/woordenschat" in lara
    # Convergentie is een automatische check (nieuw-ster op de woordenschat) en signalen
    # zijn ontsloten via de Kennisbank — dus geen aparte tool-kaarten meer bij Lara.
    assert "/signals" not in lara and "/keywords?lens=library" not in lara
    scout = _role_tools_html(_rec("concurrent_scout"))
    assert "/keywords?lens=trends" in scout
    sid = _role_tools_html(_rec("harry_hemp"))
    assert "Long-term trends" in sid and "/keywords?lens=scientist" in sid


def test_role_tools_leeg_voor_niet_eigenaar():
    assert _role_tools_html(_rec("iemand_anders")) == ""
    assert _role_tools_html(_rec("")) == ""


def test_registry_dekt_de_eigenaar_rollen():
    assert set(_ROLE_TOOLS) == {
        "mother_earth__nooch__marketing_lead", "librarian", "concurrent_scout", "harry_hemp",
        "compliance"}


def test_claims_checker_hangt_onder_compliance_en_niet_onder_de_website_rol():
    """De claims-toets is compliance-domein. De website-rol krijgt hem expliciet niet."""
    assert "/claims" in _role_tools_html(_rec("compliance"))
    for ander in ("website_watcher", "mother_earth__nooch__website_developer",
                  "mother_earth__nooch__marketing_lead"):
        assert "/claims" not in _role_tools_html(_rec(ander))
