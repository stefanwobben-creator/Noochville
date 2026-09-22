"""Een standalone wiki-bewerkpagina, zodat `blok_browsercheck.js` in ELKE browser kan draaien.

WAAROM DIT NAAST DE CHECK STAAT. De check meet wat de browser met het blokmodel doet, en dat kan
alleen op een echte bewerkpagina. De gewone cockpit wil daarvoor een dataset, een gebruiker en een
sessie — en in Safari of Firefox heb je die sessie niet, want daar logde je nooit in. Deze harness
haalt dat weg: de HTML komt uit `_wiki_editor` en `_page` (de ECHTE view-code), de JS is
`static/nooch.js` zelf. Er wordt niets nagebouwd, dus er kan ook niets uiteenlopen.

Wat de harness NIET kan is opslaan. Dat is geen gat: de check slaat ook niets op — toets 6
simuleert alleen het uitlezen van de HTML.

    ./venv/bin/python claude/blok_harness.py            # bouwt en serveert op 127.0.0.1:8799
    ./venv/bin/python claude/blok_harness.py --poort 9000

Open daarna de URL in de browser die je wilt nalopen, open de console en plak:

    fetch("/blok_browsercheck.js").then(r => r.text()).then(eval)

De tabel die verschijnt moet overal ✓ zijn. Chrome en Firefox verschillen aantoonbaar in wat
`execCommand` doet (zie de opmerking bij `blokNormaliseer`), dus "het werkt bij mij" is hier geen
uitspraak over de rest.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nooch_village.cockpit2_util import _DS_LINK          # noqa: E402
from nooch_village.views.wiki import _wiki_editor         # noqa: E402
from nooch_village.web_base import _page                  # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parents[1]


class _NepPagina:
    """Genoeg van een artefact om de view te voeden: elk bloksoort één keer."""

    id = "NOTE-HARNESS-001"
    title = "Browsercheck blokmodel"
    anchor = "mother_earth__nooch"
    updated_at = 0
    body = (
        "### Een kop\n\n"
        "Een gewone alinea met wat tekst erin.\n\n"
        "- eerste punt\n- tweede punt\n\n"
        "> een citaat\n\n"
        "1. genummerd\n2. nog een\n\n"
        "---\n\n"
        "De laatste alinea.\n"
    )


def bouw(map_: pathlib.Path) -> pathlib.Path:
    """Schrijft de pagina plus de twee dingen die hij ophaalt (static, de check zelf)."""
    map_.mkdir(parents=True, exist_ok=True)
    start = ("<button type='button' class='btn sm' data-wiki-start>&#9998; Edit page</button>")
    inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
             f"<h1>&#128196; <span id='wiki-titel' class='wiki-titel'>{_NepPagina.title}</span></h1>"
             f"<div class='wiki-kopbalk'>{start}</div>"
             f"{_wiki_editor(_NepPagina, [], 'harness-token', True)}"
             f"</div></div>")
    (map_ / "index.html").write_text(_page("Browsercheck", inner), encoding="utf-8")

    # Symlinks in plaats van kopieën: anders meet je een momentopname van de JS in plaats van de
    # JS. Dat is dezelfde reden als waarom de soorten-tabel van de server meekomt.
    for naam, doel in (("static", WORTEL / "nooch_village" / "static"),
                       ("blok_browsercheck.js", WORTEL / "claude" / "blok_browsercheck.js")):
        koppel = map_ / naam
        if koppel.is_symlink() or koppel.exists():
            koppel.unlink()
        os.symlink(doel, koppel)
    return map_ / "index.html"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="blok_harness")
    ap.add_argument("--poort", type=int, default=8799)
    ap.add_argument("--map", default=None, help="waar de pagina komt (default: een tijdelijke map)")
    a = ap.parse_args(argv)

    map_ = pathlib.Path(a.map) if a.map else pathlib.Path(tempfile.mkdtemp(prefix="blokharness-"))
    pad = bouw(map_)
    print(f"gebouwd: {pad}")
    print(f"open:    http://127.0.0.1:{a.poort}/")
    print('plak in de console: fetch("/blok_browsercheck.js").then(r => r.text()).then(eval)')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(map_))
    with http.server.ThreadingHTTPServer(("127.0.0.1", a.poort), handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\ngestopt.")


if __name__ == "__main__":
    main()
