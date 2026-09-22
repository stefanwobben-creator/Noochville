"""Het rekenhart van de sticker-optimalisatie: één GIF in, een kleinere GIF uit.

DIT STOND IN `scripts/stickers_optimaliseren.py` EN MOEST ERUIT toen een gekozen Giphy-sticker
dezelfde behandeling moest krijgen als de acht eigen stickers. Een script onder `scripts/` is
geen importeerbare module, dus de keuze was: overtypen in de cockpit, of het hart hierheen
verhuizen. Overtypen zou betekenen dat een Giphy-sticker er na één wijziging anders uitziet dan
de eigen rij — precies de klasse fout die `reference, don't copy` verbiedt.

Het script houdt wat van het script is: de CLI, de bronmap, het golden contactvel. Hier woont
alleen de vraag "hoe maak ik deze GIF klein zonder dat hij er anders uitziet".
"""
from __future__ import annotations

import io

from PIL import Image, ImageSequence

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


def _schrijf_naar(frames, duur, transp, uit) -> None:
    """Eén plek met de opslag-instellingen, zodat een droge run hetzelfde bestand oplevert als
    de echte en een Giphy-sticker hetzelfde als een eigen sticker."""
    naar_bestand = isinstance(uit, str)
    frames[0].save(uit, format=(None if naar_bestand else "GIF"), save_all=True,
                   append_images=frames[1:], loop=0, duration=duur,
                   optimize=True, disposal=2, transparency=transp)




def optimaliseer_bytes(data: bytes, cap: int = CAP_BYTES) -> bytes:
    """Een GIF in, de kleinste acceptabele GIF uit. Gooit door bij onleesbare invoer — de
    aanroeper weet of dat erg is.

    DEZELFDE TRAP ALS DE EIGEN STICKERS, en dat is het hele punt van deze functie: een sticker
    die je uit Giphy kiest hoort er in de draad net zo uit te zien en even zwaar te zijn als
    een sticker uit de vaste rij. Twee paden zouden binnen een maand twee formaten geven."""
    beste = None
    with Image.open(io.BytesIO(data)) as im:
        for trap in TRAPPEN:
            frames, duur, transp = _bouw(im, *trap)
            buf = io.BytesIO()
            _schrijf_naar(frames, duur, transp, buf)
            n = buf.tell()
            if beste is None or n < beste[0]:
                beste = (n, buf.getvalue())
            if n <= cap:
                return buf.getvalue()
    return beste[1]
