"""De radar-skills zijn geregistreerd én lopen mee op de puls.

WAAROM DIT EEN TEST IS EN GEEN AANNAME: een grant naar een niet-geregistreerde skill is een LEGE
VERWIJZING — de rol draagt dan een capability-naam die nergens op wijst, en `_run_pulse_skills`
slaat hem over als "niet van deze rol". Dat zou eruitzien als een werkende motor die niets doet.

De droge run op prod ving die volgorde-fout: daar bestonden de skills nog niet in de registry, dus
een grant vóór de deploy zou precies dat opgeleverd hebben.
"""
from __future__ import annotations

import configparser
import pathlib

from nooch_village.registry_factory import build_skill_registry

RADAR_SKILLS = ("materiaal_kwartaal", "materiaal_shortlist")


def test_beide_skills_zitten_in_de_registry():
    reg = build_skill_registry()
    for naam in RADAR_SKILLS:
        assert reg.get(naam) is not None, naam


def test_ze_lopen_mee_op_de_dagpuls():
    """`pulse_skills` bepaalt wélke skills de puls aanbiedt; zonder deze regel draaien ze nooit."""
    cp = configparser.ConfigParser()
    cp.read(pathlib.Path("config/settings.ini"))
    ps = cp.defaults().get("pulse_skills", "")
    for naam in RADAR_SKILLS:
        assert naam in ps, f"{naam} ontbreekt in pulse_skills: {ps!r}"


def test_de_bestaande_pulse_skills_blijven_staan():
    """Toevoegen mag nooit vervangen: claims_site_scan en regulation_watch draaien al."""
    cp = configparser.ConfigParser()
    cp.read(pathlib.Path("config/settings.ini"))
    ps = cp.defaults().get("pulse_skills", "")
    assert "claims_site_scan" in ps and "regulation_watch" in ps


def test_hun_kost_is_puls_veilig():
    """De pulslus draait ze elke dag; een dure skill hoort daar niet ongemarkeerd in. Beide lezen
    de eigen store — de ladder is de enige externe kost, en die zit achter hun periode-poort."""
    reg = build_skill_registry()
    for naam in RADAR_SKILLS:
        assert reg.get(naam).cost == "free", naam
