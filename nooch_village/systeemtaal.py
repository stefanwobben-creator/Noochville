"""Systeemtaal → mensentaal, deterministisch. De grond onder de leesbaarheidslaag.

Dit is deel 1 van twee: **grond-eerst, model-laatst.** Wat hier gebeurt is gratis, gebeurt altijd,
en hangt niet af van welk model er draait of dat er krediet is. Het model doet daarna het oordeel —
structuur, leesbaarheid, een menselijke vraag in plaats van een commando — maar deze swaps zijn
gegarandeerd, ook als het model wegvalt.

Zelfde MECHANIEK als de plain-language swaps in COPYCHECK-001, andere LIJST. Die gaat over
productwoorden voor een klant (petroleum → plastic); deze gaat over systeemwoorden voor de founder
(niet-uitvoering → draaide niet). Ze delen de vorm, niet de inhoud, en ze horen dus niet in één lijst.

DE REGEL DIE JE NIET MAG OVERTREDEN: een swap mag jargon vervangen, maar **geen mogelijkheden
dichtklappen.**

De aanleiding staat in het ijkpunt zelf. De ruwe tekst zei "mogelijk niet-uitvoering (hook of
service)": twee mogelijkheden en een slag om de arm. De eerste leesbare versie maakte daar
"waarschijnlijk draait zijn service niet meer" van — één mogelijkheid, en veel stelliger dan de bron.
Dat is feitbehoud dat faalt in het klein, en het gebeurde met opzet en aandacht door een mens. Doet
een zorgvuldige mens het al, dan doet een goedkoop model het vaker.

Daarom: `hook` én `service` worden allebei `achtergrondproces` — een KOEPELTERM die beide dekt zonder
er één te kiezen. Nooit `hook` → `service` of andersom. Drie eisen, die ook de model-trede erft:

  1. de slag om de arm blijft staan  — `mogelijk` blijft `mogelijk`;
  2. alternatieven blijven heel      — `hook of service` wordt niet stil één ervan;
  3. er komt geen detail bij         — de swap voegt nooit iets toe dat de bron niet had.

Wat context vraagt hoort HIER NIET. `payload`, `deliverable`, `capability`: die betekenen per zin
iets anders, en een vaste vervanging maakt ze soms fout. Die gaan naar het model. Deze lijst bevat
alleen gevallen waarin één vervanging altijd klopt.
"""
from __future__ import annotations

import re

# ── 1. de swaps ─────────────────────────────────────────────────────────────
#
# Alleen EENDUIDIGE gevallen: één vervanging die in elke zin klopt. Meerdere bronwoorden naar één
# doel mag alléén als dat doel een koepel is die ze allemaal dekt (hook/service → achtergrondproces),
# nooit als het er één van de twee kiest. `test_systeemtaal.py` bewaakt dat.
SWAPS: tuple[tuple[str, str], ...] = (
    # uitvoering
    # LET OP DE WOORDSOORT. "niet-uitvoering" is een zelfstandig naamwoord ("mogelijk
    # niet-uitvoering"), dus het doel moet dat ook zijn. "draaide niet" gaf "mogelijk draaide niet"
    # — grammaticaal kapot, en een swap die de zin breekt levert het model rommel aan.
    ("niet-uitvoering", "niet gestart"),
    ("puls-uitval", "de dagpuls draaide niet"),
    ("dead man's switch", "bewaker die aanslaat als er niets gebeurt"),
    # processen — KOEPEL: dekt hook én service én daemon, kiest er geen
    ("systemd-unit", "achtergrondproces"),
    ("cron-job", "achtergrondproces"),
    ("daemon", "achtergrondproces"),
    ("hook", "achtergrondproces"),
    ("service", "achtergrondproces"),
    # toestand
    ("no_data", "geen gegevens"),
    ("dry-run", "proefdraai"),
    ("queued", "in de wachtrij"),
    ("timeout", "duurde te lang"),
)

# Een combinatie die na de losse swaps dubbel zou lezen ("achtergrondproces of achtergrondproces").
# Eén koepelwoord dekt beide mogelijkheden; de "of" verdwijnt zonder dat er een keuze wordt gemaakt.
_DUBBEL = re.compile(r"achtergrondproces\s*(?:/|,|\bof\b|\bor\b)\s*achtergrondproces", re.I)

