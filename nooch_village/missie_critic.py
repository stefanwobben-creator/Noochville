"""missie_critic — de poort vóór 'klaar voor review'.

De review-gate liet elk project door zodra de vakjes waren afgevinkt. Dat is een telling, geen
oordeel: een rapport dat de vraag niet beantwoordt, dat leeg is, of dat prachtig geschreven maar
off-mission is, haalde precies dezelfde schone `awaiting_review` als een rapport dat klopt. De mens
merkte het verschil pas bij het lezen — en dat is precies het werk dat we hem wilden besparen.

Deze critic toetst vier dingen, en ze staan bewust in deze volgorde van goedkoop naar duur:

  1. **substantieel** — is er überhaupt iets opgeleverd? (deterministisch)
  2. **beantwoordt**  — dekt het rapport de taken en de done-when? (deterministisch)
  3. **missie**       — dient dit de missie/strategie? (deterministisch, `strategie_relevantie`)
  4. **gegrond**      — is elke bewering gegrond in een deliverable of Kroniek-record? (LLM, premium)

Alleen de vierde kost een LLM-call, en die gaat via de bestaande `tegenspraak`-skill — dezelfde
adversariële toets die een rol handmatig op zijn output kon draaien, nu automatisch en op de
premium-trede. De eerste drie zijn rekenwerk: goedkoop, reproduceerbaar en testbaar zonder netwerk.

**Fail-soft met een scherpe rand.** Geen LLM → `gegrond` wordt "onbekend", NIET "afgekeurd": een
weggevallen leverancier mag geen projecten blokkeren. Maar "onbekend" is ook geen "geslaagd" — het
reist mee in de notitie, zodat de mens ziet dat die toets niet gedraaid heeft. De drie
deterministische toetsen draaien altijd, dus er is nooit een puls zonder oordeel.

Wat hier BEWUST niet in zit: cross-rol-review. Een rapport automatisch langs compliance, de
Librarian en Noochie sturen klinkt goed, maar zet bij elke afwijzing drie andere rollen aan het
werk — en dat is geen review meer maar een lawine. Selectief routeren (wélk rapport, wélke rol,
hoe vaak) is een eigen ontwerpvraag; die komt later, als de critic-cijfers laten zien waar de
tweede blik echt nodig is.

**Nooit stil doorlaten.** Zakt de critic, dan volgt precies één herkans-pas (het einddocument wordt
opnieuw gesynthetiseerd, mét de kritiek erin). Blijft het zakken, dan gaat het project alsnog naar
review — maar niet SCHOON: het oordeel staat op het project, in een role-message en in het event.
Een project eeuwig tegenhouden is erger dan een gemarkeerd project: dan verdwijnt het uit beeld.

Elke afwijzing landt in `critic_labels.jsonl` (het claims_labels-patroon): append-only, één regel
per oordeel. Dat is de trainings- en meetreeks — waaraan zakken rapporten, en wordt dat beter?
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

log = logging.getLogger("village.critic")

BESTAND = "critic_labels.jsonl"

# De vier assen. Volgorde = de volgorde waarin ze gedraaid worden (goedkoop eerst).
ASSEN = ("substantieel", "beantwoordt", "missie", "gegrond")

# Een rapport onder deze lengte is geen rapport. Bewust laag: de toets moet "er staat vrijwel niets"
# vangen, niet "het had langer gemogen" — dat laatste is een smaakoordeel en niet aan de critic.
MIN_DOCUMENT_CHARS = 400
# Hoeveel van de telbare taken een eigen kop in het document moeten hebben. Het einddocument-format
# schrijft '## <taak>' per taak voor, dus dit is te meten. Niet 100%: een LLM parafraseert een
# taakkop soms, en daar mag een rapport niet op zakken.
MIN_TAAK_DEKKING = 0.6
# Minimaal aantal strategie-thema's dat een rapport moet raken (mission.strategie_relevantie).
# 1 is een lage lat, en dat is de bedoeling: dit vangt "gaat nergens over ons" af, niet "had
# strategischer gekund".
MIN_STRATEGIE_THEMAS = 1

# De grondings-toets draait op de PREMIUM-trede. Reden staat in llm_keuze.PREMIUM_ONLY: bij een
# oordeel-site is "geen antwoord" een eerlijker uitkomst dan een goedkoop antwoord dat als premium
# oordeel wordt gelezen. De dorpsstaart blijft eronder hangen (zachte staart), zodat een wegvallende
# leverancier geen projecten blokkeert — maar de kop is bewust duur.
PREMIUM_LADDER = "anthropic:claude-sonnet-4-5"

def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


# ── De vier toetsen ──────────────────────────────────────────────────────────────────────────

def _substantieel(document: str, deliverables: list, checklist: dict | None) -> tuple[bool, str]:
    """Is er iets opgeleverd? Vangt het lege project — de duurste vorm van valse voltooiing, want
    hij ziet er van buiten uit als een afgerond project."""
    doc = (document or "").strip()
    echte = [d for d in (deliverables or []) if d]
    leeg_items = _lege_items(checklist)
    telbaar = _telbare_items(checklist)
    if len(doc) < MIN_DOCUMENT_CHARS:
        return False, (f"het rapport is {len(doc)} tekens — dat is geen rapport "
                       f"(minimaal {MIN_DOCUMENT_CHARS})")
    if not echte and telbaar:
        return False, "geen enkele taak leverde een deliverable op; het rapport rust nergens op"
    if telbaar and len(leeg_items) == len(telbaar):
        return False, (f"alle {len(telbaar)} taken liepen leeg (onderzocht, niets gevonden) — "
                       f"dit project heeft geen antwoord, alleen kennisgaten")
    return True, ""


def _beantwoordt(document: str, project: dict, checklist: dict | None) -> tuple[bool, str]:
    """Dekt het rapport de taken en de done-when?

    Deterministisch, want het einddocument-format schrijft een '## <taak>'-kop per taak voor. Wie
    die koppen niet levert, heeft de vraag niet per taak beantwoord — hoe mooi de tekst ook is."""
    doc = (document or "")
    koppen = " ".join(m.group(1).lower() for m in re.finditer(r"^##\s+(.+)$", doc, re.M))
    telbaar = _telbare_items(checklist)
    if telbaar:
        gedekt = sum(1 for it in telbaar if _overlap(str(it.get("text") or ""), koppen) >= 0.34)
        deel = gedekt / len(telbaar)
        if deel < MIN_TAAK_DEKKING:
            return False, (f"maar {gedekt} van de {len(telbaar)} taken heeft een eigen kop in het "
                           f"rapport; de rest is niet per taak beantwoord")
    done_when = str(project.get("done_when") or project.get("dod_outcome") or "").strip()
    if done_when and _overlap(done_when, doc.lower()) < 0.25:
        return False, (f"het rapport raakt de done-when niet: \"{done_when[:100]}\"")
    return True, ""


def _missie(document: str) -> tuple[bool, str]:
    """Dient dit de missie? Via `mission.strategie_relevantie` — dezelfde deterministische
    thema-meting die de radar en Stage-0 gebruiken, zodat 'strategisch relevant' overal hetzelfde
    betekent en niet per plek opnieuw wordt uitgevonden."""
    try:
        from nooch_village.mission import strategie_relevantie
        score, labels = strategie_relevantie(document or "")
    except Exception as e:                               # noqa: BLE001 — nooit een project blokkeren
        log.warning("missie-toets overgeslagen: %s", e)
        return True, ""
    if score < MIN_STRATEGIE_THEMAS:
        return False, ("het rapport raakt geen enkel strategie-thema uit de grondwet — het is niet "
                       "te zien waarom Nooch dit werk deed")
    return True, f"raakt {score} strategie-thema('s): {', '.join(labels[:3])}"


def _gegrond(document: str, deliverables: list, project: dict, *, skill=None,
             context=None) -> tuple[bool | None, str]:
    """Is elke bewering gegrond in een deliverable of Kroniek-record?

    Via de bestaande `tegenspraak`-skill: die zoekt de zwakste claim en levert een lijst beweringen
    die NIET in de meegegeven onderbouwing staan. Precies deze toets, en hij bestond al — hier
    draait hij automatisch in plaats van op verzoek.

    Geeft None bij "kon niet toetsen" (geen LLM, geen skill). Dat is bewust geen False: een
    weggevallen leverancier mag geen rapporten afkeuren. Het reist wél mee als onbekend."""
    bewijs = "\n".join(str(d)[:600] for d in (deliverables or [])[:8])
    doel = str(project.get("done_when") or project.get("dod_outcome") or "").strip()
    try:
        if skill is None:
            from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
            skill = TegenspraakSkill()
        uit = skill.run({"tekst": (document or "")[:6000], "bewijs": bewijs, "doel": doel,
                         "ladder": PREMIUM_LADDER}, context)
    except Exception as e:                               # noqa: BLE001
        log.warning("grondings-toets faalde fail-soft: %s", e)
        return None, "de grondings-toets kon niet draaien"
    if not isinstance(uit, dict) or uit.get("error") or uit.get("ok") is False:
        return None, "de grondings-toets gaf geen oordeel (geen LLM?)"
    ongegrond = [str(x) for x in (uit.get("ongegrond") or []) if str(x).strip()]
    if ongegrond:
        return False, ("niet gegrond in de deliverables: " + "; ".join(ongegrond[:3])[:400])
    if str(uit.get("oordeel") or "").strip().lower() == "moet bij":
        return False, f"de tegenspraak-toets zegt 'moet bij': {str(uit.get('revisie') or '')[:200]}"
    return True, str(uit.get("samenvatting") or "houdt stand")


# ── Hulpjes ──────────────────────────────────────────────────────────────────────────────────

def _telbare_items(checklist: dict | None) -> list:
    from nooch_village.projects import _NIET_TELBAAR
    items = (checklist or {}).get("items") or []
    return [it for it in items if not any(it.get(v) for v in _NIET_TELBAAR)]


def _lege_items(checklist: dict | None) -> list:
    """Items die zijn uitgevoerd maar niets opleverden. Zie `Inhabitant._execute_checklist`: die
    zet `leeg` op zo'n item, zodat het afgevinkt kan zijn zónder als antwoord te tellen."""
    return [it for it in _telbare_items(checklist) if it.get("leeg")]


