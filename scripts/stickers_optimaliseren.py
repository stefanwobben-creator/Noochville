"""Maak de merk-stickers klein genoeg voor een kiezer die in één keer laadt.

DE AANLEIDING, met het getal erbij: de globe-mascotte was 5,0 MB en de hele set 10 MB. Een rij
van negen stickers boven een tekstvak die 10 MB moet ophalen is geen kiezer maar een download.

WAT ER TE HALEN VALT, en waarom dat niet "de kwaliteit verlagen" is:
  * ze zijn allemaal ~480px en worden als duimnagel getoond. Een sticker van 480px is vier keer
    zoveel beeld als er op het scherm past (240px dekt ook een retina-scherm);
  * de twee dikste hebben 168 en 188 frames. Dat is een animatie van zes seconden in een vakje
    van twee centimeter. Elke tweede frame eruit halen halveert het bestand en verdubbelt de
    frametijd, dus de animatie loopt even snel als eerst — alleen met minder tussenstapjes.

HET REKENHART STAAT IN `nooch_village/stickers.py` en niet meer hier. Een gekozen Giphy-sticker
krijgt dezelfde behandeling als de acht eigen stickers, en dat kan alleen als beide dezelfde
functie aanroepen: een script onder `scripts/` valt niet te importeren vanuit de cockpit. Hier
blijft wat van het script is — de CLI, de bronmap, het golden contactvel.

Fail-closed: hij schrijft alleen naar `nooch_village/static/stickers/` en laat de bron in
`claude/stickers_22sept/` ongemoeid, zodat je altijd terug kunt naar het origineel.

    ./venv/bin/python scripts/stickers_optimaliseren.py [--apply]

Zonder `--apply` rekent hij alleen voor wat het zou worden.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image

from nooch_village.stickers import (CAP_BYTES, TRAPPEN,   # noqa: F401 — TRAPPEN in de melding
                                    _bouw, _schrijf_naar)

BRON = os.path.join(os.path.dirname(__file__), "..", "claude", "stickers_22sept")
DOEL = os.path.join(os.path.dirname(__file__), "..", "nooch_village", "static", "stickers")
GOLDEN = os.path.join(os.path.dirname(__file__), "..", "tests", "golden",
                      "stickers_referentie.png")
TEGEL = 64            # de referentie-duimnagel; groot genoeg om kleurverval te zien

def optimaliseer(naam: str, apply: bool) -> tuple[int, int, tuple]:
    """(bytes voor, bytes na, de gebruikte trap)."""
    bron = os.path.join(BRON, naam)
    voor = os.path.getsize(bron)
    import io
    beste = None
    with Image.open(bron) as im:
        for trap in TRAPPEN:
            frames, duur, transp = _bouw(im, *trap)
            buf = io.BytesIO()
            _schrijf_naar(frames, duur, transp, buf)
            if beste is None or buf.tell() < beste[0]:
                beste = (buf.tell(), frames, duur, transp, trap)
            if buf.tell() <= CAP_BYTES:
                beste = (buf.tell(), frames, duur, transp, trap)
                break
    n, frames, duur, transp, trap = beste
    if apply:
        os.makedirs(DOEL, exist_ok=True)
        doel = os.path.join(DOEL, naam)
        _schrijf_naar(frames, duur, transp, doel)
        n = os.path.getsize(doel)
    return voor, n, trap


def tegel(pad, grootte: int = TEGEL):
    """Het eerste frame als duimnagel op wit. Op wit, want een doorzichtige achtergrond die
    verkeerd wordt ingekleurd is precies wat we willen zien."""
    im = Image.open(pad)
    im.seek(0)
    f = im.convert("RGBA")
    f.thumbnail((grootte, grootte), Image.LANCZOS)
    vel = Image.new("RGBA", (grootte, grootte), (255, 255, 255, 255))
    vel.paste(f, ((grootte - f.width) // 2, (grootte - f.height) // 2), f)
    return vel.convert("RGB")


def contactvel(map_: str, namen) -> "Image.Image":
    """Alle duimnagels naast elkaar in één strook."""
    vel = Image.new("RGB", (TEGEL * len(namen), TEGEL), (255, 255, 255))
    for i, n in enumerate(namen):
        vel.paste(tegel(os.path.join(map_, n)), (i * TEGEL, 0))
    return vel


def schrijf_referentie(namen) -> str:
    """Het contactvel van de BRONNEN, als golden file voor `tests/test_stickers_giphy.py`.

    WAAROM DIT BESTAAT. De eerste versie van die test vergeleek rechtstreeks met
    `claude/stickers_22sept/`, en die map staat niet in git: op CI werd elk bestand
    overgeslagen en de test toetste nul stickers. Hij viel om op zijn eigen ondergrens-assert —
    precies waarvoor die er stond, maar pas nadat hij lokaal groen was.

    Een golden file van 9 duimnagels is klein genoeg om te committen en is wél wat er echt
    toe doet: hoe de stickers ERUIT ZIEN. Een cap op bestandsgrootte liet de ronde door waarin
    de globe een zwart vlak werd; dit vel niet."""
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    contactvel(BRON, namen).save(GOLDEN, optimize=True)
    return GOLDEN


def main(argv=None) -> int:
    apply = "--apply" in (argv if argv is not None else sys.argv[1:])
    namen = sorted(n for n in os.listdir(BRON) if n.endswith(".gif"))
    tv = tn = 0
    te_groot = []
    for n in namen:
        voor, na, trap = optimaliseer(n, apply)
        tv += voor
        tn += na
        vlag = ""
        if na > CAP_BYTES:
            te_groot.append(n)
            vlag = "  ← boven de cap, ook op de laagste trap"
        print(f"{n:26} {voor/1024:8.0f} kB → {na/1024:6.0f} kB  ({na/voor*100:4.1f}%)  "
              f"{trap[0]}px/{trap[1]}f/{trap[2]}kl{vlag}")
    print(f"{'TOTAAL':26} {tv/1024:8.0f} kB → {tn/1024:6.0f} kB  ({tn/tv*100:4.1f}%)")
    if apply:
        pad = schrijf_referentie(namen)
        print(f"referentie-contactvel: {pad} ({os.path.getsize(pad)/1024:.0f} kB)")
    else:
        print("\nDROGE RUN — er is niets geschreven. Draai met --apply.")
    return 1 if te_groot else 0


if __name__ == "__main__":
    raise SystemExit(main())
