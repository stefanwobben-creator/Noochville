"""De kop boven een opgeleverd resultaat: wie het deed, waar het bij hoort, en wat eruit kwam.

AANLEIDING (6 september 2026, eerste echte gebruik na de akkoord-poort). De wall-note zag er zo uit:

    📎 Zoek nieuws over concurrenten — via competitor_news: 3 resultaten
    • title: 11 Best Vegan Shoes | link: … | published: 2026-05-26
    • title: How Ethical Is Nike? | link: … | published: 2026-03-25

Alles klopt en er staat niets. Je ziet niet WAT het antwoord is (daarvoor moet je drie bulletjes
lezen en zelf concluderen), niet of het IETS WAARD is, en sinds een project meerdere checklists kan
hebben ook niet meer BIJ WELKE LIJST het hoorde.

Drie toevoegingen, en alle drie zijn goedkoop:

1. **Herkomst** — de lijstnaam en de stagiair, uit gegevens die er al zijn. De stagiair komt uit
   `config/rugzakken.json`: daar staat per rugzak al wie hem draagt. Geen tweede tabel die uit de
   pas kan lopen met de eerste (`reference, don't copy`).

2. **Conclusie** — één zin: wat is het antwoord. Dit is het enige stukje waar een model aan te pas
   komt, op de goedkope trede, met een harde eis: alleen wat er in het resultaat staat.

3. **Oordeel** — bruikbaar / mager / niets. Deterministisch geteld, niet gevraagd. Een model dat
   zijn eigen output beoordeelt kijkt zijn eigen huiswerk na, en "hoeveel records zitten hier in"
   is te tellen. Gemeten slaat altijd gevraagd.

FAIL-SOFT IN BEIDE RICHTINGEN. Geen LLM, geen krediet, een exceptie: dan valt de conclusie weg en
blijft de rest staan. De ruwe velden onder de kop veranderen nooit — die zijn het bewijs, en de kop
is de leeswijzer. Een leeswijzer mag ontbreken, bewijs niet.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.deliverable_kop")

# Boven deze aantallen heet een resultaat "bruikbaar". Bewust laag: bij onderzoek is één goede
# treffer vaker raak dan tien matige, en het oordeel moet de mens helpen kiezen wat hij leest,
# niet doen alsof het een kwaliteitscijfer is.
_MAGER_TOT = 2


def stagiair_voor(rugzakken, skill: str) -> str:
    """Welke stagiair draagt dit middel? Leeg als hij in geen rugzak zit (dan noemen we niemand).

    Bron is `config/rugzakken.json`, want daar staat de indeling al. Zo volgt de stem het werk
    zonder een eigen tabel die kan afdrijven van de rugzakken."""
    if not rugzakken or not skill:
        return ""
    for blok in rugzakken.values():
        if skill in ((blok or {}).get("skills") or ()):
            return str((blok or {}).get("stagiair") or "")
    return ""


def tel_resultaten(result: dict, archetype) -> int | None:
    """Hoeveel records leverde dit op? None = niet te tellen (dan geen oordeel).

    Alleen tellen wat de archetype-detectie al heeft aangewezen; zelf gaan zoeken naar 'iets wat op
    een lijst lijkt' maakt van een leeswijzer een tweede waarheid."""
    if not isinstance(result, dict) or not archetype:
        return None
    kind, key = archetype
    waarde = result.get(key)
    if kind == "list" and isinstance(waarde, list):
        return int(result.get("total") or len(waarde))
    if kind == "dictlist" and isinstance(waarde, dict):
        return len(waarde)
    if kind == "text":
        return 1 if str(waarde or "").strip() else 0
    return None


def oordeel(aantal: int | None) -> str:
    """Bruikbaar / mager / niets, of leeg als er niets te tellen viel. Deterministisch."""
    if aantal is None:
        return ""
    if aantal <= 0:
        return "nothing"
    return "thin" if aantal <= _MAGER_TOT else "usable"


def conclusie(vraag: str, samenvatting: str, *, reason_fn=None, ladder=None) -> str:
    """Eén zin: wat is het antwoord op dit checklist-item? Leeg bij twijfel of zonder model.

    `samenvatting` is de al gerenderde ruwe note — dus precies wat de mens eronder ziet staan. Het
    model krijgt niets extra's; het mag alleen samenvatten wat er al is. Dat is de goedkoopste
    manier om te voorkomen dat er een feit bij komt dat nergens in het bewijs staat.
    """
    vraag = (vraag or "").strip()
    samenvatting = (samenvatting or "").strip()
    if not samenvatting:
        return ""
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn        # noqa: PLC0415 — lazy, testbaar
    prompt = (
        "Below is the raw result of one checklist item. Write ONE sentence that states the answer: "
        "what does this result actually say about the item?\n\n"
        "HARD RULE: use only what is literally in the result. Add no numbers, names, dates or "
        "conclusions that are not there. Found nothing? Then say that plainly.\n"
        "Do not repeat the item text and do not open with 'The result shows'. Max 25 words.\n\n"
        f"ITEM: {vraag[:300]}\n\nRESULT:\n{samenvatting[:2000]}\n\n"
        "OUTPUT: the sentence only, no quotes, no preamble."
    )
    try:
        uit = reason_fn(prompt, max_tokens=80, call_site="deliverable_conclusie", ladder=ladder)
    except Exception as exc:                                     # noqa: BLE001 — nooit het pad breken
        log.info("conclusie overgeslagen (%s)", exc)
        return ""
    zin = " ".join(str(uit or "").split()).strip().strip('"').strip()
    # Een model dat de instructie negeert en een alinea teruggeeft is geen conclusie meer; dan liever
    # niets, want de ruwe velden staan er toch onder.
    return zin[:240] if 0 < len(zin) <= 400 else ""


def kop(*, item_tekst: str, skill_label: str, lijst: str = "", stagiair: str = "",
        aantal: int | None = None) -> str:
    """De eerste regel: wat, via welk middel, door wie, op welke lijst, met welk oordeel."""
    delen = [f"📎 {item_tekst} — via {skill_label}"]
    if stagiair:
        delen.append(stagiair)
    if lijst:
        delen.append(f"list “{lijst}”")
    oor = oordeel(aantal)
    if oor:
        delen.append(f"{oor} ({aantal})" if aantal is not None else oor)
    return " · ".join(delen)
