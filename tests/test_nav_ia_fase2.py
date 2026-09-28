"""IA-fase 2: tools wonen onder hun eigenaar-rol (kaart op de Tools-tab). De keyword-tools
zijn sinds fase 3 lenzen op één datalaag; de kaarten wijzen naar /keywords?lens=… (getest hier)."""
from __future__ import annotations

import pathlib
import types

from nooch_village import claims_db
from nooch_village.views.overview import _role_tools_html, _ROLE_TOOLS, _DOMAIN_TOOLS


def _rec(rid):
    return types.SimpleNamespace(id=rid)


def _rec_met_domein(rid, domein=claims_db.DOMEIN):
    return types.SimpleNamespace(id=rid, definition=types.SimpleNamespace(domains=[domein]))


def test_geen_enkele_rol_tool_wijst_naar_een_verdwenen_scherm():
    """DE KLASSE FOUT, en niet alleen dit geval. Een tool-kaart is een LINK in code; verdwijnt het
    scherm eronder, dan merkt niemand dat tot iemand erop klikt. `/linkbuilding` stond zo negen
    dagen dood op de tools van Marketing Lead, en "Oracle" was hetzelfde geval — daar is het toen
    per kaart opgelost.

    Deze toets doet het structureel: elke interne href in `_ROLE_TOOLS`/`_DOMAIN_TOOLS` moet een
    route zijn die `cockpit2` daadwerkelijk kent. Een kaart zonder href (bewust uitgeschakeld, met
    de reden in de tekst) telt niet mee — dat is juist de oplossing."""
    import re

    from nooch_village.views.overview import _DOMAIN_TOOLS, _ROLE_TOOLS
    bron = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "cockpit2.py").read_text()
    routes = set(re.findall(r'path == "(/[a-z0-9_-]*)"', bron))
    routes |= {"/node", "/"}                       # via andere vergelijkingen afgehandeld

    dood = []
    for rijen in list(_ROLE_TOOLS.values()) + list(_DOMAIN_TOOLS.values()):
        for label, _uitleg, href in rijen:
            if not href or not href.startswith("/"):
                continue
            pad = href.replace("&amp;", "&").split("?")[0]
            if pad not in routes:
                dood.append(f"{label} → {href}")
    assert not dood, f"tool-kaart naar een route die niet bestaat: {dood}"


def test_een_uitgeschakelde_kaart_zegt_waarom():
    """Een lege href zonder uitleg is een kaart die niets doet en niets zegt. Wie hem uitschakelt,
    schrijft erbij wat er weg is — dat is het patroon dat "Oracle" al volgde."""
    from nooch_village.views.overview import _DOMAIN_TOOLS, _ROLE_TOOLS
    for rijen in list(_ROLE_TOOLS.values()) + list(_DOMAIN_TOOLS.values()):
        for label, uitleg, href in rijen:
            if href:
                continue
            assert "removed" in uitleg.lower(), f"{label} is uitgeschakeld zonder reden: {uitleg!r}"


def test_role_tools_kaarten_per_eigenaar_rol():
    marketing = _role_tools_html(_rec("mother_earth__nooch__marketing_lead"))
    # EN DE LINK IS TERUG (28 september 2026, later die dag). Hij wees sinds #516 naar een
    # verwijderd scherm en stond daarom even als uitgeschakelde kaart; het scherm is nu opnieuw
    # gebouwd op het patroon van `/site-audit`. Dat de route ook ECHT bestaat bewaakt de ratchet
    # hieronder — deze toets kijkt alleen of de kaart er staat en waarheen hij wijst.
    assert "Linkbuilding" in marketing and "tile-grid" in marketing
    assert "/linkbuilding" in marketing
    assert "/keywords?lens=marketing" in marketing
    lara = _role_tools_html(_rec("librarian"))
    assert "Library" in lara and "/woordenschat" in lara
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
    # website_developer erbij: de Backlog Builder stond op zijn Notes-tab en woont nu onder Tools,
    # zoals elk ander rol-gereedschap.
    #
    # mother_earth__nooch is de eerste CIRKEL in dit register, en dat is een bewuste keuze: de
    # copy-policies wonen bij Community & Email, maar ze gelden voor iedereen die voor Nooch
    # schrijft. Hing het gereedschap aan de eigenaar-rol, dan zou de copywriter het niet vinden.
    #
    # `compliance` staat hier NIET meer: dat gereedschap hangt aan het claims-domein
    # (`_DOMAIN_TOOLS`), zodat het meeverhuist als de rol die het domein bezit verandert.
    assert set(_ROLE_TOOLS) == {
        "mother_earth__nooch__marketing_lead", "librarian", "concurrent_scout", "harry_hemp",
        "mother_earth__nooch__website_developer", "mother_earth__nooch"}
    assert set(_DOMAIN_TOOLS) == {claims_db.DOMEIN}


def test_copy_gereedschap_hangt_onder_de_nooch_cirkel():
    """Vooraf de prompt, achteraf de toets, tegen precies dezelfde policies — dus samen op één
    plek. Twee kaarten, geen twee vindplaatsen."""
    html = _role_tools_html(_rec("mother_earth__nooch"))
    assert "/copy-prompt" in html and "/copy-check" in html
    assert "Copy prompt generator" in html and "Copy checker" in html


def test_site_audit_hangt_onder_de_website_rol():
    """De Backlog Builder hing hier tot 11 september 2026 en is verwijderd (Stefan: "die gebruiken
    we niet"; op de server bestond data/backlog.json niet eens). Het gereedschap van de rol is nu
    de site audit."""
    sid = _role_tools_html(_rec("mother_earth__nooch__website_developer"))
    assert "Site audit" in sid and "/site-audit" in sid
    assert "Backlog Builder" not in sid and "/backlog" not in sid


def test_claims_checker_hangt_aan_het_domein_en_niet_aan_een_rol_id():
    """De claims-toets is claims-DOMEIN, niet 'de rol die toevallig compliance heet'.

    Stond als `_ROLE_TOOLS["compliance"]`. Die rol verhuisde naar de Nooch-cirkel en kreeg een
    nieuw id; de kaart verdween daarmee zonder één foutmelding. Nu volgt het gereedschap het
    domein, dus het verhuist mee met wie het domein via governance bezit."""
    assert "/claims" in _role_tools_html(_rec_met_domein("mother_earth__nooch__compliance"))
    assert "/claims" in _role_tools_html(_rec_met_domein("een_heel_andere_naam"))
    # Alleen het domein geeft toegang: de oude naam op zichzelf niet meer.
    assert "/claims" not in _role_tools_html(_rec("compliance"))
    for ander in ("website_watcher", "mother_earth__nooch__website_developer",
                  "mother_earth__nooch__marketing_lead"):
        assert "/claims" not in _role_tools_html(_rec(ander))
