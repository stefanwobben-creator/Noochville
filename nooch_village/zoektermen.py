"""Wat een goede zoekterm is, op één plek.

AANLEIDING (8 september 2026, twee keer op dezelfde dag). Een leveranciers-onderzoek zocht op
"Savon de Potasse fabricant fournisseur Europe savon liquide potassique industriel" — negen
woorden, zes eisen tegelijk — en concludeerde dat er geen Europese leverancier bestaat. Stefan
typte "Savon de Potasse buy" en kreeg een lijst.

De reparatie kwam er, en toen liep hij nog een keer tegen dezelfde muur aan: de logica zat in
`skills_impl/zoekstrategie.py`, terwijl de zoekopdrachten die écht draaien geschreven worden door
`Inhabitant._plan_checklist`. Dat is een ander pad, dat `zoekstrategie` niet eens aanroept. Het
tweede plan stapelde dus vrolijk opnieuw: "kaliumzeep fabrikant Europages Kompass
site:europages.nl OR site:kompass.com" — vrije tekst plus twee site-filters plus een OR, en die
zoekopdracht kwam leeg terug.

Vandaar deze module. De regel woont hier, en beide schrijvers van zoektermen leiden eruit af:

    skills_impl/zoekstrategie  → `_breed_voor_smal` op zijn stappen
    inhabitant._plan_checklist → `verbreed_planitems` op zijn payloads

Reference, don't copy: als de eiswoorden-lijst morgen verandert, verandert hij op één plek.
"""
from __future__ import annotations

import re

#: Een kaal domein ("europages.nl") in een zoekterm is het restant van een `site:`-filter.
_KAAL_DOMEIN = re.compile(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9-]+)+$", re.I)

#: Bronnen/skills die het OPEN web bevragen. Daar geldt de breed-eerst-regel; een corpus-bron
#: (OpenAlex, patentregisters) heeft juist baat bij een precieze technische term.
OPEN_WEB = ("web_zoek", "community_listening", "google_trends")

#: Boven dit aantal woorden is een open-web-term geen zoekopdracht meer maar een specificatie.
BREED_MAX_WOORDEN = 5

#: Woorden die de kern niet dragen maar de query wel versmallen. Bewust kort en handmatig: dit is
#: geen stopwoordenlijst voor taal, het zijn de EISEN die een zoeker eraan plakt.
EISWOORDEN = frozenset({
    "manufacturer", "manufacturers", "supplier", "suppliers", "fabricant", "fabricants",
    "fournisseur", "fournisseurs", "hersteller", "lieferant", "leverancier", "leveranciers",
    "producent", "producer", "producers", "fabrikant", "fabrikanten", "maker", "makers",
    "industrial", "industriel", "industrieel", "wholesale", "bulk", "b2b",
    "company", "companies", "bedrijf", "firma", "contact", "telephone", "telefoon", "phone",
    "europe", "european", "europa", "europese", "eu", "nederland", "dutch", "france",
    "germany", "duitsland", "italy", "spain", "liquide", "liquid", "vloeibaar",
    "lijst", "list", "leden", "members",
})

#: Zoekmachine-operatoren. Eén `site:`-filter is een precisie-instrument; twee ervan met een `OR`
#: ertussen én vrije tekst eromheen is geen zoekopdracht meer. Dat was letterlijk het tweede plan,
#: en het kwam leeg terug — terwijl juist díe stap de registers met telefoonnummers moest opleveren.
OPERATOREN = ("site:", "inurl:", "intitle:", "filetype:", "related:", " OR ", " AND ")


