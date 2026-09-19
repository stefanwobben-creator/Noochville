"""De pagina "Claims policy" — wanneer een duurzaamheidsclaim live mag.

ZELFDE VORM ALS `wiki_how_we_decide`, EN OM DEZELFDE REDEN. De tekst is inhoud en geen code: hij
leeft in `content/claims_policy_en.md` en wordt door een mens onderhouden. Stond hij hier als
string, dan vroeg elke zin-wijziging een code-deploy — en dan schrijft de implementatie het beleid.

GEEN NIEUW ZAAI-MECHANISME. `wiki_seed.zaai` doet dit al: idempotent (dezelfde titel bij dezelfde
eigenaar wordt overgeslagen, nooit overschreven), fail-closed op een ontbrekende of gearchiveerde
eigenaar-rol, en dry-run tenzij `apply=True`.

WAAROM DE EIGENAAR HIER EEN ROL-ID IS EN GEEN DOMEIN-AFLEIDING. De claim-PAGINA'S in `cli.py`
leiden hun eigenaar af uit governance (`org.role_for_domain(..., claims_db.DOMEIN)`), en dat levert
sinds 18 september 2026 niets op: het domein `claims-database` heeft geen levende eigenaar meer, dus
die pagina's worden overgeslagen. Voor het BELEID is dat geen werkbare route — een beleidspagina die
pas verschijnt als er ooit weer een domein-grant is, verschijnt nooit. Stefan heeft de rol daarom op
20 september 2026 expliciet aangewezen. Een inclusie IS een besluit; een besluit dat je uit een
regel afleidt is geen besluit meer (zelfde redenering als `_COPY_STACK_ZAAD` in `cockpit2`).

WAT DIT NIET VERANDERT. `cockpit2._claims_gate` — wie de claims-database mag CUREREN — staat hier
volledig los van en blijft iedereen-ingelogd, zoals fase 5 besloot. Deze module raakt alleen de
schrijfpoort op de PAGINA (`_artefact_gate`: rolvervuller of Circle Lead). Wie de pagina niet mag
bewerken kan hem wél laten wijzigen via `pagina_voorstel` — dat is ongated en legt het voorstel bij
de eigenaar-rol neer. Zie `tests/test_wiki_claims_policy.py`, waar beide grenzen vastliggen.
"""
from __future__ import annotations

import os

TITEL = "Claims policy"
BRONBESTAND = os.path.join("content", "claims_policy_en.md")

#: De rol die de pagina bezit en bijhoudt. Aangewezen door Stefan, niet afgeleid — zie de kop.
EIGENAAR = "mother_earth__nooch__compliance"


class TekstOntbreekt(FileNotFoundError):
    """Zonder bronbestand geen pagina — we verzinnen het beleid niet."""


def tekst(base_dir: str) -> str:
    pad = os.path.join(base_dir, BRONBESTAND)
    try:
        with open(pad, encoding="utf-8") as fh:
            return fh.read()
    except OSError as e:
        raise TekstOntbreekt(f"{pad} ontbreekt — de pagina wordt niet aangemaakt") from e


def pagina(base_dir: str) -> dict:
    """De pagina in de vorm die `wiki_seed.zaai` verwacht: titel, body, feiten.

    Geen feiten. Dit is een regel over wat gepubliceerd mag worden, geen bewering over de wereld —
    de laatste alinea van de tekst zegt dat zelf. Een `meta["feiten"]`-lijst zou de grond-status op
    het scherm over het BELEID laten gaan in plaats van over een claim, en precies die verwisseling
    is wat het beleid verbiedt."""
    return {"titel": TITEL, "body": tekst(base_dir), "feiten": []}


def zorg_voor_pagina(store, records, base_dir: str, *, apply: bool = True,
                     eigenaar: str = EIGENAAR, actor_id: str = "system") -> list[dict]:
    """Zet de pagina bij de eigenaar-rol. Idempotent; geeft het rapport van `wiki_seed.zaai`."""
    from nooch_village import wiki_seed
    return wiki_seed.zaai(store, records, paginas=[pagina(base_dir)], eigenaar=eigenaar,
                          soort="beleid", apply=apply, actor_id=actor_id)
