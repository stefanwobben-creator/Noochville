"""Welke skills mag een rol voeren? Eén antwoord, voor iedereen die het vraagt.

DE DERDE INSTANTIE, en dat is precies waar `docs/CONVENTIES.md` zegt de KLASSE te migreren in plaats
van het geval te repareren:

1. **6 sept.** `_weiger` las al de volle set, maar `_plan_checklist` las `dna.skills`. Een gekoppeld
   middel mocht dus draaien en werd nooit aangeboden.
2. **7 sept.** `governance.Reconciler` beslist op DNA ∪ koppelingen of een rol een thread krijgt.
   Dat is een BEWUSTE uitzondering en blijft zo — zie de waarschuwing onderaan.
3. **7 sept.** `skill_match.plan_offers` (het stille skill-aanbod bij een mens-getypt checklist-item)
   las óók alleen het DNA. Gemeten op het echte bord: het item "check savon de potasse suppliers in
   europe" kreeg "no skill · needs a human", terwijl `web_zoek` bestaat, in rugzak `buiten` zit en
   dus voor élke rol beschikbaar is. Het gereedschap lag er; de vraag kwam er alleen nooit bij.

De oorzaak van de herhaling is niet slordigheid maar VORM: het antwoord woonde als methode op
`Inhabitant`, en het cockpit heeft geen Inwoner. Wie het daar nodig had moest het dus overschrijven.
Nu woont het hier, en de Inwoner is gewoon één van de aanroepers.

DE LAGEN, en het DNA is altijd de vloer — geen laag hierboven neemt ooit iets af:

- **DNA** — wat deze rol in zijn governance-record draagt.
- **koppelingen** (achter `skill_links_active`) — een middel dat aan één accountability hangt.
- **rugzakken** (`config/rugzakken.json`) — cirkelbrede capaciteit. Elke rol mag erbij; dát is het
  punt. Een rol onderscheidt zich door zijn DOMEIN, niet door zijn gereedschap.

DIT IS GEEN BEVOEGDHEID. `skill_meta.schrijft_in_domein` blijft absoluut en draait ná deze functie.
Een beslis-skill die per ongeluk in een rugzak zit, wordt door die poort alsnog geweigerd voor elke
rol die het domein niet houdt. Deze functie verruimt alleen de set die de poort daarna beoordeelt.

WAAROM DE SPAWN-BESLISSING HIER NIET LANGS MAG. `governance.Reconciler` bepaalt met de DNA-set of een
rol een draaiende thread krijgt. Zou die de rugzakken meetellen, dan is elke rol in de cirkel
per definitie 'bemand' en komt elke slapende rol weer tot leven — het tegenovergestelde van de
afslanking. Capaciteit is iets anders dan bestaan: een rugzak zegt "dit gereedschap ligt klaar",
nooit "hier hoort iemand te werken".
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.skillset")


def _aan(settings, sleutel: str) -> bool:
    return str((settings or {}).get(sleutel, "0")).strip().lower() in ("1", "true", "yes", "ja")


def effectief(dna_skills, *, rol_id: str = "", context=None) -> set[str]:
    """DNA ∪ koppelingen ∪ rugzakken, als set.

    `dna_skills` is de harde lijst van de rol; `context` levert de twee bovenliggende lagen. Fail-soft
    in elke tak: een context zonder `links` of `rugzakken` (de meeste tests, en elke oudere caller)
    levert exact het DNA op, zodat niets stilletjes van gedrag verandert.
    """
    uit = set(dna_skills or [])
    if context is None:
        return uit

    settings = getattr(context, "settings", None) or {}
    if rol_id and _aan(settings, "skill_links_active"):
        try:
            from nooch_village import skill_links
            uit |= skill_links.linked_skills(getattr(context, "links", None), rol_id)
        except Exception:                                 # noqa: BLE001 — nooit de aanroeper breken
            log.debug("koppelingen overgeslagen voor %s", rol_id, exc_info=True)

    rugzakken = getattr(context, "rugzakken", None)
    if rugzakken:
        try:
            from nooch_village import rugzak
            uit |= rugzak.alle_skills(rugzakken)
        except Exception:                                 # noqa: BLE001
            log.debug("rugzakken overgeslagen voor %s", rol_id, exc_info=True)
    return uit


def van_record(record, *, context=None) -> set[str]:
    """Zelfde antwoord, maar vanaf een governance-Record. Dat is wat het cockpit in handen heeft: het
    heeft geen Inwoner, en juist daarom liep het antwoord daar uit de pas."""
    dna = getattr(record, "definition", None)
    return effectief(list(getattr(dna, "skills", []) or []),
                     rol_id=str(getattr(record, "id", "") or ""), context=context)
