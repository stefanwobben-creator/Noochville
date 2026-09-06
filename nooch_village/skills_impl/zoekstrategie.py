"""zoekstrategie — bepaal HOE je gaat zoeken, voordat je zoekt.

AANLEIDING (6 september 2026, gemeten op vijf onderzoeksprojecten uit juli). 25 checklist-items, 10
af, 15 vastgelopen. De meldingen: 15x "geen werken gevonden voor deze term", 12x "Not Found", 6x
"Service Unavailable". De projecten staan sindsdien op 2 van de 5 en bereikten dus nooit de review;
er kwam nooit een einddocument, en er landde nooit iets bij een mens.

De term was "vegan schoenen". Het corpus van OpenAlex is Engelstalig. Een onderzoeker had bij nul
treffers de term vertaald of verbreed; het dorp kon dat niet, want er zat geen stap tussen "kies een
bron" en "roep hem aan". Deze skill is die stap.

WAT HIJ OPLEVERT, en waarom in twee vormen tegelijk:

- **proza** dat als deliverable op de projectwall landt, zodat je kunt teruglezen HOE er gezocht is
  en niet alleen wat eruit kwam. Een mislukte zoektocht is dan één regel om te lezen in plaats van
  een reconstructie achteraf.
- **stappen**: per bron een term en een taal. Dat is geen extra: het is precies wat de planner nodig
  heeft om de volgende lijst te schrijven. De strategie en de volgende stappen zijn hetzelfde ding.

WAT HIJ NIET DOET. Hij zoekt niet. Hij raakt geen bron aan, hij kost geen credits, en hij weet niet
of zijn strategie gaat werken. Dat is met opzet: dit is de goedkoopste stap in de keten en hij mag
falen zonder dat er iets verloren gaat. Wat hij oplevert wordt bovendien nog door een mens
goedgekeurd voordat er iets draait.

FAIL-CLOSED. Geen model of een onparseerbaar antwoord geeft een nette fout terug in plaats van een
gegokte strategie. Een verzonnen zoekstrategie is erger dan geen, want hij ziet er net zo uit als
een goede en je merkt het pas aan de lege resultaten drie stappen later.
"""
from __future__ import annotations

import json
import logging
import re

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.zoekstrategie")

# De bronnen die Sid kan raadplegen, met hun taal-eigenaardigheid erbij. Deze lijst staat hier en niet
# in de prompt-tekst zelf, zodat een nieuwe bron één regel is in plaats van een prompt-herschrijving.
BRONNEN: dict[str, str] = {
    "openalex_evidence": "academic literature, ENGLISH-language corpus — a Dutch term finds nothing",
    "epo_patents": "European patent register, English/German/French — use English technical terms",
    "google_patents": "patents worldwide, English",
    "semscholar_tldr": "one-sentence summaries of papers, English",
    "openlibrary_search_inside": "full text of books, mostly English",
    "ngram_culture": "word frequency in books over decades, per language corpus — pick the corpus",
    "community_listening": "what people say on Bluesky/YouTube — the language people actually use",
    "competitor_news": "news about known competitor brands, keyless",
    "haal_pagina": "reads ONE public page you already have the URL of",
    "google_trends": "search volume, per country and language",
}

_MAX_STAPPEN = 6


