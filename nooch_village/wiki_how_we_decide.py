"""De pagina "How we decide here" — de methode, met de echte besluiten eronder.

WAAROM DIT EEN EIGEN MODULE IS EN GEEN LITERAL. De tekst is inhoud en geen code: hij leeft in
`content/how_we_decide_en.md` en wordt door een mens onderhouden, net als het coach-sjabloon in
`prompts/`. Stond hij hier als string, dan vroeg elke zin-wijziging een code-deploy — en dan
schrijft de implementatie de methode.

GEEN NIEUW ZAAI-MECHANISME. `wiki_seed.zaai` doet dit al: idempotent (een pagina met dezelfde titel
bij dezelfde eigenaar wordt overgeslagen, nooit overschreven), fail-closed op een ontbrekende of
gearchiveerde eigenaar-rol, en dry-run tenzij `apply=True`. Wat hier overblijft is: welke tekst,
bij welke rol.

De besluiten-lijst staat NIET in deze tekst. `views/wiki._besluiten_sectie` leidt hem bij het lezen
af uit `data/decision_sheets.jsonl`, zodat de pagina nooit een kopie van een besluit bewaart.
"""
from __future__ import annotations

import os

TITEL = "How we decide here"
BRONBESTAND = os.path.join("content", "how_we_decide_en.md")

#: De rol die de pagina bezit en bijhoudt. Het besluit-domein ligt daar, dus de methode ook.
EIGENAAR = "mother_earth__nooch__strategic_lead_founder_steward"


class TekstOntbreekt(FileNotFoundError):
    """Zonder bronbestand geen pagina — we verzinnen de methode niet."""


def tekst(base_dir: str) -> str:
    pad = os.path.join(base_dir, BRONBESTAND)
    try:
        with open(pad, encoding="utf-8") as fh:
            return fh.read()
    except OSError as e:
        raise TekstOntbreekt(f"{pad} ontbreekt — de pagina wordt niet aangemaakt") from e


def pagina(base_dir: str) -> dict:
    """De pagina in de vorm die `wiki_seed.zaai` verwacht: titel, body, feiten.

    Geen feiten: dit is een werkwijze, geen bewering over de wereld. Een `meta["feiten"]`-lijst zou
    suggereren dat hier iets te gronden valt, en de grond-status op het scherm zou dan over de
    methode gaan in plaats van over een claim."""
    return {"titel": TITEL, "body": tekst(base_dir), "feiten": []}


def zorg_voor_pagina(store, records, base_dir: str, *, apply: bool = True,
                     eigenaar: str = EIGENAAR, actor_id: str = "system") -> list[dict]:
    """Zet de pagina bij de eigenaar-rol. Idempotent; geeft het rapport van `wiki_seed.zaai`."""
    from nooch_village import wiki_seed
    return wiki_seed.zaai(store, records, paginas=[pagina(base_dir)], eigenaar=eigenaar,
                          soort="methode", apply=apply, actor_id=actor_id)
