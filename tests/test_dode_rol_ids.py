"""Een rol-id in code overleeft de rol niet.

Op 17 en 18 september 2026 zijn zes AI-rollen opgeruimd. Drie plekken in de code noemden er nog
één bij naam, en alle drie wezen ze daarna stil naar een gearchiveerd record:

- `founder_taken.UITVOERDER_ROL` → de copywriter. Een goedgekeurd voorstel werd "overgedragen" aan
  een rol waar niemand meer naar kijkt. De comment eronder beschreef dat gevaar al, voor compliance.
- `founder_taken.FIELD_NOTE_ROL` → website_watcher, die de field_note-skill droeg.
- `claims_board.ROL_IDS` en `cockpit2._COPY_*` → de copywriter, twee keer.

Dezelfde les als bij het claims-domein: leid de rol af uit wat governance vastlegt. Voor een domein
is dat `org.role_for_domain`, voor een middel `org.role_with_skill` — en allebei tellen ze
gearchiveerd niet mee. Niemand die het houdt is een zichtbaar antwoord, geen dood id.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village import claims_board, cockpit2, org, role_proposals


def _rol(rid, *, skills=(), archived=False, slaapt=False):
    return SimpleNamespace(id=rid, archived=archived, slaapt=slaapt,
                           definition=SimpleNamespace(skills=list(skills), domains=[]))


# ── org.role_with_skill: het zusje van role_for_domain ────────────────────────

def test_levende_houder_van_het_middel_wordt_gevonden():
    rollen = [_rol("a", skills=["escaleer"]), _rol("schrijver", skills=["content_schrijven"])]
    assert org.role_with_skill(rollen, "content_schrijven").id == "schrijver"


def test_gearchiveerde_houder_telt_niet_mee():
    """Precies het gat in `records.get(id) is None`: een archief-record bestaat nog."""
    rollen = [_rol("oud", skills=["content_schrijven"], archived=True)]
    assert org.role_with_skill(rollen, "content_schrijven") is None


def test_slapende_houder_telt_niet_mee():
    """Een slapende rol draait geen thread en pakt niets op — werk blijft er liggen."""
    rollen = [_rol("dommel", skills=["field_note"], slaapt=True)]
    assert org.role_with_skill(rollen, "field_note") is None


def test_onbekend_middel_geeft_none():
    assert org.role_with_skill([_rol("a", skills=["escaleer"])], "bestaat_niet") is None
    assert org.role_with_skill([_rol("a", skills=["escaleer"])], "") is None


# ── founder_taken: de twee afgeleide rollen ──────────────────────────────────

def _st(rollen):
    return SimpleNamespace(records=SimpleNamespace(all=lambda: rollen))










# ── de uitgeschakelde copywriter-verwijzingen ────────────────────────────────

def test_copywriter_staat_nergens_meer_als_bestemming():
    """Uitgeschakeld, niet omgeleid: het werk is niet verhuisd maar vervallen. Zou je het label op
    een andere rol zetten, dan draai je dat besluit stilzwijgend terug."""
    dood = "mother_earth__nooch__noochville__copywriter"
    assert dood not in claims_board.ROL_IDS.values()
    assert "copywriter" not in claims_board.ROL_IDS
    assert "copywriter + compliance" not in claims_board.ROL_IDS
    assert dood not in cockpit2._COPY_PROMPT_ROLLEN
    assert dood not in cockpit2._COPY_STACK_ZAAD
    for bronnen in cockpit2._COPY_STACK_ZAAD.values():
        assert dood not in bronnen


def test_compliance_parent_wijst_niet_naar_de_ontbonden_cirkel():
    """Een nieuwe rol onder een gearchiveerde cirkel heeft geen levende ouder."""
    assert role_proposals._COMPLIANCE_PARENT == "mother_earth__nooch"
