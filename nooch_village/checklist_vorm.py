"""Wat is een bruikbare checklist-stap? Deterministisch, geen model.

AANLEIDING (29 aug 2026). De checklist-AI leverde paragraaflange suggesties die bovendien
"recycled polymers" en "algae-based plastics" als ONZE materialen opvoerden. Dat zijn ze niet, en
'recycled' is een claim die je bij ons niet zomaar mag zetten.

De oorzaak van het tweede is bekend en zit in het GROND-BLOK: de planner krijgt de kennislaag mee —
kaartjes, inzichten en Kroniek-records uit `openalex_evidence`, `epo_patents` en de radar — met de
instructie "bouw hierop voort". Nergens staat dat dat EXTERN ONDERZOEK is en geen inventaris van wat
wij gebruiken. Een model dat "PHA, PBAT, algae-based" leest onder het kopje 'wat we al weten',
schrijft het terug als het onze. De prompt is daarop aangepast; deze module is het vangnet
eronder — want een prompt is een verzoek en een poort is een garantie.

DRIE REGELS, en ze zijn alle drie vormcontrole, geen smaak:

1. KORT. Een stap is een handeling, geen alinea. Max `MAX_WOORDEN` woorden — geijkt op de stappen
   die MENSEN zelf intypen ("reach out and chase", "Order all 'set dressing' materials").
2. BEGINT MET EEN WERKWOORD. Een stap die met 'de', 'het' of 'een' begint is een onderwerp, geen
   opdracht. Fail-OPEN: alleen een korte lijst bekende NIET-werkwoorden wordt geweigerd; een woord
   dat we niet kennen laten we door. Liever een stap te veel dan een goede stap geblokkeerd door
   een woordenlijst die nooit compleet is.
3. GEEN CLAIM DIE WIJ NIET MOGEN MAKEN. Getoetst tegen `config/claims_database.json` — dezelfde
   database die Compliance gebruikt, met 56 gecureerde termen, hun stoplicht, de reden en het
   wettelijke bron-detail. GEEN eigen woordenlijst hier: dan zouden twee plekken hetzelfde feit
   uitleggen en uit elkaar lopen (`reference, don't copy`).

WAT DEZE MODULE NIET KAN. Hij weet niet wat Nooch écht gebruikt — er is geen bill of materials in
het dorp. Hij kan dus wél zien dat 'recycled' een gereguleerde claim is, maar niet dat 'algae-based
plastic' geen Nooch-materiaal is. Zolang die lijst er niet is, is dit de scherpste grond die er is;
een verzonnen materialenlijst hier zou erger zijn dan geen.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.checklist")

# Geijkt op wat mensen zelf intypen. De gemeten AI-suggesties waren 25-40 woorden.
MAX_WOORDEN = 12

# Openers die van een stap een onderwerp maken in plaats van een opdracht. Bewust KORT en gesloten:
# dit is een weigerlijst, geen goedkeurlijst — alles wat er niet in staat mag door.
_GEEN_WERKWOORD = frozenset({
    "de", "het", "een", "deze", "dit", "die", "dat", "er", "we", "wij", "ik", "je", "jij", "u",
    "men", "alle", "elk", "elke", "als", "voor", "bij", "met", "over", "door", "uit", "in", "op",
    "the", "a", "an", "this", "that", "these", "those", "we", "i", "you", "all", "for", "with",
    "about", "there", "it", "our", "their",
})

# Een parenthetische opsomming: haakjes met een komma erin, of een heel lang haakje. Dat is waar de
# materiaal-dumps zaten ("(PHA, PBAT, algae-based plastics)").
_HAAKJES_DUMP = re.compile(r"\([^)]*,[^)]*\)|\([^)]{40,}\)")


def _woorden(tekst: str) -> list[str]:
    return [w for w in re.split(r"\s+", (tekst or "").strip()) if w]


def keur(tekst: str, *, data_dir: str = "") -> dict:
    """Mag deze stap op de checklist? Geeft {ok, redenen, claims}.

    `redenen` is leeg als het goed is. Fail-OPEN op de claim-toets: is de database onleesbaar, dan
    keurt hij op vorm alleen — een kapotte database mag het plannen niet stilzetten, en de
    compliance-rol ziet zo'n stap alsnog."""
    tekst = (tekst or "").strip()
    redenen: list[str] = []
    if not tekst:
        return {"ok": False, "redenen": ["leeg"], "claims": []}

    ww = _woorden(tekst)
    if len(ww) > MAX_WOORDEN:
        redenen.append(f"te lang ({len(ww)} woorden, max {MAX_WOORDEN}) — een stap is een "
                       f"handeling, geen alinea")
    eerste = re.sub(r"[^\w-]", "", ww[0]).lower()
    if eerste in _GEEN_WERKWOORD:
        redenen.append(f"begint met '{ww[0]}' — een stap begint met een werkwoord")
    if _HAAKJES_DUMP.search(tekst):
        redenen.append("bevat een opsomming tussen haakjes — noem het onderwerp, niet de lijst")

    claims: list[dict] = []
    try:
        from nooch_village import claims_db
        uit = claims_db.check_tekst(tekst, data_dir=data_dir or None)
        claims = [b for b in uit.get("bevindingen", [])
                  if b.get("stoplicht") in ("red", "orange")]
    except Exception as e:                               # noqa: BLE001 — fail-open op de db
        log.warning("claim-toets op een checklist-stap overgeslagen: %s", e)
    for b in claims:
        redenen.append(f"claim '{b.get('term')}' ({b.get('stoplicht')}) — {b.get('waarom')}")
    return {"ok": not redenen, "redenen": redenen, "claims": claims}