def _woorden(tekst: str) -> set:
    return {w for w in re.split(r"[\W_]+", (tekst or "").lower()) if len(w) >= 4}


def _overlap(a: str, b: str) -> float:
    """Welk deel van de betekenisdragende woorden uit `a` komt voor in `b`."""
    wa = _woorden(a)
    if not wa:
        return 1.0                                       # niets om te dekken → geen bezwaar
    wb = _woorden(b)
    return len(wa & wb) / len(wa)


# ── Het oordeel ──────────────────────────────────────────────────────────────────────────────

def beoordeel(*, project: dict, document: str, deliverables: list, checklist: dict | None = None,
              skill=None, context=None) -> dict:
    """Toets een rapport op de vier assen. Geeft
    {geslaagd, oordelen: {as: True|False|None}, redenen: [...], samenvatting}.

    `geslaagd` is False zodra één as False is. Een as op None (niet te toetsen) blokkeert niet,
    maar telt ook niet als geslaagd — hij staat als onbekend in de samenvatting."""
    oordelen: dict = {}
    redenen: list[str] = []

    for naam, fn in (("substantieel", lambda: _substantieel(document, deliverables, checklist)),
                     ("beantwoordt", lambda: _beantwoordt(document, project, checklist)),
                     ("missie", lambda: _missie(document))):
        try:
            ok, waarom = fn()
        except Exception as e:                           # noqa: BLE001 — een kapotte toets ≠ afkeuring
            log.warning("critic-toets '%s' faalde fail-soft: %s", naam, e)
            ok, waarom = None, f"de toets '{naam}' kon niet draaien"
        oordelen[naam] = ok
        if ok is False and waarom:
            redenen.append(f"{naam}: {waarom}")

    # De dure toets pas als de goedkope niet al gezakt zijn: een leeg rapport hoeft geen premium
    # LLM-call om afgekeurd te worden.
    if all(oordelen.get(a) is not False for a in ("substantieel", "beantwoordt", "missie")):
        ok, waarom = _gegrond(document, deliverables, project, skill=skill, context=context)
        oordelen["gegrond"] = ok
        if ok is False and waarom:
            redenen.append(f"gegrond: {waarom}")
    else:
        oordelen["gegrond"] = None
        redenen.append("gegrond: niet getoetst — de goedkope toetsen zakten al")

    geslaagd = all(oordelen.get(a) is True for a in ASSEN)
    onbekend = [a for a in ASSEN if oordelen.get(a) is None]
    if geslaagd:
        samenvatting = "de critic laat dit rapport staan: gegrond, beantwoordend, substantieel en op missie"
    else:
        samenvatting = "de critic houdt dit rapport tegen — " + " | ".join(redenen[:3])
    if onbekend:
        samenvatting += f" (niet getoetst: {', '.join(onbekend)})"
    return {"geslaagd": geslaagd, "oordelen": oordelen, "redenen": redenen,
            "onbekend": onbekend, "samenvatting": samenvatting}


