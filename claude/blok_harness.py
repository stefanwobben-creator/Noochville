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

from nooch_village import wiki                            # noqa: E402
from nooch_village.cockpit2_util import _DS_LINK          # noqa: E402
from nooch_village.views.wiki import (_backlink_sectie,   # noqa: E402
                                      _feiten_sectie, _meta_blok, _wiki_editor)
from nooch_village.web_base import _page                  # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parents[1]


class _NepPagina:
    """Genoeg van een artefact om de view te voeden: elk bloksoort één keer."""

    id = "NOTE-HARNESS-001"
    title = "Browsercheck blokmodel"
    anchor = "mother_earth__nooch"
    updated_at = 0
    kind = wiki.PAGINA_KIND
    # DE GEMENGDE VOLGORDE UIT HET ONTWERPDOCUMENT (26 september 2026), letterlijk:
    # tekst → feit → afbeelding → tekst → tekst → drie feiten → link.
    #
    # "Drie feiten" is één `{{facts}}`-blok met drie feiten erin — de markering plaatst de sectie,
    # de sectie draagt de rijen. Daarom staat hij hier één keer, met drie feiten in `meta`.
    #
    # DE OUDE VORM STOND HIERONDER en had elk bloksoort één keer (kop, lijst, citaat, nummering,
    # scheiding). Die blijft, want `blok_browsercheck.js` meet erop — hij is alleen naar voren
    # geschoven zodat de gemengde volgorde erachter aan één stuk te lezen en te screenshotten is.
    body = (
        "### Een kop\n\n"
        "- eerste punt\n- tweede punt\n\n"
        "> een citaat\n\n"
        "1. genummerd\n2. nog een\n\n"
        # EEN BESTAANDE TABEL (26 september 2026). De harness maakte er wel één via het blokmenu,
        # maar er stond er nooit al eentje — en juist die route ("✎ bewerk als tekst" op de greep)
        # kreeg geen uitleg bij het `|---|---|`-sjabloon. Zonder een tabel in de body is dat niet
        # te meten.
        "| Materiaal | Herkomst |\n|---|---|\n| Hennep | NL |\n\n"
        "---\n\n"
        "Een pagina begint met gewone tekst.\n\n"
        # HET AFGELEIDE BLOK. Staat hier omdat het het enige blok is dat FORMULIEREN draagt, en
        # juist die vorm brak: een `<input>` heeft geen eindtag, dus de chrome-teller in
        # `_md_naar_bron` liep op en at de rest van de alinea op.
        "{{facts}}\n\n"
        "![Een schoen op de leest](/wiki-bestand/NOTE-HARNESS-001/schoen.png)\n\n"
        "Tekst onder de afbeelding, want dat is de overgang die moet kloppen.\n\n"
        "En nog een alinea erachteraan, zodat het echt lopende tekst is.\n\n"
        "{{backlinks}}\n\n"
        "[De leveranciersbrief](/wiki-bestand/NOTE-HARNESS-001/brief.pdf)\n\n"
        "De laatste alinea, met een [[Andere pagina]] die nog niet bestaat.\n\n"
        # EEN LÁNGE STAART (26 september 2026), want het zwevende opmaak-balkje moet op een pagina
        # getoetst worden die écht scrolt: een selectie bovenin en een selectie onderin geven
        # tegenovergestelde posities, en juist bij de tweede kon hij half buiten beeld hangen.
        + "\n\n".join(f"Alinea {n} van de lange staart, om de pagina te laten scrollen."
                       for n in range(1, 31))
        + "\n"
    )
    #: DRIE FEITEN, zoals het ontwerpdocument vraagt — en met verschillende grond, zodat de
    #: grond-chips alle drie te zien zijn in plaats van drie keer dezelfde.
    meta = {"feiten": [wiki.maak_feit("Een schoen weegt 300 gram"),
                       wiki.maak_feit("Hennep bindt CO2 tijdens de groei",
                                      soort="bron", url="https://example.org/hennep"),
                       wiki.maak_feit("De zool is volledig plantaardig",
                                      soort="policy", ref="POLICY-MAT-001")]}


