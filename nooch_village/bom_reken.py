"""De rekenlaag van het BOM-scherm: gewicht, kostprijs, CO2e en water per paar (BOM stuk 1).

NIETS HIER IS EEN CIJFER. Het gewicht komt uit de stuklijst (`data_bom`, kolom `Weight (g)`), de
factoren komen van de wiki-pagina's — CO2e en water van de MATERIAALpagina, de prijs van de
LEVERANCIERpagina — als feit met een waarde (`wiki.GROOTHEDEN`). Dit module vermenigvuldigt en telt
op; verandert een factor op een pagina, dan klopt het scherm de volgende keer vanzelf. Reference,
don't copy.

EEN ONVOLLEDIG TOTAAL ZEGT DAT HET ONVOLLEDIG IS. Elk totaal draagt `n` (componenten die meetellen)
naast `m` (alle componenten), en elk gat staat als open punt bij zijn component. Een totaal over 3
van de 23 onderdelen dat zich als "het gewicht van de schoen" presenteert, is precies het soort
stille onwaarheid dat deze laag niet mag maken.

FAIL-CLOSED BIJ TWIJFEL. Twee waarden voor dezelfde grootheid op één pagina telt niet mee: welke
het is, is een besluit van de eigenaar, geen keuze van deze code.
"""
from __future__ import annotations

from nooch_village import wiki
from nooch_village.compositie import bom_rijen
from nooch_village.wiki_seed import _materiaalnaam

# GEEN MAAT-SCHALING MEER (2 oktober 2026, besluit Stefan). Hier stonden `maat_config` en
# `schaalfactor` (3% per maat uit config/bom_maten.json). Eén percentage voor alle onderdelen klopt
# niet: lengte, omtrek en hoogte graderen elk anders, per onderdeel. De gewichten gelden bij
# `data_bom.REFERENTIEMAAT`; maatafhankelijk verbruik komt bij de materiaalplanning, per onderdeel.


#: De vier totalen, in schermvolgorde: (sleutel, grootheid op de pagina of None voor gewicht,
#: waar die grootheid woont).
METRIEKEN = (
    ("gram", None, ""),
    ("prijs", "prijs_per_kg", "supplier"),
    ("co2e", "co2e_per_kg", "material"),
    ("water", "water_per_kg", "material"),
)


def _factor(pagina, grootheid: str) -> tuple[float | None, str]:
    """(getal, reden-als-het-er-niet-is) van één grootheid op één pagina."""
    if pagina is None:
        return None, "no page"
    waarden = [w for w in (wiki.waarde(f) for f in wiki.feiten(pagina))
               if w and w["grootheid"] == grootheid]
    if not waarden:
        return None, "no value on the page"
    if len(waarden) > 1:
        return None, "more than one value on the page"
    return waarden[0]["getal"], ""


def effectieve_rijen(bom_tekst: str, afwijkingen: list[dict] | None = None) -> list[dict]:
    """De stuklijst zoals hij voor DIT model en DEZE variant geldt (BOM Stuk 4).

    `afwijkingen` komt uit `bom_materialen.afwijkingen(model, variant)`: eerst de master-, dan de
    variant-afwijkingen, zodat een variant de master overschrijft. Een afwijking VERVANGT het
    materiaal en/of gewicht van een bestaande rij, of VOEGT een rij toe die in de master niet
    bestaat (`toegevoegd`). Per rij: `origineel` (wat de stuklijst zegt), `niveau` ("" = stuklijst,
    "master" of de variant-handle die hem het laatst veranderde) en `toegevoegd`."""
    from nooch_village.bom_materialen import sleutel as part_sleutel
    rijen, index = [], {}
    for r in bom_rijen(bom_tekst):
        rij = {**r, "origineel": r["material"], "gram_origineel": r["gram"], "niveau": "",
               "toegevoegd": False}
        index[part_sleutel(r["part"])] = rij
        rijen.append(rij)
    for a in afwijkingen or []:
        niveau = a.get("variant") or "master"
        rij = index.get(a["sleutel"])
        if rij is None:
            if not a.get("toegevoegd") or not a.get("materiaal"):
                continue                         # afwijking op een rij die niet (meer) bestaat
            rij = {"part": a.get("part") or a["sleutel"], "material": a["materiaal"],
                   "comment": "", "gram": a.get("gram"), "origineel": "", "gram_origineel": None,
                   "niveau": niveau, "toegevoegd": True}
            index[a["sleutel"]] = rij
            rijen.append(rij)
            continue
        if a.get("materiaal"):
            rij["material"] = a["materiaal"]
        if a.get("gram") is not None:
            rij["gram"] = a["gram"]
        rij["niveau"] = niveau
    return rijen


