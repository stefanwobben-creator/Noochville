"""Maak de merk-stickers klein genoeg voor een kiezer die in één keer laadt.

DE AANLEIDING, met het getal erbij: de globe-mascotte was 5,0 MB en de hele set 10 MB. Een rij
van negen stickers boven een tekstvak die 10 MB moet ophalen is geen kiezer maar een download.

WAT ER TE HALEN VALT, en waarom dat niet "de kwaliteit verlagen" is:
  * ze zijn allemaal ~480px en worden als duimnagel getoond. Een sticker van 480px is vier keer
    zoveel beeld als er op het scherm past (240px dekt ook een retina-scherm);
  * de twee dikste hebben 168 en 188 frames. Dat is een animatie van zes seconden in een vakje
    van twee centimeter. Elke tweede frame eruit halen halveert het bestand en verdubbelt de
    frametijd, dus de animatie loopt even snel als eerst — alleen met minder tussenstapjes.

Fail-closed: hij schrijft alleen naar `nooch_village/static/stickers/` en laat de bron in
`claude/stickers_22sept/` ongemoeid, zodat je altijd terug kunt naar het origineel.

    ./venv/bin/python scripts/stickers_optimaliseren.py [--apply]

Zonder `--apply` rekent hij alleen voor wat het zou worden.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageSequence

BRON = os.path.join(os.path.dirname(__file__), "..", "claude", "stickers_22sept")
DOEL = os.path.join(os.path.dirname(__file__), "..", "nooch_village", "static", "stickers")
GOLDEN = os.path.join(os.path.dirname(__file__), "..", "tests", "golden",
                      "stickers_referentie.png")
TEGEL = 64            # de referentie-duimnagel; groot genoeg om kleurverval te zien

CAP_BYTES = 300 * 1024   # per sticker; `test_stickers.py` bewaakt dezelfde grens

#: De trappen, van mooi naar klein: (langste zijde, max frames, kleuren). We nemen de EERSTE die
#: onder de cap blijft, per bestand. Zo betaalt alleen de sticker die het probleem is: de globe
#: zakt naar 200px/64 kleuren, de andere acht blijven op de bovenste trede staan. Eén vaste
#: instelling voor de hele set zou betekenen dat acht stickers lelijker worden omdat er één uit
#: de bocht vliegt.
TRAPPEN = ((240, 32, 96), (240, 32, 64), (200, 32, 64), (200, 24, 64))


def _bouw(im: Image.Image, zijde: int, max_frames: int, kleuren: int):
    """(frames, frametijd in ms) op één gedeeld palet.

    DRIE DINGEN DIE HIER MIS GINGEN, en het contactvel liet ze alle drie zien terwijl de
    bestandsgrootte er prima uitzag:

      1. `convert("P", palette=ADAPTIVE)` per frame geeft ELK frame een eigen palet. Dat is
         groter én het laat een animatie flikkeren;
      2. `info["transparency"] = 0` wijst index 0 aan als doorzichtig. In een adaptief palet is
         index 0 gewoon een kleur — meestal de meest voorkomende. De globe kreeg zo een zwart
         vlak en de peace-hand werd cyaan;
      3. quantiseren vanuit RGBA gooit de alfa weg op een manier die de randen mangelt.

    Nu: één palet, afgeleid van het eerste frame, met één EXTRA index erachter die nergens
    anders voor wordt gebruikt — dát is de doorzichtige. De alfa van elk frame wordt apart
    bewaard en als masker teruggezet.

    De frames worden uitgedund met een vaste stap, en de frametijd gaat maal die stap: de
    animatie DUURT even lang als eerst, hij heeft alleen minder tussenstapjes."""
    totaal = getattr(im, "n_frames", 1)
    stap = max(1, -(-totaal // max_frames))          # ceil, zodat we onder de framecap blijven
    duur = int(im.info.get("duration") or 80) * stap

    im.seek(0)
    eerste = im.convert("RGBA")
    eerste.thumbnail((zijde, zijde), Image.LANCZOS)
    palet = eerste.convert("RGB").quantize(colors=kleuren, method=Image.MEDIANCUT)
    rgb = palet.getpalette()[:3 * kleuren] + [255, 0, 255]   # +1 gereserveerde index
    transp = kleuren

    frames = []
    for i, frame in enumerate(ImageSequence.Iterator(im)):
        if i % stap:
            continue
        f = frame.convert("RGBA")
        f.thumbnail((zijde, zijde), Image.LANCZOS)
        alpha = f.getchannel("A")
        q = f.convert("RGB").quantize(palette=palet, dither=Image.FLOYDSTEINBERG)
        q.putpalette(rgb)
        q.paste(transp, mask=alpha.point(lambda a: 255 if a < 128 else 0))
        q.info["transparency"] = transp
        frames.append(q)
    return frames, max(duur, 20), transp


def _schrijf(frames, duur, transp, doel=None) -> int:
    """Naar schijf of naar een buffer — dezelfde opslag-instellingen, zodat de droge run
    hetzelfde getal geeft als de echte."""
    import io
    uit = doel or io.BytesIO()
    frames[0].save(uit, format=("GIF" if doel is None else None), save_all=True,
                   append_images=frames[1:], loop=0, duration=duur,
                   optimize=True, disposal=2, transparency=transp)
    return os.path.getsize(doel) if doel else uit.tell()


def optimaliseer(naam: str, apply: bool) -> tuple[int, int, tuple]:
    """(bytes voor, bytes na, de gebruikte trap)."""
    bron = os.path.join(BRON, naam)
    voor = os.path.getsize(bron)
    beste = None
    with Image.open(bron) as im:
        for trap in TRAPPEN:
            frames, duur, transp = _bouw(im, *trap)
            n = _schrijf(frames, duur, transp)
            if beste is None or n < beste[0]:
                beste = (n, frames, duur, transp, trap)
            if n <= CAP_BYTES:
                beste = (n, frames, duur, transp, trap)
                break
    n, frames, duur, transp, trap = beste
    if apply:
        os.makedirs(DOEL, exist_ok=True)
        doel = os.path.join(DOEL, naam)
        _schrijf(frames, duur, transp, doel)
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
