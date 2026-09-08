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
    "openalex_evidence": "academic literature, ENGLISH-language corpus — use an English term",
    "epo_patents": "European patent register, English/German/French — use English technical terms",
    "google_patents": "patents worldwide, English",
    "semscholar_tldr": "one-sentence summaries of papers, English",
    "openlibrary_search_inside": "full text of books, mostly English",
    "ngram_culture": "word frequency in books over decades, per language corpus — pick the corpus",
    "community_listening": "what people say on Bluesky/YouTube — the language people actually use",
    "competitor_news": "news about known competitor brands, keyless",
    "web_zoek": "the open web: searches a term and reads the top pages, any language",
    "haal_pagina": "reads ONE public page you already have the URL of",
    "google_trends": "search volume, per country and language",
}

_MAX_STAPPEN = 6

#: Bronnen die het OPEN web bevragen. Daar geldt de breed-eerst-regel; een corpus-bron (OpenAlex,
#: patenten) heeft juist baat bij een precieze technische term.
_OPEN_WEB = ("web_zoek", "community_listening", "google_trends")

#: Boven dit aantal woorden is een open-web-term geen zoekopdracht meer maar een specificatie.
#: Gemeten aan het geval dat dit veroorzaakte: "Savon de Potasse fabricant fournisseur Europe savon
#: liquide potassique industriel" is negen woorden en zes eisen tegelijk, en levert de pagina's die
#: op de FORMULERING matchen in plaats van op de behoefte.
_BREED_MAX_WOORDEN = 5

#: Woorden die de kern niet dragen maar de query wel versmallen. Bewust kort en handmatig: dit is
#: geen stopwoordenlijst voor taal, het zijn de EISEN die een zoeker eraan plakt.
_EISWOORDEN = frozenset({
    "manufacturer", "manufacturers", "supplier", "suppliers", "fabricant", "fabricants",
    "fournisseur", "fournisseurs", "hersteller", "lieferant", "leverancier", "leveranciers",
    "producent", "producer", "producers", "industrial", "industriel", "industrieel",
    "wholesale", "bulk", "b2b", "company", "companies", "bedrijf", "firma",
    "europe", "european", "europa", "europese", "eu", "nederland", "dutch", "france",
    "germany", "duitsland", "italy", "spain", "liquide", "liquid", "vloeibaar",
})


def _lessen(context) -> list[str]:
    """De zoeklessen die de mens eerder heeft vastgelegd. Read-only, fail-soft → [].

    Dit is de LEESKANT van de leerlus, en hij ontbrak. Op 8 september bleek een leveranciers-
    onderzoek in zijn eigen eindrapport op te schrijven wat het anders had moeten doen ("verbreed
    voorbij het Frans", "gebruik B2B-registers in plaats van algemeen webzoeken") — correcte
    diagnose, in een document dat niets terugleest. De volgende zoektocht begon weer bij nul.

    De store is dezelfde als die van de huis-regels bij de kansen, met een ander domein; zie
    `constraints.py` voor waarom dat één mechanisme is en geen twee."""
    dd = getattr(context, "data_dir", None)
    if not dd:
        return []
    import os
    pad = os.path.join(dd, "constraints.json")
    if not os.path.exists(pad):
        return []
    try:
        from nooch_village.constraints import ZOEKEN, Constraints
        return Constraints(pad).texts(ZOEKEN)
    except Exception as exc:                             # noqa: BLE001 — nooit de strategie breken
        log.warning("zoeklessen niet leesbaar (%s)", exc)
        return []


def _breed_voor_smal(stappen: list[dict]) -> list[dict]:
    """Zet vóór elke te smalle open-web-stap zijn brede variant. Hooguit één per strategie, want
    twee brede stappen is dubbel werk en de cap op `_MAX_STAPPEN` is er niet voor niets."""
    uit: list[dict] = []
    toegevoegd = False
    for stap in stappen:
        if not toegevoegd and stap.get("bron") in _OPEN_WEB:
            breed = verbreed(stap.get("term", ""))
            if breed:
                uit.append({"bron": stap["bron"], "term": breed, "taal": stap.get("taal", "en"),
                            "waarom": "de brede vorm eerst: de woorden die een mens zou typen",
                            "verbreed_van": stap["term"]})
                toegevoegd = True
        uit.append(stap)
    return uit[:_MAX_STAPPEN]


