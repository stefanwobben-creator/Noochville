"""Een statische nav-harness, zodat het navigatiepaneel in ELKE browser te meten is.

WAAROM DIT BESTAAT, en waarom naast `blok_harness.py` in plaats van erin. De wiki-harness zet één
BEWERKPAGINA neer; deze zet een MINI-SITE neer: een startpagina, een node-pagina en het
paneelfragment, zodat je er echt doorheen kunt klikken. Wat je ermee meet is gedrag dat zich pas
laat zien over een paginagrens heen — of het paneel open blijft terwijl je doorbladert, en met
welke `hier` het dan vraagt. Dat is met een enkele pagina niet te zien.

De HTML komt uit `_nav()` en `render_nav_paneel` (de echte view-code), de JS is `static/nooch.js`
zelf via een symlink. Er wordt niets nagebouwd, dus er kan ook niets uiteenlopen.

TWEE DINGEN DIE `python -m http.server` FOUT DOET en die deze server rechtzet:

  1. Een bestand zonder extensie krijgt `application/octet-stream`, en dan DOWNLOADT Chrome
     `/node` in plaats van het te tonen — er navigeert niets en je meet niets.
  2. Zou je er een map `node/` van maken, dan stuurt hij een 301 naar `/node/` en klopt
     `location.pathname === "/node"` niet meer, precies de regel die bepaalt of `hier` meegaat.

WAT DE HARNESS NIET KAN. Het paneelfragment is één vast bestand: de querystring wordt genegeerd,
dus elke `hier` levert dezelfde boom. Je ziet hier dus wél of het paneel terugkomt en wat het
VRAAGT (lees het netwerkverkeer), maar niet of de server de goede tak markeert — dat is een
servervraag en hoort in pytest of op de echte cockpit.

    ./venv/bin/python claude/nav_harness.py --data data/
    # open http://127.0.0.1:8802/ in de browser die je wilt nalopen
    # klik Organization, klik een rol, en kijk of het paneel blijft staan

Wil je het met échte records meten, wijs `--data` dan naar een kopie van de productiedataset.
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

from nooch_village import cockpit2                                      # noqa: E402
from nooch_village.cockpit2_util import (_DS_LINK, _SIDE_OVERLEG,       # noqa: E402
                                         _nav, overleg_items)
from nooch_village.views.navpaneel import render_nav_paneel             # noqa: E402
from nooch_village.web_base import _page                                # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parents[1]


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Zie de moduledocstring: extensieloze bestanden zijn hier HTML, geen download."""

    def guess_type(self, path):
        soort = super().guess_type(path)
        return "text/html" if soort in (None, "application/octet-stream") else soort


def bouw(map_: pathlib.Path, data_dir: str) -> pathlib.Path:
    map_.mkdir(parents=True, exist_ok=True)
    st = cockpit2._Stores(data_dir)
    cid = cockpit2._home_node(st.records.all())
    # `_nav()` laat de overleg-knoppen open als placeholder omdat ze een cirkel-id dragen; in de
    # cockpit vult `_send` ze in. Hier doen we hetzelfde, anders mist de balk twee knoppen.
    nav = _nav().replace(_SIDE_OVERLEG, overleg_items(cid), 1)

    def pagina(titel: str, uitleg: str) -> str:
        return _page(titel, f"{_DS_LINK}{nav}<div class='c2-wrap'><div class='c2-main'>"
                            f"<h1>{titel}</h1><p class='muted'>{uitleg}</p></div></div>")

    (map_ / "index.html").write_text(
        pagina("Harness", "Startpagina. Klik Organization en daarna een rol."), encoding="utf-8")
    # Eén bestand bedient elke `/node?id=…`: de querystring wordt genegeerd. Genoeg om te zien of
    # het paneel de paginagrens overleeft.
    (map_ / "node").write_text(
        pagina("Node", "Een node-pagina. Staat het paneel er nog?"), encoding="utf-8")
    # EN EEN PAGINA DIE GEEN NODE IS, want de helft van het gedrag gaat daarover: het paneel hoort
    # bij Organization, dus op het scherm van een ánder hoofditem hoort hij dicht te zijn. Zonder
    # deze pagina kon de harness alleen de helft meten die goed ging.
    (map_ / "wiki").write_text(
        pagina("Wiki", "Een ander hoofditem. Hier hoort het paneel dicht te zijn."),
        encoding="utf-8")
    (map_ / "nav-paneel").write_text(render_nav_paneel(st, "org", ""), encoding="utf-8")

    koppel = map_ / "static"
    if koppel.is_symlink() or koppel.exists():
        koppel.unlink()
    os.symlink(WORTEL / "nooch_village" / "static", koppel)
    return map_ / "index.html"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="nav_harness")
    ap.add_argument("--poort", type=int, default=8802)
    ap.add_argument("--data", default="data", help="de dataset waaruit de boom wordt gevuld")
    ap.add_argument("--map", default=None, help="waar de site komt (default: een tijdelijke map)")
    a = ap.parse_args(argv)

    map_ = pathlib.Path(a.map) if a.map else pathlib.Path(tempfile.mkdtemp(prefix="navharness-"))
    bouw(map_, a.data)
    print(f"gebouwd: {map_}")
    print(f"open:    http://127.0.0.1:{a.poort}/")
    print("meet:    klik Organization → een rol (/node): blijft staan;"
          " daarna /wiki: dicht")
    handler = functools.partial(_Handler, directory=str(map_))
    with http.server.ThreadingHTTPServer(("127.0.0.1", a.poort), handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\ngestopt.")


if __name__ == "__main__":
    main()
