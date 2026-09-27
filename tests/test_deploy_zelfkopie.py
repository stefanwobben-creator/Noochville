"""`deploy.sh` overleeft een wijziging aan zichzelf tijdens zijn eigen pull (27 september 2026).

HET PROBLEEM, en het is geen theorie. Dit script ligt IN de repo die het uitrolt, en bash leest een
script INCREMENTEEL: hij onthoudt een positie in het bestand en haalt de volgende opdracht op als hij
eraan toe is. Herschrijft `git merge` het bestand terwijl de run loopt, dan leest die run vanaf die
positie verder in de NIEUWE bytes — en voert uit wat daar toevallig staat. De deploy van die dag is
daarom met de hand omzeild: nieuwe versie naar /tmp, en die gedraaid.

WAT DEZE TOETS DOET, en waarom hij niet op de vorm kijkt. `test_zonder_de_wissel_gaat_het_mis` DRAAIT
een script dat zichzelf overschrijft en laat zien dat het dan iets anders uitvoert dan er in zijn
eigen bron stond. `test_met_de_wissel_gaat_het_goed` draait hetzelfde scenario met het ECHTE blok uit
`deploy.sh` ervoor — uit het bestand geknipt, niet nagetypt — en dan klopt de uitvoer wel. Zonder de
eerste toets bewijst de tweede niets: dan weet je niet of het scenario überhaupt stuk kán.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

WORTEL = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = (WORTEL / "scripts" / "deploy.sh").read_text(encoding="utf-8")


def _blok(kop: str) -> str:
    """Een genummerde sectie uit deploy.sh, tot de volgende sectiekop."""
    m = re.search(rf"^# ── {kop}.*?$(.*?)(?=^# ── |\Z)", DEPLOY, re.M | re.S)
    assert m, f"sectie {kop!r} niet gevonden in deploy.sh"
    return m.group(1)


WISSEL = _blok(r"1\. Uit de vuurlinie")
LOG = next(r for r in DEPLOY.splitlines() if r.startswith("log(){"))


# ══ 1. Staat hij op de goede plek? ═══════════════════════════════════════════
def test_de_wissel_staat_voor_de_pull():
    """DE ENIGE VOLGORDE DIE WERKT. Staat de wissel ná de pull, dan is het script al herschreven
    op het moment dat hij zichzelf kopieert — en kopieert hij de nieuwe helft van een half
    bijgewerkte run."""
    wissel = DEPLOY.index("exec bash \"$KOPIE\"")
    for later in ('git_nooch fetch --quiet origin main',
                  'git_nooch merge --ff-only origin/main',
                  'git_nooch status --porcelain'):
        assert wissel < DEPLOY.index(later), f"de wissel staat ná: {later}"


def test_de_kopie_ligt_buiten_de_repo():
    """Een kopie binnen `$REPO` wordt door de pull net zo hard overschreven als het origineel."""
    assert '/tmp/noochville-deploy-actief.sh' in WISSEL
    assert '"$REPO' not in WISSEL


def test_hij_ruimt_de_kopie_niet_op_terwijl_hij_draait():
    """Opruimen ná afloop is dezelfde fout in het klein: een bestand weghalen dat op dat moment
    wordt uitgevoerd. Vast pad, volgende run overschrijft hem — nooit meer dan één."""
    assert "rm " not in WISSEL and "trap " not in WISSEL


def test_er_zit_een_rem_op():
    """Een `exec` zonder vlag die zegt 'dit is al gebeurd' is een oneindige lus, en die lus draait
    dan als root op de productieserver."""
    assert 'NOOCH_DEPLOY_KOPIE' in WISSEL and 'export NOOCH_DEPLOY_KOPIE' in WISSEL


# ══ 2. Het scenario, echt uitgevoerd ═════════════════════════════════════════
VULLING_OUD, VULLING_NIEUW = 6000, 300


def _schrijf(pad: pathlib.Path, *, wissel: bool, vulling: int, staart: str) -> None:
    """Een miniatuur-deploy: hij zegt START, doet zijn 'pull', en zegt daarna wie hij is.

    De vulling is geen opsmuk. Bash leest met een buffer van enkele kilobytes vooruit; staat de
    laatste regel vlak achter de pull, dan zit hij al in het geheugen en merk je niets. Tienduizenden
    bytes ertussen dwingt hem het bestand opnieuw te lezen — precies wat er bij een echte deploy
    gebeurt, waar tussen de pull en de health-check honderd regels staan.
    """
    kop = f"{LOG}\n{WISSEL}\n" if wissel else ""
    pad.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"{kop}"
        'echo START\n'
        'cp "$NIEUW" "$DOEL"\n'          # ← de 'git pull': het ORIGINEEL wordt herschreven
        + "# vulling\n" * vulling
        + f"echo {staart}\n", encoding="utf-8")


def _draai(tmp_path, *, wissel: bool):
    doel = tmp_path / "deploy.sh"
    nieuw = tmp_path / "nieuwe-versie.sh"
    _schrijf(doel, wissel=wissel, vulling=VULLING_OUD, staart="EIND-OUD")
    _schrijf(nieuw, wissel=wissel, vulling=VULLING_NIEUW, staart="EIND-NIEUW")
    r = subprocess.run(["bash", str(doel)], capture_output=True, text=True, timeout=60,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "DOEL": str(doel),
                           "NIEUW": str(nieuw),
                           "NOOCH_DEPLOY_KOPIE_PAD": str(tmp_path / "kopie-actief.sh")})
    return r


def test_zonder_de_wissel_gaat_het_mis(tmp_path):
    """HET SCENARIO VAN VANDAAG, aantoonbaar. Dit script zegt in zijn eigen bron `EIND-OUD`, maar
    dat is niet wat er gebeurt: bash leest na de overschrijving verder in de nieuwe bytes."""
    r = _draai(tmp_path, wissel=False)
    assert "START" in r.stdout
    assert "EIND-OUD" not in r.stdout, (
        "de lopende run kwam ongeschonden door — dan toont deze toets niets meer aan "
        f"(bash-versie?): {r.stdout!r}")


def test_met_de_wissel_gaat_het_goed(tmp_path):
    """DEZELFDE overschrijving, met het echte blok uit deploy.sh ervoor. De run draait dan vanaf
    een kopie buiten de vuurlinie en maakt zijn eigen versie af."""
    r = _draai(tmp_path, wissel=True)
    assert r.returncode == 0, r.stderr
    assert "EIND-OUD" in r.stdout, r.stdout
    assert "EIND-NIEUW" not in r.stdout, "hij voerde alsnog de nieuwe versie uit"


def test_hij_wisselt_precies_een_keer(tmp_path):
    """De rem, uitgevoerd in plaats van gelezen: twee keer wisselen is een lus."""
    r = _draai(tmp_path, wissel=True)
    assert r.stdout.count("verder vanaf een kopie") == 1, r.stdout
    assert r.stdout.count("draait vanaf de kopie") == 1, r.stdout
    assert r.stdout.count("START") == 1, r.stdout


def test_de_kopie_blijft_bruikbaar_achter(tmp_path):
    """Vast pad, geen opruiming: na afloop ligt er precies één kopie, en dat is de versie die
    gedraaid heeft — handig als je achteraf wilt zien wat er nu eigenlijk is uitgevoerd."""
    r = _draai(tmp_path, wissel=True)
    kopie = tmp_path / "kopie-actief.sh"
    assert r.returncode == 0 and kopie.exists()
    assert "EIND-OUD" in kopie.read_text(encoding="utf-8")