def verbreed(term: str) -> str:
    """De korte versie van een te lange zoekterm: de kern, zonder de eisen eromheen. Leeg = de term
    was al breed genoeg en er valt niets te verbeteren.

    WAAROM DIT DETERMINISTISCH IS EN GEEN PROMPTREGEL. De prompt zegt sinds 8 september "start
    broad", en dat helpt. Maar een promptregel is een belofte: hij houdt zich er meestal aan, en
    precies de keer dat hij dat niet doet mislukt het onderzoek zonder dat iemand het merkt. Dit
    maakt de brede stap een EIGENSCHAP van het plan in plaats van een intentie.

    De aanpak is bewust dom: gooi de eiswoorden en operatoren weg, houd de eerste paar overgebleven
    woorden. Dat is niet slim, maar het is voorspelbaar en het is precies wat een mens doet als hij
    opnieuw begint."""
    schoon = term or ""
    for op in OPERATOREN:
        schoon = schoon.replace(op, " ")
    woorden = [w.strip(",.;:()[]\"'") for w in schoon.split()]
    # Een KAAL DOMEIN is het restant van een weggehaald filter, geen zoekwoord. Zonder deze regel
    # levert "…Kompass site:europages.nl…" de term "kaliumzeep Europages Kompass europages.nl" op:
    # de merknaam staat er dan twee keer, één keer als woord en één keer als domein.
    woorden = [w for w in woorden
               if w and not _KAAL_DOMEIN.match(w)
               and not any(o.strip() in w for o in ("site:", "inurl:", "intitle:", "filetype:"))]
    kern, gezien = [], set()
    for w in woorden:
        laag = w.lower()
        if laag in EISWOORDEN or laag in gezien:
            continue                                     # eis of herhaling: draagt de kern niet
        gezien.add(laag)
        kern.append(w)
    if not kern:
        return ""
    oorspronkelijk = [w for w in (term or "").split() if w]
    if len(kern) == len(oorspronkelijk) and len(oorspronkelijk) <= BREED_MAX_WOORDEN:
        return ""                                        # was al kort en zonder eisen
    kort = " ".join(kern[:BREED_MAX_WOORDEN - 1])
    return kort if kort.lower() != (term or "").strip().lower() else ""


def gestapeld(term: str) -> str:
    """Draagt deze term zoveel operatoren dat geen enkele zoekmachine er iets zinnigs mee doet?
    Geeft de reden terug, of "" als hij in orde is.

    Eén `site:` is prima. Twee `site:`-filters met een `OR` en vrije tekst eromheen is de vorm die
    op 8 september leeg terugkwam op precies de stap die de telefoonnummers moest opleveren."""
    t = f" {term or ''} "
    sites = t.lower().count("site:")
    if sites >= 2:
        return (f"{sites} site:-filters in één zoekopdracht — zoek de registers apart, of laat het "
                f"filter weg en noem de naam gewoon in de term")
    if sites and (" or " in t.lower()):
        return "een site:-filter gecombineerd met OR — splits dit in twee zoekopdrachten"
    return ""


def verbreed_planitems(items: list[dict]) -> list[dict]:
    """Zet vóór het eerste te smalle open-web-item zijn brede variant, in de item-vorm van
    `Inhabitant._plan_checklist` (`{text, skill, payload:{term}, reason}`).

    Hooguit één per plan: twee brede stappen is dubbel werk, en het aantal stappen is begrensd.
    Het smalle item blijft staan — dat was niet fout, het was te vroeg."""
    uit: list[dict] = []
    toegevoegd = False
    for it in items or []:
        payload = it.get("payload") if isinstance(it.get("payload"), dict) else {}
        term = str(payload.get("term") or "")
        if not toegevoegd and it.get("skill") in OPEN_WEB and term:
            breed = verbreed(term)
            if breed:
                nieuw = dict(it)
                nieuw["payload"] = {**payload, "term": breed}
                nieuw["text"] = f"Broad first: {breed}"
                nieuw["reason"] = ("de brede vorm eerst: de woorden die een mens zou typen, "
                                   f"afgeleid uit «{term[:70]}»")
                nieuw["verbreed_van"] = term
                uit.append(nieuw)
                toegevoegd = True
        uit.append(it)
    return uit
