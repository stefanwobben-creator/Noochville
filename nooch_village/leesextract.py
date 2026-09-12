"""leesextract — wat er op een gelezen pagina staat, in twee of drie zinnen, vóór het de note ingaat.

AANLEIDING (12 september 2026, het lijmvrij-onderzoek van Harry Hemp). `web_zoek` las de bovenste
vijf pagina's, 3000 tekens elk, en daarna gooide de keten dat lezen weg in drie stappen:

    de deliverable-note     `_format_record` kapt elk veld op 160 tekens → van 3000 blijven er 160
    de conclusiezin         `deliverable_kop.conclusie` leest díe note, dus ziet 160 tekens per pagina
    het verslag             `project_verslag.deliverable_blokken` kreeg `str(dict)[:1200]`: 1200 tekens
                            van een Python-dict, grofweg het fragment van de eerste treffer

Gevolg: ook als Google de juiste pagina vond, kon het verslag niet zeggen wat erop stond. De
rapportschrijver zag vier merknamen en verder niets, en Stefan gaf het verslag een 4.

WAT DEZE MODULE DOET. Eén modelronde per skillresultaat, op de goedkope trede, die per gelezen record
opschrijft wat de tekst zegt dat voor het checklist-item telt: namen, producten, materialen,
getallen, en wat voor pagina het is. Dat extract komt IN HET RECORD te staan (`extract`), vóór de
note wordt gerenderd en vóór het resultaat de deliverable-store ingaat. Zo lezen note, conclusie én
verslag hetzelfde extract, en hoeft geen van drieën het opnieuw te doen.

WAT HIJ NIET DOET. Hij oordeelt niet (of iets bij Nooch past is een andere stap) en hij voegt niets
toe: de harde eis in de prompt is "alleen wat er letterlijk staat". Het ruwe materiaal blijft in het
resultaat staan; het extract is een leeswijzer erbovenop, geen vervanging.

FAIL-SOFT. Geen model, geen krediet, onzin terug: dan geen extract, en de keten gedraagt zich als
voorheen. Een extract mag ontbreken; een resultaat niet.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("village.leesextract")

#: Vanaf dit aantal tekens is een tekstveld gelezen materiaal en geen fragment meer. Een fragment
#: (de snippet van de zoekmachine, ~300 tekens) staat al leesbaar in de note; daar valt niets uit te
#: halen wat er niet al staat.
LANG_TEKST = 600

#: De velden waarin skills hun gelezen tekst zetten, in volgorde van voorkeur. `tekst` is web_zoek,
#: `abstract` is OpenAlex/EPO, `text`/`content` de rest.
TEKSTVELDEN = ("tekst", "text", "abstract", "content", "body")

#: Eén modelronde, dus een plafond op het aantal records erin. Boven de tien leest een mens de note
#: toch niet meer, en de rest van het resultaat staat nog gewoon in de store.
MAX_RECORDS = 10

#: Twee tot drie zinnen. Langer is geen extract meer maar een tweede pagina.
EXTRACT_MAX = 400

#: Gelijk aan wat web_zoek per pagina meegeeft (`_TEKST_PER_PAGINA`); meer staat er niet in.
_INVOER_PER_RECORD = 3000
_TOKENS_PER_RECORD = 110

_TITELVELDEN = ("titel", "title", "name", "term", "query", "brand", "key")


def te_lezen(result, archetype) -> list[tuple[dict, str]]:
    """De records met gelezen materiaal: (record, tekstveld), in volgorde. Leeg als er niets te
    lezen valt: geen lijst-archetype, alleen korte velden, of de extracten staan er al.

    Alleen tellen wat de archetype-detectie al heeft aangewezen (`_classify_result`); zelf op zoek
    gaan naar 'iets wat op een lijst lijkt' maakt van een leeswijzer een tweede waarheid, dezelfde
    regel als in `deliverable_kop.tel_resultaten`."""
    if not isinstance(result, dict) or not archetype:
        return []
    kind, key = archetype
    if kind == "list":
        recs = [r for r in (result.get(key) or []) if isinstance(r, dict)]
    elif kind == "dictlist":
        recs = [r for r in (result.get(key) or {}).values() if isinstance(r, dict)]
    else:
        return []
    uit: list[tuple[dict, str]] = []
    for r in recs[:MAX_RECORDS]:
        if str(r.get("extract") or "").strip():
            continue                                     # al gedaan (herdraai, of de skill deed het zelf)
        for veld in TEKSTVELDEN:
            t = r.get(veld)
            if isinstance(t, str) and len(t.strip()) >= LANG_TEKST:
                uit.append((r, veld))
                break
    return uit


def _titel(rec: dict) -> str:
    for k in _TITELVELDEN:
        v = rec.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:120]
    return ""


def _prompt(item_tekst: str, paren: list[tuple[dict, str]]) -> str:
    stukken = []
    for i, (rec, veld) in enumerate(paren, start=1):
        kop = f"TEXT {i}" + (f" ({_titel(rec)})" if _titel(rec) else "")
        stukken.append(f"{kop}:\n{str(rec.get(veld) or '').strip()[:_INVOER_PER_RECORD]}")
    schema = ", ".join(f'"{i}": "<2-3 sentences>"' for i in range(1, len(paren) + 1))
    return (
        f"Below are {len(paren)} texts that were read in full for one checklist item. For EACH text "
        "write 2 to 3 sentences that state what the text says that matters for the item: names of "
        "companies, products, materials, institutes, numbers and claims, and what kind of page it is "
        "(article, product page, supplier, paper, blog, register).\n\n"
        "HARD RULE: use only what is literally in the text. Add no numbers, names or conclusions "
        "that are not there. If a text does not address the item, say in one sentence what the page "
        "is about instead; do not stretch it.\n"
        "Write in English; a quoted name or term stays in its original language.\n\n"
        f"ITEM: {(item_tekst or '').strip()[:300]}\n\n"
        + "\n\n".join(stukken)
        + f"\n\nAnswer ONLY with JSON, exactly this shape: {{{schema}}}"
    )


def _json_uit(rauw):
    """JSON uit een modelantwoord, ook met ```-fences eromheen. None bij onparseerbaar. Dezelfde
    tolerantie als `zoekstrategie._json_uit`: een fence is geen reden om een leesronde weg te gooien."""
    tekst = str(rauw or "").strip()
    if not tekst:
        return None
    tekst = re.sub(r"^```(?:json)?|```$", "", tekst, flags=re.M).strip()
    try:
        return json.loads(tekst)
    except Exception:                                    # noqa: BLE001
        m = re.search(r"\{.*\}", tekst, re.S)
        try:
            return json.loads(m.group()) if m else None
        except Exception:                                # noqa: BLE001
            return None


def verrijk(item_tekst: str, result, archetype, *, reason_fn=None, ladder=None) -> int:
    """Zet per gelezen record een `extract` in het record zelf. Eén modelronde voor alle records.
    Geeft het aantal geplaatste extracten terug; 0 = niets veranderd (fail-soft, zie moduletekst).

    Het resultaat wordt IN PLACE verrijkt, met opzet: note, store en verslag lezen daarna hetzelfde
    object, en er is geen tweede kopie die uit de pas kan lopen."""
    paren = te_lezen(result, archetype)
    if not paren:
        return 0
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn        # noqa: PLC0415 — lazy, testbaar
    prompt = _prompt(item_tekst, paren)
    try:
        rauw = reason_fn(prompt, json_mode=True, max_tokens=_TOKENS_PER_RECORD * len(paren) + 60,
                         call_site="lees_extract", ladder=ladder)
    except Exception as exc:                                     # noqa: BLE001 — nooit het pad breken
        log.info("leesextract overgeslagen (%s)", exc)
        return 0
    data = _json_uit(rauw)
    if not isinstance(data, dict):
        if rauw:
            log.info("leesextract: antwoord niet parseerbaar, geen extracten")
        return 0
    n = 0
    for i, (rec, _veld) in enumerate(paren, start=1):
        zin = " ".join(str(data.get(str(i)) or "").split()).strip().strip('"')
        if zin:
            rec["extract"] = zin[:EXTRACT_MAX]
            n += 1
    return n
