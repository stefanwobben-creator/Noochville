"""Gelogde decision sheets — wat een lid besloot, in zijn eigen woorden, na een coachsessie.

De Decision Coach (`views/decision_coach.py`) maakt een prompt die het lid in zijn EIGEN chat
plakt. Daar ontstaan twee dingen: een thinking report en een decision sheet. Het thinking report
blijft daar — er is hier geen veld voor en geen route naartoe. Alleen het sheet komt terug, en
belandt hier.

WAAROM DIT EEN EIGEN STORE IS. De scope vroeg eerst om hergebruik van "de bestaande decision log".
Die bestaat niet: geen `decisions.jsonl`, geen schema, niets in de 32 andere jsonl-stores. Dit is
dus de eerste, en hij staat bewust los van `insight.py` (kennis over de wereld) en van de
governance-records (besluiten over structuur). Een besluit van een mens over zijn eigen werk is
geen van beide, en die drie samenvoegen zou betekenen dat elke afgeleide meting later moet weten
welk soort besluit ze telt.

FAIL-CLOSED PARSEN. Een half gelezen sheet is erger dan een geweigerde plakactie: dan staat er een
regel in het logboek die zegt dat er besloten is, terwijl de helft ontbreekt. Er is daarom één
schrijfpad, en dat pad wordt alleen bereikt als alle zes verplichte velden gevuld zijn. Geen
best-effort, geen gedeeltelijke rij.
"""
from __future__ import annotations

import json
import logging
import os
import time

from pydantic import BaseModel, Field

from nooch_village import decision_coach as dc
from nooch_village.util import file_lock

log = logging.getLogger("village.decision_sheets")

BESTAND = "decision_sheets.jsonl"
BRON = "decision_coach"

#: De markers waartussen het sheet staat. Alles erbuiten wordt genegeerd — een lid mag gerust het
#: hele chatvenster plakken, zolang dit blok er maar in zit.
START = "=== DECISION SHEET ==="
EIND = "=== END DECISION SHEET ==="

#: Het thinking report is PRIVÉ. Het hoort de chat van het lid niet te verlaten, en als het per
#: ongeluk toch wordt meegeplakt, is weigeren de enige juiste uitkomst: filteren zou betekenen dat
#: we het eerst lezen en dan weggooien, en dan is het al binnen geweest.
PRIVE_MARKERS = ("THINKING REPORT", "This report is for you only")

#: De zeven velden, exact zoals ze in het geplakte blok staan. De volgorde is de leesvolgorde van
#: het sheet; de sleutels zijn de veldnamen in de opgeslagen rij.
VELDEN: tuple[tuple[str, str], ...] = (
    ("Decision", "decision"),
    ("Chosen option", "chosen_option"),
    ("Assumption 1", "assumption_1"),
    ("Assumption 2", "assumption_2"),
    ("Prediction (number and date)", "prediction"),
    ("Stop signal", "stop_signal"),
    ("Still unknown, and whether that is acceptable", "still_unknown"),
    # Het achtste veld is geen vraag aan het lid: het sjabloon vult hem bij het GENEREREN in en de
    # coach kopieert de regel letterlijk. Zo draagt het sheet zijn eigen herkomst mee. Zonder dit
    # veld zou de versie bij het loggen van schijf moeten komen — en dan logt een sheet uit
    # september de versie van december, stilzwijgend fout in precies het veld waarop je later
    # vertrouwt. Ontbreekt de regel, dan is het antwoord "unknown"; NOOIT de versie op schijf.
    ("Coach version", "template_version"),
)

#: Als enige mag dit veld leeg zijn: "niets meer onbekend" is een geldige uitkomst. De andere zes
#: zijn weigeringsgrond — een besluit zonder gekozen optie of zonder stopsignaal is geen besluit.
OPTIONEEL = {"still_unknown", "template_version"}


class DecisionSheet(BaseModel):
    """Het geplakte sheet, zoals het lid het uit zijn eigen chat haalt.

    Pydantic en geen dataclass, omdat dit INGEST-data is: tekst van buiten, waarvan de vorm moet
    worden afgedwongen voordat hij het logboek raakt (zie CLAUDE.md, Conventies). De rest van het
    dorp blijft dataclasses gebruiken."""

    decision: str
    chosen_option: str
    assumption_1: str
    assumption_2: str
    prediction: str
    stop_signal: str
    still_unknown: str = Field(default="")
    #: De versie van het sjabloon waarmee dit sheet is gemaakt, uit het sheet zelf.
    template_version: str = Field(default=dc.ONBEKENDE_VERSIE)


class Geweigerd(ValueError):
    """Deze plakactie wordt niet gelogd, en er is niets geschreven."""


def _blok(tekst: str) -> str:
    """De inhoud tussen de twee markers, of "" als het blok niet compleet is."""
    if START not in tekst or EIND not in tekst:
        return ""
    na_start = tekst.split(START, 1)[1]
    if EIND not in na_start:
        return ""
    return na_start.split(EIND, 1)[0]