class _NepStores:
    """Genoeg van de stores om de twee secties te renderen: ze vragen alleen naar grond."""

    evidence = None
    att = None


#: DE ECHTE RENDERERS, geen nagebouwde HTML. Hier stond een met de hand geschreven `.c2-sec` met
#: `.card`-rijen erin, en dat is precies de val die deze codebase `reference, don't copy` noemt:
#: toen de secties op 26 september hun kader verloren, bleef de harness het oude kader tonen — de
#: pagina waarmee je de vormgeving controleert, liep dan achter op de vormgeving.
_SECTIES = {
    "facts": _feiten_sectie(_NepPagina, _NepStores, "harness-token", True),
    "backlinks": _backlink_sectie(_NepPagina, []),
}


def _proef_png(breedte: int = 560, hoogte: int = 240) -> bytes:
    """Een geldige PNG zonder Pillow — een verloopje, genoeg om te zien DÁT er beeld staat en hoe
    het zich tot de kolom verhoudt. Met de hand, want de harness hoort geen afhankelijkheid te
    hebben die het project zelf niet heeft."""
    import struct, zlib

    rijen = b""
    for y in range(hoogte):
        rijen += b"\x00"                       # filtertype 0 per rij
        for x in range(breedte):
            rijen += bytes((60 + x * 120 // breedte, 150 + y * 80 // hoogte, 90))

    def stuk(soort: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + soort + data
                + struct.pack(">I", zlib.crc32(soort + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + stuk(b"IHDR", struct.pack(">IIBBBBB", breedte, hoogte, 8, 2, 0, 0, 0))
            + stuk(b"IDAT", zlib.compress(rijen, 6))
            + stuk(b"IEND", b""))


def bouw(map_: pathlib.Path) -> pathlib.Path:
    """Schrijft de pagina plus de twee dingen die hij ophaalt (static, de check zelf)."""
    map_.mkdir(parents=True, exist_ok=True)
    # GEEN "EDIT PAGE"-KNOP MEER (26 september 2026). De echte pagina heeft hem ook niet: wie mag
    # bewerken krijgt een bewerkbare pagina zodra hij hem opent. Stond hij hier nog, dan zou de
    # harness een toestand tonen die op prod niet bestaat — en dat is precies waarvoor hij niet is.
    #
    # `.wiki-doc` OMSLUIT TITEL ÉN TEKST, net als in `render_pagina`: één linkerrand, één vlak.
    inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'><div class='wiki-doc'>"
             f"<h1>&#128196; <span id='wiki-titel' class='wiki-titel'>{_NepPagina.title}</span></h1>"
             f"{_wiki_editor(_NepPagina, [], 'harness-token', True, _SECTIES)}"
             # DE VOLGORDE VAN DE ECHTE PAGINA: tekst, dan de metadata-voet. Het losse
             # uploadformulier van #603 stond hier ook; dat is op 26 september vervallen omdat
             # uploaden sindsdien via het blokmenu gaat, op de plek van de `+`.
             # `can_edit=True`, want anders mist de voet juist de twee knoppen die deze ronde
             # toevoegde (Archive en Delete) — die staan achter het bewerkrecht.
             f"{_meta_blok(_NepPagina, None, 'harness-token', True, [])}"
             f"</div></div></div>")
    (map_ / "index.html").write_text(_page("Browsercheck", inner), encoding="utf-8")

    # EEN ECHT BESTAND ACHTER DE AFBEELDING. Zonder dit toont de harness een gebroken `<img>` en
    # weet je niet of je naar een renderfout kijkt of naar een ontbrekend bestand. De harness
    # serveert zijn eigen map, dus `/wiki-bestand/<id>/<naam>` valt hier gewoon op schijf.
    beeld = map_ / "wiki-bestand" / _NepPagina.id
    beeld.mkdir(parents=True, exist_ok=True)
    (beeld / "schoen.png").write_bytes(_proef_png())
    (beeld / "brief.pdf").write_bytes(b"%PDF-1.4\n% proefbestand\n")

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
