"""Compositie-adapters: vertalen een domein-'snede' naar constituenten voor de belofte-graaf.

Dit is de DOMEIN-laag. De belofte-graaf (belofte_graaf.py) kent geen BOM en geen dienst;
hij krijgt een lijst Constituenten. Een fysiek product levert die via zijn Bill of Materials
(ontleed_bom), een dienst via zijn voorwaarden-ontwerp (ontleed_voorwaarden). Beide geven
dezelfde vorm terug, zodat de kern abstract blijft.
"""
from __future__ import annotations

from nooch_village.belofte_graaf import Constituent


def _split_comment(velden: list[str]) -> tuple[list[str], str]:
    """Splits een rij in (kop, commentaar). Het commentaar begint bij de eerste cel die
    met '<' opent (BOM-conventie voor een opmerking/alternatief)."""
    for i, v in enumerate(velden):
        if v.startswith("<"):
            return velden[:i], " ".join(velden[i:])
    return velden, ""


def _alternatieven(comment: str) -> tuple[str, ...]:
    """Haal kandidaat-realisaties uit een BOM-commentaar. 'Or X, Or Y' → (X, Y). Een vrije
    check-opmerking zonder 'Or' ('Might be linen thread, please check') levert géén
    alternatief — dat is een vraag, geen kandidaat."""
    c = comment.strip().lstrip("<").strip()
    if not c:
        return ()
    alts = []
    for stuk in c.split(","):
        s = stuk.strip()
        if s.lower().startswith("or "):
            kandidaat = s[3:].strip()
            if kandidaat:
                alts.append(kandidaat)
    return tuple(alts)


def ontleed_bom(tekst: str, bron: str = "BOM") -> list[Constituent]:
    """Parse een (tab- of dubbelspatie-gescheiden) Bill of Materials naar constituenten.

    Tolerant voor een leidende status/legenda-kolom: per rij worden de cellen ontdaan van
    lege waarden, het commentaar (vanaf '<') afgesplitst, en Part + Material als de laatste
    twee kop-cellen genomen. Zo werkt zowel 'Done<tab><tab>Outsole<tab>Pliant' als
    '<tab><tab>Eyestay<tab>HyphaLite'. De koprij (Part/Material) wordt overgeslagen."""
    uit: list[Constituent] = []
    for regel in tekst.splitlines():
        if not regel.strip():
            continue
        rauw = regel.split("\t") if "\t" in regel else __import__("re").split(r"\s{2,}", regel)
        velden = [v.strip() for v in rauw if v.strip() != ""]
        if len(velden) < 2:
            continue
        kop, comment = _split_comment(velden)
        if len(kop) < 2:
            continue
        laag = {c.lower() for c in kop}
        if {"part", "material"} <= laag:
            continue  # koprij (ongeacht hoeveel kolommen ervoor staan)
        part, material = kop[-2], kop[-1]
        uit.append(Constituent(
            naam=part,
            realisatie=material,
            alternatieven=_alternatieven(comment),
            bron=bron,
        ))
    return uit


def ontleed_voorwaarden(voorwaarden: list[str] | list[tuple[str, str]], bron: str = "dienstontwerp") -> list[Constituent]:
    """Snede voor een DIENST i.p.v. een product: de belofte valt uiteen in voorwaarden
    (inschrijftoegang, cognitieve aansluiting, erkenning). Accepteert kale namen of
    (naam, realisatie)-paren. Zelfde vorm als ontleed_bom, ander domein — bewijs dat de
    kern niets van 'materiaal' hoeft te weten."""
    uit: list[Constituent] = []
    for v in voorwaarden:
        if isinstance(v, tuple):
            naam, realisatie = v[0], (v[1] if len(v) > 1 else "")
        else:
            naam, realisatie = v, ""
        if naam and naam.strip():
            uit.append(Constituent(naam=naam.strip(), realisatie=realisatie.strip(), bron=bron))
    return uit