def parse(tekst: str) -> DecisionSheet:
    """Lees het decision sheet uit een geplakt blok. Gooit `Geweigerd` met de reden.

    De volgorde van de controles is niet willekeurig. De privé-check staat vóór alles, want een
    thinking report dat per ongeluk wordt meegeplakt mag geen enkele verdere verwerking krijgen —
    ook geen foutmelding die de inhoud citeert."""
    tekst = tekst or ""
    for marker in PRIVE_MARKERS:
        if marker.lower() in tekst.lower():
            raise Geweigerd(
                "This paste contains your thinking report. That part is private and stays in your "
                "own chat — paste only the block between the decision sheet markers. Nothing was "
                "saved.")
    blok = _blok(tekst)
    if not blok.strip():
        raise Geweigerd(
            f"Could not find a complete decision sheet. The paste must contain both '{START}' and "
            f"'{EIND}', with the seven fields between them. Nothing was saved.")

    waarden: dict[str, str] = {}
    for label, sleutel in VELDEN:
        waarden[sleutel] = _veld(blok, label)
    ontbreekt = [label for label, sleutel in VELDEN
                 if sleutel not in OPTIONEEL and not waarden[sleutel]]
    if ontbreekt:
        raise Geweigerd(
            "These fields are empty or missing: " + ", ".join(f"'{x}'" for x in ontbreekt) +
            ". A decision sheet is only logged when it is complete. Nothing was saved.")
    if not waarden.get("template_version"):
        waarden["template_version"] = dc.ONBEKENDE_VERSIE
    return DecisionSheet(**waarden)


def _veld(blok: str, label: str) -> str:
    """De waarde achter `label:` — op dezelfde regel, plus eventuele vervolgregels.

    Een vervolgregel is alles tot het volgende bekende label; zo overleeft een antwoord van drie
    regels (een aanname mag een alinea zijn) zonder dat we op een vaste regellengte gokken."""
    labels = [x for x, _ in VELDEN]
    regels = blok.splitlines()
    uit: list[str] = []
    bezig = False
    for regel in regels:
        kop = regel.strip()
        gevonden = next((x for x in labels if kop.lower().startswith(x.lower() + ":")), "")
        if gevonden:
            if bezig:
                break                                     # volgend veld → dit veld is klaar
            if gevonden.lower() == label.lower():
                bezig = True
                uit.append(kop[len(gevonden) + 1:].strip())
            continue
        if bezig:
            uit.append(regel.strip())
    return " ".join(x for x in uit if x).strip()


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def log_sheet(data_dir: str, sheet: DecisionSheet, *, decider: str, role: str,
              raw: str) -> dict:
    """Schrijf één rij. Append-only, onder een lock, en geeft de geschreven rij terug.

    Het LOCK is hier geen overdaad: het dorp schrijft dit bestand vanuit de webserver, en twee
    leden die tegelijk op 'Log' drukken schrijven anders in elkaars regel. De andere jsonl-stores
    in deze codebase appenden zonder lock; dat is geen precedent maar een openstaande schuld.

    ER IS GEEN `template_version`-PARAMETER, en dat is met opzet. Die waarde komt uit het sheet
    zelf (`Coach version`), nooit van de aanroeper en nooit van schijf: een parameter zou de
    terugval waar hij is weggehaald gewoon weer mogelijk maken, één aanroeper verderop.

    `raw` bewaart het geplakte blok ONGEWIJZIGD. De zeven velden zijn de leesbare afgeleide; het
    origineel is wat het lid daadwerkelijk heeft neergelegd, en dat hoort niet te veranderen als
    de parser later slimmer wordt."""
    rij = {
        "timestamp": time.time(),
        "decider": decider,
        "role": role,
        "source": BRON,
        **sheet.model_dump(),                              # bevat template_version, uit het sheet
        "raw": raw,
    }
    os.makedirs(data_dir, exist_ok=True)
    with file_lock(pad(data_dir)):
        with open(pad(data_dir), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rij, ensure_ascii=False) + "\n")
    log.info("🧭 decision sheet gelogd door %s (%s)", decider or "onbekend", role or "geen rol")
    return rij


def alle(data_dir: str) -> list[dict]:
    """Alle gelogde sheets, nieuwste eerst. Een kapotte regel wordt overgeslagen, niet gegokt."""
    uit: list[dict] = []
    try:
        with open(pad(data_dir), encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    uit.append(json.loads(regel))
                except json.JSONDecodeError:
                    log.warning("decision_sheets: onleesbare regel overgeslagen")
    except FileNotFoundError:
        return []
    except OSError as e:                                   # noqa: BLE001
        log.warning("decision_sheets niet te lezen: %s", e)
        return []
    return sorted(uit, key=lambda r: r.get("timestamp") or 0, reverse=True)