def bereken(bom_tekst: str, pags: list, leveranciers: dict | None = None,
            materialen: dict | None = None, afwijkingen: list[dict] | None = None) -> dict:
    """{"rijen": [...], "totalen": {sleutel: {"som", "n", "m"}}} voor één stuklijst.

    Per rij: de component, zijn materiaal- en leverancierpagina (of None), het gewicht, de bijdrage
    per metriek (of None) en de open punten in leesbare tekst.

    `leveranciers` = {materiaalsleutel: naam} uit `bom_leveranciers` (per MATERIAAL, niet per rij).
    `afwijkingen` = de regels uit `bom_materialen.afwijkingen(model, variant)` (Stuk 4): per
    component een ander materiaal, een ander gewicht, of een rij die erbij komt; zie
    `effectieve_rijen`. `materialen` = de oudere vorm {partsleutel: materiaal} (alleen materiaal,
    alleen master) — blijft werken. De leverancier volgt altijd het NIEUWE materiaal."""
    leveranciers = leveranciers or {}
    if afwijkingen is None:
        afwijkingen = [{"sleutel": k, "materiaal": v, "variant": ""}
                       for k, v in (materialen or {}).items()]
    rijen = []
    for r in effectieve_rijen(bom_tekst, afwijkingen):
        origineel, _ = _materiaalnaam(r["origineel"])
        materiaal, _onzeker = _materiaalnaam(r["material"])
        gewijzigd = bool(r["niveau"]) and not r["toegevoegd"] and (
            materiaal != origineel or r["gram"] != r["gram_origineel"])
        mat = wiki.resolve(materiaal, pags)
        supplier = leveranciers.get(materiaal.lower(), "")
        lev = wiki.resolve(supplier, pags) if supplier else None
        gram = r["gram"]
        bijdrage: dict[str, float | None] = {"gram": gram}
        open_punten: list[str] = []
        if gram is None:
            open_punten.append("weight not filled in")
        if mat is None:
            open_punten.append(f"no material page for “{materiaal}”")
        if not supplier:
            open_punten.append("no supplier")
        elif lev is None:
            open_punten.append(f"no supplier page for “{supplier}”")
        for sleutel, grootheid, waar in METRIEKEN:
            if grootheid is None:
                continue
            pagina = mat if waar == "material" else lev
            factor, reden = _factor(pagina, grootheid)
            if factor is None:
                bijdrage[sleutel] = None
                if pagina is not None:                    # geen pagina staat er hierboven al
                    open_punten.append(f"{wiki.GROOTHEDEN[grootheid]['label']}: {reden}")
                continue
            bijdrage[sleutel] = gram / 1000 * factor if gram is not None else None
        rijen.append({"part": r["part"], "materiaal": materiaal, "supplier": supplier,
                      "origineel": origineel, "gewijzigd": gewijzigd,
                      "toegevoegd": r["toegevoegd"], "niveau": r["niveau"],
                      "gram_origineel": r["gram_origineel"],
                      "gram_eigen": r["gram"],              # voor het gewicht-formulier
                      "mat": mat, "lev": lev, "bijdrage": bijdrage, "open": open_punten})

    m = len(rijen)
    totalen = {}
    for sleutel, _g, _w in METRIEKEN:
        waarden = [r["bijdrage"][sleutel] for r in rijen if r["bijdrage"].get(sleutel) is not None]
        totalen[sleutel] = {"som": sum(waarden), "n": len(waarden), "m": m}
    return {"rijen": rijen, "totalen": totalen}