def zeef(items: list, *, data_dir: str = "") -> tuple[list, list]:
    """(behouden, geweigerd) voor een lijst voorgestelde items.

    Geweigerde items dragen hun `redenen` mee: een stille drop zou betekenen dat je niet kunt zien
    dat de planner iets onbruikbaars maakte — en dan is de kwaliteit van het model niet te meten."""
    goed, weg = [], []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        oordeel = keur(it.get("tekst") or "", data_dir=data_dir)
        if oordeel["ok"]:
            goed.append(it)
        else:
            weg.append({**it, "redenen": oordeel["redenen"]})
    if weg:
        log.info("checklist-vorm: %d van de %d stappen geweigerd (%s)", len(weg),
                 len(goed) + len(weg), "; ".join(r for w in weg for r in w["redenen"])[:200])
    return goed, weg


# ── Werkt de suggestie eigenlijk? Eén regel per project, meer niet ───────────
#
# DOM MET OPZET. Geen analytics-rig, geen sessies, geen trechter: per aangemaakt project één regel
# met hoeveel suggesties er lagen en hoeveel er zijn overgenomen. Genoeg om over een week
# kill-of-houden op een GETAL te beslissen in plaats van op een gevoel, en te weinig om zelf een
# onderhoudslast te worden.
#
# Append-only jsonl naast `llm_usage.jsonl` en `groeidagboek.jsonl` — dezelfde meet-spoor-familie.
# Bewust GEEN store op `_Stores`: dit is een logboek, geen bron van waarheid, en de conventie-poort
# telt stores om precies die reden.

SPOOR = "checklist_suggesties.jsonl"


def noteer_acceptatie(data_dir: str, *, aangeboden: int, overgenomen: int, eigen: int = 0,
                      pid: str = "", tijd=None) -> bool:
    """Leg vast wat er met de suggesties gebeurde. Fail-soft: meten mag nooit iets blokkeren.

    `aangeboden` = hoeveel suggesties de wizard toonde, `overgenomen` = hoeveel de mens aantikte,
    `eigen` = hoeveel stappen hij zelf typte. Die derde is de eerlijke noemer: nul overgenomen bij
    nul eigen stappen betekent 'geen checklist gemaakt', niet 'suggesties genegeerd'."""
    import json
    import os
    import time
    if not data_dir or aangeboden < 0 or overgenomen < 0:
        return False
    rij = {"ts": (tijd if tijd is not None else time.time()),
           "pid": str(pid or "")[:40], "aangeboden": int(aangeboden),
           "overgenomen": int(overgenomen), "eigen": int(eigen)}
    try:
        with open(os.path.join(data_dir, SPOOR), "a", encoding="utf-8") as f:
            f.write(json.dumps(rij, ensure_ascii=False) + "\n")
        return True
    except Exception as e:                               # noqa: BLE001 — meten blokkeert nooit
        log.warning("acceptatie-spoor niet weggeschreven: %s", e)
        return False


def acceptatie(data_dir: str) -> dict:
    """De telling terug: {projecten, aangeboden, overgenomen, eigen, aandeel}.

    `aandeel` is overgenomen/aangeboden, en None als er nooit iets is aangeboden — geen deling die
    0% suggereert waar de vraag niet gesteld is. Zelfde regel als `no_data ≠ nul`."""
    import json
    import os
    pad = os.path.join(data_dir or "", SPOOR)
    uit = {"projecten": 0, "aangeboden": 0, "overgenomen": 0, "eigen": 0, "aandeel": None}
    if not os.path.exists(pad):
        return uit
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                try:
                    r = json.loads(regel)
                except ValueError:
                    continue
                uit["projecten"] += 1
                for k in ("aangeboden", "overgenomen", "eigen"):
                    uit[k] += int(r.get(k) or 0)
    except Exception as e:                               # noqa: BLE001
        log.warning("acceptatie-spoor onleesbaar: %s", e)
        return uit
    if uit["aangeboden"]:
        uit["aandeel"] = round(uit["overgenomen"] / uit["aangeboden"], 3)
    return uit