def notitie(oordeel: dict, *, herkansing: bool) -> str:
    """De zichtbare critic-notitie op de projectkaart. Nooit stil: als de critic iets tegenhoudt,
    moet dat op de kaart staan in de taal van de lezer, niet alleen in een logregel."""
    kop = "🔎 Missie-critic: " + ("dit rapport gaat één keer terug voor herstel."
                                  if herkansing else
                                  "dit rapport haalt de lat NIET, ook niet na herstel.")
    regels = "\n".join(f"- {r}" for r in (oordeel.get("redenen") or []))
    staart = ("\nHet gaat toch naar review — een project eeuwig tegenhouden verbergt het. Lees dit "
              "oordeel mee bij je beoordeling." if not herkansing else "")
    return f"{kop}\n{regels}{staart}"


# ── De meetreeks ─────────────────────────────────────────────────────────────────────────────

def leg_vast(data_dir: str, *, project_id: str, rol: str, oordeel: dict, fase: str) -> dict | None:
    """Leg één critic-oordeel append-only vast (claims_labels-patroon).

    Ook een geslaagd oordeel gaat erin: zonder de geslaagde regels weet je alleen hoeveel er zakten,
    niet welk aandeel dat is — en dan is 'de critic wijst veel af' niet van 'het dorp levert veel
    slechte rapporten' te onderscheiden. Fail-soft: labelen mag een puls nooit breken."""
    rij = {"project": project_id, "rol": rol, "fase": fase,
           "geslaagd": bool(oordeel.get("geslaagd")),
           "oordelen": oordeel.get("oordelen") or {},
           "redenen": [str(r)[:300] for r in (oordeel.get("redenen") or [])][:5],
           "ts": time.time()}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(rij, ensure_ascii=False) + "\n")
    except Exception as e:                               # noqa: BLE001
        log.warning("critic-label niet weggeschreven: %s", e)
        return None
    return rij


def alle(data_dir: str) -> list[dict]:
    """Alle critic-oordelen, oudste eerst. Kapotte regels worden overgeslagen, niet fataal."""
    uit: list[dict] = []
    try:
        with open(pad(data_dir), encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = json.loads(regel)
                except ValueError:
                    continue
                if isinstance(rij, dict):
                    uit.append(rij)
    except FileNotFoundError:
        return []
    except Exception as e:                               # noqa: BLE001
        log.warning("critic-labelbestand onleesbaar: %s", e)
        return []
    return uit