def verbreed(term: str) -> str:
    """De korte versie van een te lange zoekterm: de kern, zonder de eisen eromheen.

    WAAROM DIT DETERMINISTISCH IS EN GEEN PROMPTREGEL. De prompt zegt sinds 8 september "start
    broad", en dat helpt. Maar een promptregel is een belofte: hij houdt zich er meestal aan en
    precies de keer dat hij dat niet doet, mislukt het onderzoek zonder dat iemand het merkt. Deze
    functie maakt de brede stap een EIGENSCHAP van de strategie in plaats van een intentie.

    De aanpak is bewust dom: gooi de eiswoorden weg, houd de eerste paar overgebleven woorden. Dat
    is niet slim, maar het is voorspelbaar en het is precies wat een mens doet als hij opnieuw
    begint. Geeft een lege of ongewijzigde kern terug, dan was de term al breed en gebeurt er
    niets."""
    woorden = [w.strip(",.;:()[]\"'") for w in (term or "").split()]
    woorden = [w for w in woorden if w]
    kern, gezien = [], set()
    for w in woorden:
        laag = w.lower()
        if laag in _EISWOORDEN or laag in gezien:
            continue                                     # eis of herhaling: draagt de kern niet
        gezien.add(laag)
        kern.append(w)
    if not kern:
        return ""
    if len(kern) == len(woorden) and len(woorden) <= _BREED_MAX_WOORDEN:
        return ""                                        # was al kort en zonder eisen
    kort = " ".join(kern[:_BREED_MAX_WOORDEN - 1])
    return kort if kort.lower() != (term or "").strip().lower() else ""


# Een reden is een EIGENSCHAP van de bron ("English-language corpus"), geen uitsluiting ("not the
# Dutch term"). Zie `_bevestigend` voor waarom dat verschil de moeite van een vangrail waard is.
_ONTKENNING = re.compile(
    r"\b(not|no|never|nor|isn't|doesn't|don't|won't|avoid|rather than|instead of|"
    r"niet|geen|nooit|vermijd|in plaats van)\b", re.I)


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
        lessen = _lessen(context)
        lessen_txt = ""
        if lessen:
            lessen_txt = ("\nLESSONS FROM EARLIER SEARCHES (the human recorded these; respect "
                          "them):\n" + "\n".join(f"- {l}" for l in lessen[:10]) + "\n")
        prompt = (
            "You are planning HOW to research a question, before any searching happens.\n\n"
            f"QUESTION: {vraag}\n"
            + (f"\nALREADY KNOWN (do not research again):\n{bekend[:1500]}\n" if bekend else "")
            + lessen_txt
            + f"\nAVAILABLE SOURCES:\n{catalogus}\n\n"
            "Pick 2 to 4 sources. For EACH one give the exact search term you would use and the "
            "language of that term.\n\n"
            "THE RULE THAT MATTERS MOST: match the term to the corpus. An English-language corpus "
            "takes an English term even when the question is Dutch.\n\n"
            "THE SECOND RULE: START BROAD. For open-web sources your FIRST term is SHORT — two to "
            "four words, the words a person would actually type. Stacking every requirement into "
            "one query ('X manufacturer supplier Europe industrial liquid') returns the pages that "
            "match the phrasing, not the pages that match the need. Narrow on the NEXT step, once "
            "you have seen what comes back.\n\n"
            "WHEN YOU ARE LOOKING FOR COMPANIES (suppliers, manufacturers, distributors), general "
            "web search and guide articles are the wrong instrument: they surface articles about "
            "the thing, not the firms that make it. Reach for trade registers and B2B directories "
            "by name in the term (Kompass, Europages, national trade associations), and for the "
            "plain buying phrase a customer would use.\n\n"
            "WRITE THE PLAN AS WHAT YOU WILL DO. Every sentence names a move you are making. State "
            "a reason as a property of the source you are using — \"English-language corpus\", "
            "\"European register\", \"the words people use themselves\" — never as what you are "
            "leaving out or avoiding. The reader wants your approach, not your exclusions.\n\n"
            "Also give the term you will reach for next if the first one comes back thin: one "
            "sentence, one concrete broader or adjacent term.\n\n"
            "Answer ONLY with JSON, exactly this schema:\n"
            '{"strategie": "<2-4 sentences in plain language: what you are going to do and why>", '
            '"stappen": [{"bron": "<source name from the list>", "term": "<the exact search term>", '
            '"taal": "<en|nl|de|fr>", "waarom": "<one short affirmative clause>"}], '
            '"bij_nul_treffers": "<one sentence naming the next term>"}'
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
                            "waarom": _bevestigend(str(s.get("waarom") or "").strip()[:160])})
        if not stappen:
            return {"error": "strategie noemde geen bruikbare bron uit de catalogus"}

        # DE BREDE STAP WORDT ERVOOR GEZET, NIET GEVRAAGD. Is de eerste open-web-term een
        # specificatie in plaats van een zoekopdracht, dan komt de korte versie ervóór te staan. De
        # smalle stap blijft: die is niet fout, hij was alleen te vroeg. Zo loopt de strategie van
        # breed naar smal, ook als het model de promptregel deze keer negeerde.
        stappen = _breed_voor_smal(stappen)

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


