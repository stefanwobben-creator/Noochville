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
    assert "Woordenschat" in lara and "Signals &amp; Insights" in lara
    assert "/woordenschat" in lara and "/signals" in lara
    assert "/keywords?lens=library" in lara            # convergentie-lens
    scout = _role_tools_html(_rec("concurrent_scout"))
    assert "/keywords?lens=trends" in scout
    sid = _role_tools_html(_rec("harry_hemp"))
    assert "Long-term trends" in sid and "/keywords?lens=scientist" in sid


def test_role_tools_leeg_voor_niet_eigenaar():
    assert _role_tools_html(_rec("iemand_anders")) == ""
    assert _role_tools_html(_rec("")) == ""


def test_registry_dekt_de_vier_eigenaars():
    assert set(_ROLE_TOOLS) == {
        "mother_earth__nooch__marketing_lead", "librarian", "concurrent_scout", "harry_hemp"}
