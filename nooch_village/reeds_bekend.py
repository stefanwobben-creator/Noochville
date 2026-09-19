"""Wat weten we hier al van? — vers gevraagd, niets opgeslagen.

VERVANGT `kennis_context.kennis_voor/kennis_blok`, en daarmee de NotesStore-lookup die 530
kaartjes doorzocht die sinds 17 juli niet meer groeiden. Het rendermechanisme haalde al twee
maanden nul kaartjes boven zijn eigen drempel; een lookup die altijd leeg terugkomt is geen
kennislaag maar een ritueel.

WAT DIT WÉL IS. Eén LLM-call op de tekst die de aanroeper meegeeft, in de vorm van
`skills_impl/onderzoeksvraag.py`: side-effect-free, klein tokenbudget, fail-closed. Geen store,
geen index, geen embedding — en dus ook niets dat kan verouderen zonder dat iemand het merkt.

WAT DIT NIET MEER IS, en dat hoort iemand te weten. De oude `kennis_voor` plakte vier bronnen aan
elkaar: de kaartjes (weg), de Kroniek-stand per onderwerp, eerdere projecten, en een
preflight-"weten we dit al". Alleen de eerste was de kennisbank. De Kroniek-sectie verdwijnt dus
mee uit deze prompts — bewust, want de twee aanroepers die haar nog injecteren (`project_worker`
en `inhabitant`, allebei AI-projectuitvoering) gaan in fase 3 zelf weg. Blijft er ooit een
aanroeper over die de Kroniek écht nodig heeft, dan hoort die hem rechtstreeks bij
`evidence_ledger.interpret` te halen: dat is de gezaghebbende bron, niet een doorgeefluik.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.reeds_bekend")

#: Zelfde budget-orde als `onderzoeksvraag`: dit is een korte oriëntatie, geen rapport.
MAX_TOKENS = 500
MAX_BLOK_CHARS = 1200

_PROMPT = """You are briefing someone who is about to start work at Nooch, a vegan, plastic-free
shoe brand. In at most five short bullets, say what is already commonly known about the topic
below, and name anything that is usually assumed but often turns out to be wrong.

Be concrete and sober. No encouragement, no marketing language. If you have nothing solid to say
about the topic, answer exactly: NOTHING.

Topic: {tekst}"""


def blok(bron, tekst: str, **_genegeerd) -> str:
    """Het 'ALREADY KNOWN'-blok voor een prompt, of "" als er niets te zeggen valt.

    `bron` mag een data_dir (str) of een Context-achtig object zijn — de signatuur volgt de oude
    `kennis_voor` zodat de aanroepers niet hoeven te weten dat de bron verdwenen is. Er wordt niets
    uit gelezen; het argument blijft alleen staan om de aanroepers ongemoeid te laten.

    Fail-closed en fail-soft tegelijk: geen model, een leeg antwoord of welke fout dan ook levert
    "" op, en dan wordt er geen sectie geïnjecteerd. Een verzonnen blok zou erger zijn dan geen
    blok — dat is precies waarom de oude laag zweeg als ze niets vond."""
    tekst = " ".join(str(tekst or "").split())[:400]
    if not tekst:
        return ""
    try:
        from nooch_village import llm
        antwoord = llm.reason(_PROMPT.format(tekst=tekst), max_tokens=MAX_TOKENS,
                              call_site="reeds_bekend")
    except Exception as e:                                 # noqa: BLE001 — nooit het werk breken
        log.info("reeds-bekend overgeslagen (%s: %s)", type(e).__name__, e)
        return ""
    antwoord = (antwoord or "").strip()
    if not antwoord or antwoord.upper().startswith("NOTHING"):
        return ""
    return "ALREADY KNOWN (fresh, not stored — verify before you lean on it):\n" \
           + antwoord[:MAX_BLOK_CHARS]


def meld(bus, *, project_id: str = "", rol: str = "", gevonden: bool = False) -> None:
    """Maak zichtbaar DÁT er geraadpleegd is, ook als er niets uitkwam — zelfde reden als bij de
    oude `meld_raadpleging`: nul is ook een uitkomst. Eén logregel, en het bestaande
    `kennis_geraadpleegd`-event als er een bus is. Fail-soft."""
    log.info("📚 %s raadpleegde vers (%s): %s", rol or "?", project_id or "-",
             "iets gevonden" if gevonden else "niets gevonden")
    if bus is None:
        return
    try:
        from nooch_village.event_bus import Event
        bus.publish(Event("kennis_geraadpleegd",
                          {"project_id": project_id, "rol": rol, "vers": True,
                           "gevonden": bool(gevonden)}, rol or "village"))
    except Exception:                                      # noqa: BLE001
        pass