class ZoekstrategieSkill(Skill):
    name = "zoekstrategie"
    cost = "free"                  # begrensde LLM-call, geen externe bron
    side_effect_free = True        # bepaalt alleen; zoekt niets, schrijft niets
    description = (
        "Bepaalt HOE een onderzoeksvraag onderzocht wordt voordat er gezocht wordt: welke bronnen, "
        "met welke term, in welke taal, en wat te doen bij nul treffers. Levert leesbare uitleg voor "
        "de mens plus de stappen waaruit het volgende uitvoerplan wordt geschreven. Zoekt zelf niets."
    )
    input_schema = ("vraag: str (verplicht — de onderzoeksvraag); "
                    "bekend: str (optioneel — wat we al weten, bv. uit weten_we_dit_al); "
                    "bronnen: list[str] (optioneel — beperk tot deze bronnen)")
    required_payload = ("vraag",)
    output_schema = ("ok, vraag, strategie (proza), stappen[{bron, term, taal, waarom}], "
                     "bij_nul_treffers, text (voor de wall) | error")

    def run(self, payload: dict, context=None) -> dict:
        vraag = ((payload or {}).get("vraag") or "").strip()
        if not vraag:
            return {"error": "ontbrekende parameter: 'vraag' is verplicht"}
        bekend = ((payload or {}).get("bekend") or "").strip()
        keuze = [b for b in ((payload or {}).get("bronnen") or []) if b in BRONNEN] or list(BRONNEN)

        catalogus = "\n".join(f"- {b}: {BRONNEN[b]}" for b in keuze)
        prompt = (
            "You are planning HOW to research a question, before any searching happens.\n\n"
            f"QUESTION: {vraag}\n"
            + (f"\nALREADY KNOWN (do not research again):\n{bekend[:1500]}\n" if bekend else "")
            + f"\nAVAILABLE SOURCES:\n{catalogus}\n\n"
            "Pick 2 to 4 sources. For EACH one give the exact search term you would use and the "
            "language of that term.\n\n"
            "THE RULE THAT MATTERS MOST: match the term to the corpus, not to the question. An "
            "English-language corpus needs an English term even when the question is Dutch. Getting "
            "this wrong returns zero results and reads exactly like 'there is nothing there'.\n\n"
            "Also say, in one sentence, what to do if a source returns nothing: which broader or "
            "different term to try.\n\n"
            "Answer ONLY with JSON, exactly this schema:\n"
            '{"strategie": "<2-4 sentences in plain language: what you are going to do and why>", '
            '"stappen": [{"bron": "<source name from the list>", "term": "<the exact search term>", '
            '"taal": "<en|nl|de|fr>", "waarom": "<one short clause>"}], '
            '"bij_nul_treffers": "<one sentence>"}'
        )
        from nooch_village.llm import reason
        try:
            rauw = reason(prompt, json_mode=True, max_tokens=700, call_site="zoekstrategie",
                          ladder=(payload or {}).get("ladder"))
        except Exception as exc:                              # noqa: BLE001 — nooit de puls breken
            log.warning("zoekstrategie: LLM-fout (%s)", exc)
            return {"error": f"kon geen strategie bepalen: {exc}"}
        data = _json_uit(rauw)
        if not isinstance(data, dict) or not data.get("stappen"):
            return {"error": "geen bruikbare strategie (fail-closed; liever geen dan een gegokte)"}

        stappen = []
        for s in data["stappen"][:_MAX_STAPPEN]:
            if not isinstance(s, dict):
                continue
            bron = str(s.get("bron") or "").strip()
            term = str(s.get("term") or "").strip()
            if bron not in BRONNEN or not term:
                # Een verzonnen bron of een lege term is geen stap; stil overslaan zou de strategie
                # korter maken dan hij lijkt, dus we melden het in het log.
                log.info("zoekstrategie: stap overgeslagen (bron=%r term=%r)", bron, term)
                continue
            stappen.append({"bron": bron, "term": term[:120],
                            "taal": str(s.get("taal") or "en").strip()[:5],
                            "waarom": str(s.get("waarom") or "").strip()[:160]})
        if not stappen:
            return {"error": "strategie noemde geen bruikbare bron uit de catalogus"}

        strategie = str(data.get("strategie") or "").strip()[:900]
        bij_nul = str(data.get("bij_nul_treffers") or "").strip()[:300]
        return {"ok": True, "vraag": vraag, "strategie": strategie, "stappen": stappen,
                "bij_nul_treffers": bij_nul, "text": _als_tekst(strategie, stappen, bij_nul)}


def _json_uit(rauw):
    """JSON uit een modelantwoord, ook met ```-fences eromheen. None bij onparseerbaar."""
    tekst = str(rauw or "").strip()
    if not tekst:
        return None
    tekst = re.sub(r"^```(?:json)?|```$", "", tekst, flags=re.M).strip()
    try:
        return json.loads(tekst)
    except Exception:
        m = re.search(r"\{.*\}", tekst, re.S)
        try:
            return json.loads(m.group()) if m else None
        except Exception:
            return None


def _als_tekst(strategie: str, stappen: list, bij_nul: str) -> str:
    """De vorm die op de projectwall landt. Eén blok dat een mens in tien seconden leest en waaruit
    hij kan zien of de aanpak klopt vóórdat hij op go ahead klikt."""
    regels = [strategie] if strategie else []
    for s in stappen:
        waarom = f" — {s['waarom']}" if s.get("waarom") else ""
        regels.append(f"• {s['bron']}: “{s['term']}” ({s['taal']}){waarom}")
    if bij_nul:
        regels.append(f"Bij nul treffers: {bij_nul}")
    return "\n".join(regels)