# ── 2. commando's eruit ─────────────────────────────────────────────────────
#
# Een commando is geen zin die je leest maar een instructie aan een terminal. In een bericht aan een
# mens is het ruis, en het duwt de echte tekst voorbij de leesgrens.
#
# WAT HIER MISGING EN WAAROM DE REGEL NU ZO IS. Mijn eerste versie at het commando én alles erachter:
# "Draai systemctl restart noochville-village om te herstellen." werd een lege string. Een swap die
# een hele zin opeet is geen leesbaarheid maar verlies — precies de fout die de feitbehoud-eis
# verbiedt, in de deterministische laag in plaats van in het model.
#
# Daarom twee stappen, en de tweede heeft een DREMPEL:
#   1. haal het commando zelf weg (de naam plus hoogstens twee argument-achtige tokens: iets met
#      een punt, streep of slash erin — "om" en "herstellen" zijn dat niet en blijven staan);
#   2. blijft er van die zin ≤3 woorden over, dan was het een pure instructie en gaat de zin weg.
#      Blijft er meer staan, dan droeg de zin ook een feit en blijft hij.
_ARG = r"(?:\s+(?:-{1,2}[\w-]+|[\w]*[./_-][\w./_-]*)){0,2}"
_COMMANDO = re.compile(
    r"(?:python\s+-m\s+[\w.]+|\./venv/bin/[\w./-]+|sudo\s+[\w./-]+"
    r"|git\s+[a-z-]+|systemctl\s+[a-z-]+|journalctl\s+[\w-]+|pytest\b)" + _ARG, re.I)

# Woorden die geen inhoud dragen: blijft alleen dit over, dan stond er niets meer dan de opdracht.
_LEEG = re.compile(r"^[\W_]*(?:beoordeel|draai|voer|run|check|zie|via|met|door|om|te|uit|hem|het|"
                   r"dit|dat|hier|dan|nog|even|alsjeblieft)?[\W_]*$", re.I)


def _zin_zonder_commando(zin: str) -> str:
    """Eén zin: was hij niets dan een opdracht, dan gaat hij weg. Anders blijft hij HEEL.

    ALLES OF NIETS, en dat is met opzet. Een commando midden uit een zin knippen haalde
    "systemctl restart" weg uit "de koppeling viel om nadat we systemctl restart draaiden" — de zin
    bleef staan maar miste het feit wát er gedraaid was. Een deterministische laag hoort alleen te
    doen wat onmiskenbaar veilig is; twijfelgevallen zijn voor het model, dat de hele tekst ziet."""
    kaal = _COMMANDO.sub(" ", zin)
    if kaal == zin:
        return zin
    woorden = [w for w in re.split(r"\s+", kaal.strip()) if w and not _LEEG.match(w)]
    return "" if len(woorden) <= 3 else zin


def ontjargon(tekst: str) -> str:
    """Systeemwoorden vervangen en commando's verwijderen. Verandert nooit de STREKKING.

    Idempotent: twee keer draaien geeft hetzelfde resultaat als één keer."""
    t = str(tekst or "")
    if not t.strip():
        return t
    # Per zin, want de drempel hieronder werkt op zinsniveau.
    t = " ".join(_zin_zonder_commando(z) for z in re.split(r"(?<=[.!?])\s+", t))
    for bron, doel in SWAPS:
        # Hoofdletter van de bron overnemen: staat het woord aan het begin van een zin, dan hoort
        # de vervanging dat ook te doen. Anders leest een keurige swap als een slordigheid.
        t = re.sub(r"\b" + re.escape(bron) + r"\b",
                   lambda m, d=doel: (d[0].upper() + d[1:]) if m.group(0)[:1].isupper() else d,
                   t, flags=re.I)
    t = _DUBBEL.sub("achtergrondproces", t)
    # Lidwoord meeverhuizen: "de hook" werd "de achtergrondproces". Eén onzijdig doelwoord, dus één
    # regel — geen grammatica-motor, alleen deze bekende botsing.
    t = re.sub(r"\b([Dd])e (achtergrondproces)\b", lambda m: ("H" if m.group(1) == "D" else "h")
               + "et " + m.group(2), t)
    # Losse haakjes en dubbele spaties die van het strippen overblijven; nooit inhoud.
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+([.,;:])", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip(" -–—·|").strip()


def raakt(tekst: str) -> list[str]:
    """Welke systeemwoorden zitten er in? Voor de meting en voor een zichtbaar spoor — niet om
    iets te blokkeren."""
    laag = str(tekst or "").lower()
    return [b for b, _ in SWAPS if re.search(r"\b" + re.escape(b) + r"\b", laag)]
