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


#: De kolommen die een BOM op KOPNAAM kan dragen (kleine letters). `part` en `material` zijn
#: verplicht; de rest is optioneel. Eén plek, zodat de parser en het BOM-scherm dezelfde namen lezen.
KOLOMMEN = {"part": "part", "material": "material", "comment": "comment",
            "weight (g)": "gram"}


def _kolommen(tekst: str) -> dict[str, int] | None:
    """{veld: kolomindex} uit de tab-gescheiden koprij, of None als er geen bruikbare kop is.

    WAAROM OP KOPNAAM (1 oktober 2026). De positionele lezing hieronder neemt Part en Material als de
    laatste twee niet-lege cellen vóór het commentaar. Dat werkte zolang Comment de laatste kolom
    was; met `Weight (g)` en `Supplier` erachter zou een ingevuld gewicht als materiaal gelezen
    worden. Lege cellen tellen hier wél mee, zodat een rij en zijn kop op dezelfde index staan."""
    for regel in tekst.splitlines():
        if "\t" not in regel:
            continue
        cellen = [c.strip().lower() for c in regel.split("\t")]
        if "part" in cellen and "material" in cellen:
            return {KOLOMMEN[c]: i for i, c in enumerate(cellen) if c in KOLOMMEN}
    return None


def bom_rijen(tekst: str) -> list[dict]:
    """Elke componentrij als dict: part, material, comment, gram (float of None). De leverancier zit
    niet in de stuklijst maar in `bom_leveranciers` (per materiaal, bewerkbaar).

    Alleen voor een tab-BOM mét koprij (zonder kop: lege lijst — het BOM-scherm heeft de kolommen
    nodig). Een gewicht dat geen getal ≥ 0 is wordt None, niet 0: een onleesbaar vak is "nog open",
    geen nul gram."""
    kol = _kolommen(tekst)
    if not kol:
        return []
    uit = []
    kop_gezien = False
    for regel in tekst.splitlines():
        cellen = [c.strip() for c in regel.split("\t")]
        if not kop_gezien:
            kop_gezien = {c.lower() for c in cellen} >= {"part", "material"}
            continue

        def cel(veld: str) -> str:
            i = kol.get(veld)
            return cellen[i] if i is not None and i < len(cellen) else ""

        part, material = cel("part"), cel("material")
        if not part or not material:
            continue
        try:
            gram = float(cel("gram").replace(",", ".")) if cel("gram") else None
        except ValueError:
            gram = None
        if gram is not None and (gram != gram or gram < 0):
            gram = None
        uit.append({"part": part, "material": material, "comment": cel("comment"), "gram": gram})
    return uit


def ontleed_bom(tekst: str, bron: str = "BOM") -> list[Constituent]:
    """Parse een (tab- of dubbelspatie-gescheiden) Bill of Materials naar constituenten.

    Tolerant voor een leidende status/legenda-kolom: per rij worden de cellen ontdaan van
    lege waarden, het commentaar (vanaf '<') afgesplitst, en Part + Material als de laatste
    twee kop-cellen genomen. Zo werkt zowel 'Done<tab><tab>Outsole<tab>Pliant' als
    '<tab><tab>Eyestay<tab>HyphaLite'. De koprij (Part/Material) wordt overgeslagen.

    Heeft de BOM een tab-koprij, dan wordt op KOPNAAM gelezen (`bom_rijen`) — zie `_kolommen`."""
    if _kolommen(tekst):
        return [Constituent(naam=r["part"], realisatie=r["material"],
                            alternatieven=_alternatieven(r["comment"]), bron=bron,
                            opmerking=r["comment"].strip().lstrip("<").strip())
                for r in bom_rijen(tekst)]
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
            opmerking=comment.strip().lstrip("<").strip(),
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
