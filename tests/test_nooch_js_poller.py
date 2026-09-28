"""De JS-toets van de generieke poller, meegenomen in de gewone suite.

`tests/js/poller.test.js` laadt het ECHTE `nooch.js` in een minimale DOM-stub en tikt de poller
met de hand aan. Dit bestand is alleen de doorgeefluik-laag zodat `pytest tests/` hem meeneemt —
de toetsen zelf staan daar, want ze zijn JavaScript.

WAAROM NIET OP DE BRONTEKST ASSERTEN, zoals `test_bezig_indicator.py` doet. Die vorm vangt een
verwijderde regel maar bewijst geen gedrag, en de bug die hier gefixt is (het Topic-veld dat
tijdens het typen werd overschreven) kwam juist van een regel die er hoorde te staan.

ZONDER NODE SLAAT HIJ OVER, en dat is geen gat dat groeit: node staat op de machine waar dit dorp
gebouwd wordt, en de toets draait daar dus echt. Een harde fout zou de suite onbruikbaar maken op
een machine die alleen Python heeft, terwijl er niets aan de hand is.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

TEST_JS = pathlib.Path(__file__).resolve().parent / "js" / "poller.test.js"


def test_de_poller_gedraagt_zich_zoals_beloofd():
    node = shutil.which("node")
    if not node:
        pytest.skip("node niet geïnstalleerd — draai `node tests/js/poller.test.js` met de hand")
    uit = subprocess.run([node, str(TEST_JS)], capture_output=True, text=True, timeout=60)
    assert uit.returncode == 0, f"JS-toetsen rood:\n{uit.stdout}\n{uit.stderr}"
    # De uitvoer meelezen, zodat een stilgevallen harnas (0 toetsen, exit 0) niet groen oogt.
    assert uit.stdout.count("  ok   ") >= 9, f"te weinig toetsen gedraaid:\n{uit.stdout}"
