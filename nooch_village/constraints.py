"""Huis-regels — wat de mens één keer heeft geoordeeld, en wat het dorp daarna niet meer vergeet.

Ontstaan uit triage: als de mens een kans afwijst met een reden ("bio-afbreekbaar is een
producteis", "we bieden geen kinderschoenen"), dan wordt die reden een vaste regel. De
opportunity-reflex leest ze en stelt niets meer voor dat ertegen botst.

DEZE MODULE WAS DOOD, EN DAT WAS HET GAT. `Inhabitant._house_constraints()` leest
`data/constraints.json` bij ELKE reflectie en zet de inhoud in de prompt als "VASTE HUIS-REGELS
(respecteer ALTIJD)". De leeskant draaide dus gewoon; de schrijfkant (`add`) zat alleen in
`inbox_actions.decide_opportunity`, en die functie heeft geen enkele productie-aanroeper. Netto
vroeg het dorp elke week om het oordeel van de mens en kreeg gegarandeerd niets terug. Dat is de
reden dat de kans-reflex in juli 195 varianten van dezelfde voorstellen produceerde: hij kón niet
leren, en op 16 juli is de kraan daarom dichtgedraaid in plaats van het scharnier gerepareerd.

HET DOMEIN IS OP 8 SEPTEMBER TOEGEVOEGD, want dezelfde vorm bleek elders óók te ontbreken. Een
zoekstrategie die niets vond schreef in haar eigen eindrapport op wat ze anders had moeten doen
("verbreed voorbij het Frans", "gebruik B2B-registers in plaats van algemeen webzoeken") en niets
las dat ooit terug. Dat is precies dezelfde lus met een andere inhoud, dus dezelfde store met een
ander domein — geen tweede mechanisme naast dit ene (reference, don't copy).

  domein "kansen"  → gelezen door `Inhabitant._house_constraints` bij elke reflectie
  domein "zoeken"  → gelezen door `skills_impl/zoekstrategie` vóór elke zoekstrategie

Regels zonder `domein` (alles van vóór 8 september) tellen als "kansen". Zo hoeft er niets
gemigreerd te worden en blijft de bestaande lezer kloppen.

ONDER HET SLOT sinds hij levend is: het cockpit schrijft (een mens die oordeelt) en de daemon leest
(de reflex). Twee processen op één bestand is precies waar `JsonStore` voor bestaat.
"""
from __future__ import annotations

import time

from nooch_village.util import JsonStore

#: De domeinen die een lezer heeft. Een regel zonder domein is historisch en telt als "kansen".
KANSEN = "kansen"
ZOEKEN = "zoeken"
DOMEINEN = (KANSEN, ZOEKEN)


class Constraints(JsonStore):
    """Huis-regels per domein. `data/constraints.json`, een lijst van dicts."""

    _STATE = "_items"
    _default = list
    _EXPECT = list
    _WRITE_METHODS = ("add", "remove")

    def add(self, text: str, *, by: str = "human", source: str = "",
            domein: str = KANSEN) -> bool:
        """Voeg een huis-regel toe. Dedup op tekst binnen hetzelfde domein. True = nieuw.

        Dedup is per DOMEIN en niet globaal: "verbreed eerst voor je versmalt" kan een zinnige
        zoekles zijn én een zinnige kansregel, en dan zijn het twee regels voor twee lezers."""
        text = (text or "").strip()
        if not text:
            return False
        domein = (domein or KANSEN).strip() or KANSEN
        if any(c.get("text", "").lower() == text.lower() and _domein_van(c) == domein
               for c in self._items):
            return False
        self._items.append({"text": text, "by": by, "source": source, "domein": domein,
                            "date": time.strftime("%Y-%m-%d")})
        self._save()
        return True

    def remove(self, text: str, *, domein: str | None = None) -> bool:
        """Haal een regel weg. Een oordeel dat niet meer klopt moet ingetrokken kunnen worden,
        anders wordt de leerlus een gevangenis: de reflex blijft zich houden aan een regel die de
        mens allang heeft losgelaten."""
        text = (text or "").strip().lower()
        if not text:
            return False
        voor = len(self._items)
        self._items = [c for c in self._items
                       if not (c.get("text", "").lower() == text
                               and (domein is None or _domein_van(c) == domein))]
        if len(self._items) == voor:
            return False
        self._save()
        return True

    def all(self, domein: str | None = None) -> list[dict]:
        if domein is None:
            return list(self._items)
        return [c for c in self._items if _domein_van(c) == domein]

    def texts(self, domein: str | None = None) -> list[str]:
        return [c["text"] for c in self.all(domein) if c.get("text")]


def _domein_van(regel: dict) -> str:
    """Het domein van een regel. Ontbreekt het veld, dan is de regel van vóór 8 september en hoort
    hij bij de kansen — dat was toen het enige domein dat bestond."""
    return (regel.get("domein") or KANSEN).strip() or KANSEN
