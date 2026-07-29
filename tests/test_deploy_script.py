"""Guard op scripts/deploy.sh: elke service die deze code draait wordt ook herstart.

Waarom een test op een shell-script: op 29 juli 2026 herstartte de deploy alleen de cockpit. De
daemon — waar de tend-lus, de bord-puls en al het rolwerk draaien — bleef op de oude code staan,
en de deploy meldde vrolijk "✅ live". De park-fix leek niet te werken tot de daemon apart herstart
werd. Een unit-bestand erbij zonder het aan de deploy toe te voegen is precies dezelfde val, dus de
bron van waarheid (deploy/*.service) en de restart-lijst worden hier tegen elkaar gehouden.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_ROOT, "scripts", "deploy.sh")


def _script() -> str:
    with open(_SCRIPT, encoding="utf-8") as f:
        return f.read()


def _services_in_script() -> list[str]:
    m = re.search(r"^SERVICES=\(([^)]*)\)", _script(), re.M)
    assert m, "SERVICES=(...) niet gevonden in deploy.sh"
    return re.findall(r'"([^"]+)"', m.group(1))


def _units_op_schijf() -> list[str]:
    return sorted(os.path.basename(p)[: -len(".service")]
                  for p in glob.glob(os.path.join(_ROOT, "deploy", "*.service")))


def test_deploy_herstart_elke_gedeployde_service():
    """De harde regel: elke unit in deploy/ staat in de restart-lijst. Vergeet je er één, dan draait
    die na een deploy op oude code — een halve deploy die zich als een hele voordoet."""
    ontbreekt = set(_units_op_schijf()) - set(_services_in_script())
    assert not ontbreekt, (
        f"deploy.sh herstart deze service(s) niet: {sorted(ontbreekt)}. Zet ze in SERVICES=(...), "
        f"anders draait die na een deploy door op de oude code.")


def test_de_daemon_staat_er_expliciet_bij():
    """Named guard op de service die het probleem veroorzaakte — dat mag niemand er stilletjes
    uit halen zonder deze test te zien."""
    assert "noochville-village" in _services_in_script()


def test_rollback_en_health_dekken_alle_services():
    """Rollback en health-check moeten over dezelfde lijst lopen als de restart; anders rolt een
    kapotte deploy maar de helft terug, of keurt hij zichzelf goed terwijl de daemon plat ligt."""
    s = _script()
    assert s.count("alles_gezond") >= 3           # definitie + deploy-pad + rollback-pad
    assert "health_ok || return 1" in s           # web-check zit in de gedeelde poort
    assert "daemon_ok" in s                       # en de niet-web services ook
    assert 'systemctl restart "$svc"' in s        # restart loopt over de lijst, niet over één naam


def test_script_is_syntactisch_geldig():
    assert subprocess.run(["bash", "-n", _SCRIPT], capture_output=True).returncode == 0