def _bevestigend(waarom: str) -> str:
    """Een reden die een ONTKENNING is, verdwijnt. Leeg is beter dan negatief.

    Waarom deze vangrail bestaat: het model kreeg de taalval als NEGATIEF voorbeeld aangeleerd en gaf
    hem zo ook terug — "niet 'vegan schoenen', het corpus is Engelstalig". Dat leest als een
    verantwoording tegenover een criticus in plaats van als een plan. Wat de lezer wil weten is wat
    Sid gaat doen; wat hij niet doet is oneindig lang en nergens interessant.

    Weggooien en niet herschrijven: herschrijven kost een tweede modelronde en levert een zin op die
    Sid niet gezegd heeft. De reden is bovendien versiering — de bron en de term dragen het werk. Een
    stap zonder reden is nog steeds een volledige stap; een stap met een negatieve reden niet.

    Grof met opzet: één ontkennend woord is genoeg om de hele clausule te laten vallen. Dat kost af
    en toe een terechte reden waarin toevallig "no" staat, en dat is de goedkoopste kant van de fout.
    De prompt vraagt nu bevestigend, dus normaal komt deze vangrail niet in actie.
    """
    if not waarom or _ONTKENNING.search(waarom):
        if waarom:
            log.info("zoekstrategie: ontkennende reden weggelaten (%r)", waarom[:80])
        return ""
    return waarom


def _als_tekst(strategie: str, stappen: list, bij_nul: str) -> str:
    """De vorm die op de projectwall landt. Eén blok dat een mens in tien seconden leest en waaruit
    hij kan zien of de aanpak klopt vóórdat hij op go ahead klikt.

    Elke regel is een handeling: dit ga ik doen, hier, met deze term. Ook de laatste — die noemt de
    volgende term, niet het uitblijven van resultaat. Engels, zoals de hele inhoudslaag sinds
    06-09-2026."""
    regels = [strategie] if strategie else []
    for s in stappen:
        waarom = f" — {s['waarom']}" if s.get("waarom") else ""
        regels.append(f"• {s['bron']}: “{s['term']}” ({s['taal']}){waarom}")
    if bij_nul:
        regels.append(f"Next term if the first runs thin: {bij_nul}")
    return "\n".join(regels)
