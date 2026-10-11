"""`deploy.sh` draait nooit twee keer tegelijk (11 oktober 2026).

WAT ER GEBEURDE. Eén deploy-opdracht opende twee ssh-sessies drie seconden na elkaar, en dus twee runs
tegelijk: de eerste rolde uit en herstartte, de tweede meldde "geen nieuwe commit" — en dat was de
uitvoer die terugkwam. Zie sectie 0b in `scripts/deploy.sh`.

WAT DEZE TOETS DOET. Hij knipt het ECHTE slot-blok (0b) en de ECHTE wissel (1) uit `deploy.sh`, zet
er een run achter die blijft lopen tot de toets hem loslaat, en start daar een tweede naast.
`test_zonder_slot_lopen_ze_allebei` laat eerst zien dat het scenario zonder slot echt stuk kan; anders
bewijst de rest niets. `flock` zit in util-linux (de server, CI); op een Mac zonder flock slaan de
drie toetsen die het slot draaien over, op Linux falen ze dan juist. De volgorde-toets draait overal.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

import pytest

WORTEL = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = (WORTEL / "scripts" / "deploy.sh").read_text(encoding="utf-8")

# Alleen de toetsen die het slot ÉCHT draaien hebben flock nodig. Op Linux nooit overslaan: daar
# hoort flock er te zijn, en ontbreekt hij, dan moet dat rood worden.
vereist_flock = pytest.mark.skipif(shutil.which("flock") is None and not sys.platform.startswith("linux"),
                                   reason="geen flock op dit systeem (macOS); CI en de server hebben hem")


def _blok(kop: str) -> str:
    m = re.search(rf"^# ── {kop}.*?$(.*?)(?=^# ── |\Z)", DEPLOY, re.M | re.S)
    assert m, f"sectie {kop!r} niet gevonden in deploy.sh"
    return m.group(1)


SLOT = _blok(r"0b\. Eén deploy tegelijk")
WISSEL = _blok(r"1\. Uit de vuurlinie")
HULP = "\n".join(r for r in DEPLOY.splitlines() if r.startswith(("log(){", "fout(){")))


def _script(tmp_path, *, slot: bool) -> pathlib.Path:
    """Een miniatuur-deploy: slot, wissel naar een kopie, en dan 'werk' tot het STOP-bestand er is."""
    pad = tmp_path / "deploy.sh"
    pad.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + HULP + "\n"
                   + (SLOT if slot else "") + WISSEL
                   + 'echo "BEZIG $$"\n'
                   + 'while [ ! -e "$STOP" ]; do sleep 0.05; done\necho KLAAR\n', encoding="utf-8")
    return pad


def _env(tmp_path, naam):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "STOP": str(tmp_path / "stop"),
            "NOOCH_DEPLOY_SLOT_PAD": str(tmp_path / "deploy.lock"),
            "NOOCH_DEPLOY_KOPIE_PAD": str(tmp_path / f"kopie-{naam}.sh")}


def _start(tmp_path, pad, naam):
    p = subprocess.Popen(["bash", str(pad)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, env=_env(tmp_path, naam))
    regel = ""
    eind = time.time() + 10
    while time.time() < eind and "BEZIG" not in regel:   # wacht tot hij voorbij de wissel is
        regel = p.stdout.readline()
        if not regel and p.poll() is not None:
            break
    return p, regel


def _tweede(tmp_path, pad):
    return subprocess.run(["bash", str(pad)], capture_output=True, text=True, timeout=10,
                          env=_env(tmp_path, "b"))


@vereist_flock
def test_zonder_slot_lopen_ze_allebei(tmp_path):
    """Het scenario van 11 oktober: zonder slot komt een tweede run gewoon langs."""
    pad = _script(tmp_path, slot=False)
    a, _ = _start(tmp_path, pad, "a")
    try:
        b, regel = _start(tmp_path, pad, "b")
        assert "BEZIG" in regel, "zonder slot zou de tweede run moeten draaien — de toets toont niets aan"
    finally:
        (tmp_path / "stop").touch()
        a.wait(10)
        b.wait(10)


@vereist_flock
def test_een_tweede_run_stopt_meteen_met_een_duidelijke_melding(tmp_path):
    pad = _script(tmp_path, slot=True)
    a, regel = _start(tmp_path, pad, "a")
    assert "BEZIG" in regel, a.stderr.read() if a.poll() is not None else regel
    try:
        # A draait nu vanaf zijn KOPIE (de wissel deed `exec`): het slot moet die wissel overleven.
        b = _tweede(tmp_path, pad)
        assert b.returncode == 3, (b.returncode, b.stdout, b.stderr)
        assert "BEZIG" not in b.stdout                                  # niets gedaan
        assert "er loopt al een deploy" in b.stderr and "er is niets gedaan" in b.stderr
        assert f"pid {regel.split()[1]}" in b.stderr                    # zegt wíe er loopt
    finally:
        (tmp_path / "stop").touch()
        assert a.wait(10) == 0


@vereist_flock
def test_na_afloop_is_het_slot_weer_vrij(tmp_path):
    pad = _script(tmp_path, slot=True)
    a, _ = _start(tmp_path, pad, "a")
    (tmp_path / "stop").touch()
    assert a.wait(10) == 0
    c = _tweede(tmp_path, pad)
    assert c.returncode == 0 and "KLAAR" in c.stdout, (c.stdout, c.stderr)


def test_het_slot_staat_voor_de_wissel_en_voor_elke_git_actie():
    """Na de wissel is te laat: dan kan een tweede run al aan zijn kopie begonnen zijn. Alleen
    CODEregels tellen: de uitleg in sectie 0b noemt `exec bash "$KOPIE"` zelf ook."""
    code = [(i, r) for i, r in enumerate(DEPLOY.splitlines()) if not r.lstrip().startswith("#")]
    regel = lambda tekst: next(i for i, r in code if tekst in r)
    slot = regel("flock -n 9")
    for later in ('exec bash "$KOPIE"', "git_nooch status --porcelain", "git_nooch fetch --quiet origin main",
                  "git_nooch merge --ff-only origin/main"):
        assert slot < regel(later), f"het slot staat ná: {later}"
