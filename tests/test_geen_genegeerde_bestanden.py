"""Ratchet: geen enkel TRACKED bestand mag door .gitignore genegeerd worden.

Op 5 september bleek dat 77 bestanden tracked stonden terwijl `.gitignore` ze noemt: de hele
`_to_delete/`-map (git-lockbestanden, een rebase-merge-state, 14 MB aan tarballs), 21 gegenereerde
competitor-rapporten in `output/`, twee `.pyc`-bestanden, een gitlink naar een los project, en
`materiaal_memo.json` — dat laatste is LIVE state die de server elke dag herschrijft.

Dat is geen netheidskwestie. Twee dingen gaan er echt van stuk:

1. **De deploy-guard breekt.** `scripts/deploy.sh` weigert te deployen zodra er een tracked
   wijziging in de working tree staat (regel 99, `--untracked-files=no`). Een tracked bestand dat de
   server zelf elke dag herschrijft zet die guard permanent op rood, en de rollback (`reset --hard`)
   gooit het weg.
2. **Elke checkout blokkeert.** Een gegenereerd rapport dat opnieuw geschreven wordt, maakt
   `git checkout` onmogelijk tot je het handmatig weggooit.

`.gitignore` repareert dit NIET achteraf: de regels gelden alleen voor bestanden die nog niet in de
index staan. Wat er eenmaal in zit, blijft erin tot iemand `git rm --cached` draait. Vandaar deze
ratchet: hij vangt het bij de commit in plaats van bij de deploy.

Repareren: `bash scratch/aanbod/opruimen_repo.sh --apply`
"""
from __future__ import annotations
import os
import shutil
import subprocess

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args, invoer: bytes | None = None):
    return subprocess.run(["git", "--no-optional-locks", *args], cwd=_ROOT,
                          input=invoer, capture_output=True)


def test_geen_tracked_bestand_wordt_genegeerd():
    if shutil.which("git") is None:
        pytest.skip("git niet beschikbaar")
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("geen git-repo (bv. een export of een tarball-checkout)")

    tracked = _git("ls-files", "-z")
    assert tracked.returncode == 0, tracked.stderr.decode(errors="replace")

    # --no-index is essentieel: zonder die vlag slaat check-ignore juist de bestanden over die in de
    # index staan, en dat zijn precies de bestanden waar deze test over gaat.
    genegeerd = _git("check-ignore", "--no-index", "--stdin", "-z", invoer=tracked.stdout)
    paden = [p for p in genegeerd.stdout.decode(errors="replace").split("\0") if p]

    assert not paden, (
        f"{len(paden)} tracked bestand(en) worden door .gitignore genegeerd:\n  "
        + "\n  ".join(sorted(paden)[:20])
        + (f"\n  … en nog {len(paden) - 20}" if len(paden) > 20 else "")
        + "\n\n.gitignore werkt niet met terugwerkende kracht: wat al in de index staat blijft "
          "tracked. Haal ze eruit met `bash scratch/aanbod/opruimen_repo.sh --apply` (dat draait "
          "`git rm --cached` en laat de bestanden op schijf staan), of — als het bestand er WEL in "
          "hoort — haal het uit .gitignore."
    )
