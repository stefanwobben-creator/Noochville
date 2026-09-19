"""Claims losgekoppeld van rol en persona (fase 5, 19 september 2026).

De governance-vraag "wie houdt het claims-domein vóór 27 september" is beantwoord met: niemand
hoeft het te houden, iemand moet het draaien. Dat heeft drie gevolgen, en alle drie staan hier
vast omdat ze met de hand terugsluipen:

1. de twee claims-skills lopen NIET meer mee op de dagpuls — ze zijn knoppen;
2. de curatie-poort vraagt niet meer naar een domein-eigenaar, alleen naar een ingelogde mens;
3. de authenticatie-helft van die poort blijft wél staan (guest mag alles, ingelogde-onbekende
   wordt geweigerd) — de rol-eis eruit halen mag de login niet meesleuren.
"""
from __future__ import annotations

import configparser
import os
from types import SimpleNamespace

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 1. niet meer op de puls ──────────────────────────────────────────────────
def test_de_claims_skills_staan_niet_meer_in_pulse_skills():
    cp = configparser.ConfigParser()
    cp.read(os.path.join(PKG, "config", "settings.ini"))
    skills = [s.strip() for s in cp["DEFAULT"].get("pulse_skills", "").split(",") if s.strip()]
    assert "claims_site_scan" not in skills
    assert "regulation_watch" not in skills
    # De materiaal-skills blijven wél: die horen bij een levende rol met een eigen ritme.
    assert "materiaal_kwartaal" in skills


def test_de_dna_grant_is_niet_ingetrokken():
    """De skills MOGEN nog; ze gaan alleen niet meer uit zichzelf lopen. Zou de grant ook weg zijn,
    dan kon de knop hem niet meer draaien — en dat is een andere beslissing."""
    from nooch_village.registry_factory import build_skill_registry
    namen = set(build_skill_registry().names())
    assert {"claims_site_scan", "regulation_watch"} <= namen


# ── 2. de poort vraagt niet meer naar een eigenaar ───────────────────────────
def _st(persoon_bekend: bool):
    return SimpleNamespace(
        people=SimpleNamespace(by_email=lambda u: object() if persoon_bekend else None),
        records=None)


def test_zonder_domein_eigenaar_mag_een_ingelogde_mens_gewoon_cureren():
    """Dit was de blokkade: het claims-domein heeft sinds 18 september geen levende eigenaar, en de
    oude poort weigerde dan iedereen — met een EmpCo-deadline op 27 september."""
    from nooch_village import cockpit2
    assert cockpit2._claims_gate(_st(True), "iemand@nooch.earth") is None
    assert cockpit2._claims_gate_open(_st(True), "iemand@nooch.earth") is True


def test_guest_mag_alles_zoals_bij_elke_andere_poort():
    from nooch_village import cockpit2
    assert cockpit2._claims_gate(_st(False), "guest") is None


def test_een_ingelogde_onbekende_wordt_nog_steeds_geweigerd():
    """Fail-closed blijft. De rol-eis eruit halen mag de authenticatie niet meeslepen."""
    from nooch_village import cockpit2
    deny = cockpit2._claims_gate(_st(False), "vreemde@elders.nl")
    assert deny and "not recognised" in deny


def test_de_poort_noemt_geen_rol_of_domein_meer():
    """Geen 'alleen de rolvervuller of Circle Lead', geen 'assign it via governance'."""
    from nooch_village import cockpit2
    import inspect
    body = inspect.getsource(cockpit2._claims_gate)
    code = "\n".join(r for r in body.splitlines() if not r.strip().startswith("#"))
    assert "_role_gate" not in code and "_claims_rol" not in code


# ── 3. de knoppen ────────────────────────────────────────────────────────────
def test_beide_skills_hebben_een_knop_op_claims():
    from nooch_village.views.claims import _blok_skills
    html = _blok_skills("TOK")
    assert "value='claims_site_scan'" in html and "value='regulation_watch'" in html
    assert "value='claims_skill'" in html                   # de dispatch-actie
    assert "style=" not in html                             # designsysteem-regel


def test_de_knop_weigert_een_skill_die_er_niet_bij_hoort():
    """De actie draait ALLEEN de twee claims-skills. Zonder die lijst was dit een algemene
    'draai willekeurige skill'-knop achter een claims-poort."""
    from nooch_village import cockpit2
    c = SimpleNamespace(nxt="/claims", st=_st(True), username="guest",
                        g=lambda k: {"skill": "shopify_sales"}.get(k, ""))
    _, msg = cockpit2._act_claims_skill(c)
    assert "unknown claims skill" in msg
