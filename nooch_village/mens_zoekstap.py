"""mens_zoekstap — de zoekopdrachten voor de mens, als item op het plan en als bericht op de wall.

Stefan, 12 september 2026, bij het lijmvrij-verslag (een 4): "als dit niet automatisch kan, is het
ook prima dat je in het project een prompt voorstelt. Bijv. ga naar Google en typ dit in, of vul
deze prompt in in Gemini." Dit is dat voorstel, in code, en het is DETERMINISTISCH: geen extra
modelronde, want de termen zijn er al (de planner schreef ze) en het sjabloon is vast.

WAAROM EEN MENS-STAP OP EEN AI-PLAN. Het dorp zoekt met de termen die het zelf schreef, leest wat
het vindt, en stopt. Een mens kijkt, leest, stuurt bij en zoekt opnieuw; dat is een lus, en die lus
heeft het dorp (nog) niet. Zolang ronde twee niet automatisch is, staat de lus als taak op het bord,
mét de zoekopdrachten erbij, zodat de mens niet zelf hoeft te bedenken wat hij moet typen. Wat hij
vindt hangt hij als links aan het project, en dáár leest de rol de volgende ronde uit.

WAT ER STAAT. Een `human_task`-item (telt niet mee voor done, precies als een fabrieksbezoek) met een
korte tekst, en een bericht op de wall met (1) de Google-queries: de termen van het plan, in alle
drie de woordenschatten als de planner ze schreef, plus de brede vorm; (2) een deep-research-prompt
voor Gemini, Claude of Perplexity met het doel en de opdracht van de mens erin. Beide binnen de caps
van het bord (`check_add` 200 tekens per item, `add_role_message` 1500 per bericht).

WAT ER NIET STAAT: de Nooch-criteria (plasticvrij, vegan) als literal. Die leven in de missie en in
de opdracht die de mens bij het project schreef (`description`); de prompt verwijst daarnaar. Een
tweede kopie van de missie in een sjabloon drijft af van de eerste (reference, don't copy).
"""
from __future__ import annotations

from nooch_village.zoektermen import OPEN_WEB, verbreed

#: Corpus-bronnen: een plan met zo'n item is onderzoek, ook zonder open-web-stap.
CORPUS = ("openalex_evidence", "epo_patents", "google_patents", "semscholar_tldr",
          "openlibrary_search_inside")
#: Alles waarmee het dorp buiten zichzelf zoekt. `competitor_discover` en `claim_evidence` zoeken
#: ook op het web, met een `topic`/`claim` in plaats van een `term`; ze tellen mee als onderzoek
#: maar leveren geen query voor de mens (hun payload is geen zoekterm).
ONDERZOEK = OPEN_WEB + CORPUS + ("competitor_discover", "claim_evidence")

MAX_QUERIES = 6
_MAX_BERICHT = 1500                 # = projects.add_role_message; langer wordt daar afgekapt
_MAX_DOEL = 220

ITEM_TEKST = ("🔎 Human search step: run the Google queries on the wall (and the deep-research "
              "prompt), add the best five URLs as links on this project")
ITEM_REDEN = ("the village searches with the terms it wrote and stops; a person looks, reads, "
              "adjusts and searches again")
MARKER = "🔎 For you, the human"


def _term(item: dict) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    return str(payload.get("term") or item.get("query") or "").strip()


def is_onderzoeksplan(items) -> bool:
    """Staat er minstens één zoekstap met een term op het plan?"""
    return any(it.get("skill") in ONDERZOEK and _term(it) for it in (items or []))


def queries(items) -> list[str]:
    """De Google-queries voor de mens, uit het plan zelf: eerst de open-web-termen (in de volgorde
    van het plan, dus vak, koper, markt als de planner die schreef), dan de brede vorm van de
    eerste, dan de corpus-termen (korte vakfrases zijn goede Google-queries). Ontdubbeld, gecapt."""
    uit: list[str] = []
    gezien: set[str] = set()

    def _voeg(t: str) -> None:
        t = " ".join((t or "").split())
        if t and t.lower() not in gezien and len(uit) < MAX_QUERIES:
            gezien.add(t.lower())
            uit.append(t)

    open_web = [_term(it) for it in (items or []) if it.get("skill") in OPEN_WEB and _term(it)]
    for t in open_web:
        _voeg(t)
    if open_web:
        _voeg(verbreed(open_web[0]))
    for it in (items or []):
        if it.get("skill") in CORPUS:
            _voeg(_term(it))
    return uit


def item_voor_de_mens(items) -> dict | None:
    """Het plan-item, in de vorm van `_plan_checklist` (`text`, `skill`, `payload`, `reason`, `kind`),
    zodat `prepare_project` het als gewone mens-taak wegschrijft. None als dit geen onderzoek is
    of als het item er al staat."""
    if not is_onderzoeksplan(items):
        return None
    # `text` is de vorm van de planner, `tekst` die van de wizard; allebei kunnen al een 🔎 dragen.
    if any(str(it.get("text") or it.get("tekst") or "").startswith("🔎") for it in (items or [])):
        return None
    return {"text": ITEM_TEKST, "skill": None, "payload": {}, "kind": "human_external",
            "reason": ITEM_REDEN}


def bericht_voor_de_mens(goal: str, description: str, zoekopdrachten: list[str]) -> str:
    """Het wall-bericht: de queries en de deep-research-prompt, binnen de bericht-cap."""
    doel = " ".join((goal or "").split())[:_MAX_DOEL]
    opdracht = " ".join((description or "").split())
    regels = [f"{MARKER}: the role searches with the terms below and stops there. A person finds "
              "more by looking, reading and searching again. Two things to do now.",
              "1. Paste these into Google, one per tab, read to page 2:"]
    regels += [f"   • {q}" for q in zoekopdrachten]
    prompt = (f"Research this: {doel}. "
              + (f"The assignment: {opdracht[:300]}. " if opdracht else "")
              + "Search in three vocabularies (trade terms, buyer words, the language of the market "
                "where this is made or sold) and check institutes and brands that already do this. "
                "For EVERY lead: name, URL, what it is in one line, one quoted sentence, and "
                "yes/no/unknown on each criterion of the assignment with the quote that supports it. "
                "List discarded leads with the reason, say what you could not find, and end with "
                "three next actions. Do not invent; 'unknown' is a valid answer.")
    regels.append("2. Paste this into Gemini, Claude or Perplexity (deep research):")
    regels.append(f'   "{prompt}"')
    regels.append("Add the best five URLs as links on this project; the role reads them in the next round.")
    tekst = "\n".join(regels)
    if len(tekst) > _MAX_BERICHT:
        # De opdracht van de mens is het enige rekbare deel; de queries en de instructie blijven.
        kort = bericht_voor_de_mens(goal, "", zoekopdrachten) if opdracht else tekst[:_MAX_BERICHT]
        return kort[:_MAX_BERICHT]
    return tekst
