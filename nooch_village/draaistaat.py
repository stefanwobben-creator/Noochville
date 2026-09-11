"""De draaistaat: welke skill wanneer heeft gedraaid, en of er iets uitkwam.

Aanleiding (11 september 2026). Stefan keek naar een gekoppeld middel op een rolpagina en zei:
"op basis van één regel weet ik ook niet wat de skill precies doet, ik zie hem ook niet live
werkend ofzo". Meting daarop: van de 49 skill-bestanden schrijven er **acht** een spoor. Voor de
andere 41 bestaat er nergens een antwoord op de vraag of ze ooit iets hebben gedaan. Een catalogus
die zegt wat een skill belooft zonder te laten zien wat hij opleverde, is dezelfde fout als een
skill die "gelukt" meldt zonder iets te doen — één laag hoger.

**Waarom dit niet de Kroniek is.** De docstring van `evidence_ledger` zegt dat élke skill-run daar
hoort te landen, en dat klopte ooit als bedoeling. Maar `claims_substantiatie` indexeert inmiddels
ELKE regel uit dat register en kan er claim-bewijs van maken zodra `subject` een Nooch-merknaam
bevat en de status `bevestigd` is. Er 41 skills bij gooien is dus geen boekhoudkwestie maar een
claims-risico, twaalf dagen voor de EmpCo-handhaving. De Kroniek blijft wat hij in de praktijk is:
bewijs ónder een claim. Dit bestand is iets anders en lichters: heeft dit gereedschap gewerkt.

(De leesfout zit daarmee in `claims_substantiatie`, niet hier: dat hoort te filteren op
bewijsdragende skills in plaats van alles te indexeren. Aparte scope, aparte meting — de
claims-keten wijzig je niet als bijvangst van een observatie-scope.)

**Wat hier NIET in staat.** Geen payloads en geen resultaten. Alleen dát er iets was, geclassificeerd
met dezelfde lat als de rest van het dorp (`Inhabitant._classify_result`): `gelukt` / `leeg` /
`fout`. Een draaistaat die de inhoud meeschrijft wordt een tweede register van waarheden, en dan
drijven ze uit elkaar — precies wat we deze week vier keer hebben opgeruimd.

Opslag: append-only `data/draaistaat.jsonl`, één JSON-object per regel:
  {ts, skill, door, uitkomst, ms}
- `door`  — wie hem riep (rol-id, of een aanroeper-label als er geen rol is, bv. "cli")
- `uitkomst` ∈ {"gelukt", "leeg", "fout"}
- `ms`    — hoe lang hij deed, afgerond op hele milliseconden

Concurrency: append onder `util.file_lock`, zoals de Kroniek. Lezen is lock-vrij.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import threading
import time
from contextlib import contextmanager

from nooch_village.util import file_lock

log = logging.getLogger("village.draaistaat")

BESTANDSNAAM = "draaistaat.jsonl"

#: Dezelfde drie uitkomsten als de Kroniek, en met dezelfde reden: `leeg` is een echt resultaat en
#: geen mislukking. Wie die twee op één hoop gooit kan een dode bron niet van een stille bron
#: onderscheiden.
UITKOMSTEN = ("gelukt", "leeg", "fout")


def pad_voor(data_dir: str) -> str:
    return os.path.join(data_dir, BESTANDSNAAM)


class Draaistaat:
    """Append-only staat van skill-aanroepen. Schrijven faalt nooit hard: een kapotte staat mag
    geen enkele skill platleggen, want dan is de observatie duurder dan wat ze observeert."""

    def __init__(self, path: str):
        self.path = path
        self._rows: list[dict] | None = None

    # ── schrijven ────────────────────────────────────────────────────────────

    def noteer(self, *, skill: str, door: str, uitkomst: str, ms: int = 0,
               ts: float | None = None) -> dict | None:
        """Schrijf één aanroep weg. Geeft de regel terug, of None als er niets geschreven is.

        Fail-soft op ALLES: een onbekende uitkomst, een onschrijfbaar pad of een volle schijf geeft
        een logregel en None. Dit is de enige plek in het dorp waar een onbekende waarde niet
        fail-closed gooit, en dat is bewust: de aanroeper is een wrapper om een skill die al draait,
        en die mag nooit alsnog struikelen over zijn eigen boekhouding.
        """
        if uitkomst not in UITKOMSTEN:
            log.warning("draaistaat: onbekende uitkomst %r voor skill %r — niet genoteerd",
                        uitkomst, skill)
            return None
        row = {
            "ts":       ts if ts is not None else time.time(),
            "skill":    str(skill or ""),
            "door":     str(door or ""),
            "uitkomst": uitkomst,
            "ms":       int(ms),
        }
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
            with file_lock(self.path):
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception as exc:                      # noqa: BLE001 — zie de docstring
            log.warning("draaistaat: kon '%s' niet noteren: %s", skill, exc)
            return None
        if self._rows is not None:
            self._rows.append(row)
        return row

    # ── lezen (lock-vrij) ────────────────────────────────────────────────────

    def _laad(self) -> None:
        if self._rows is not None:
            return
        rows: list[dict] = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for regel in f:
                    regel = regel.strip()
                    if not regel:
                        continue
                    try:
                        r = json.loads(regel)
                    except ValueError:
                        continue                      # één kapotte regel mag de staat niet wissen
                    if isinstance(r, dict):
                        rows.append(r)
        except FileNotFoundError:
            pass
        except Exception as exc:                      # noqa: BLE001
            log.warning("draaistaat: kon '%s' niet lezen: %s", self.path, exc)
        self._rows = rows

    def alles(self) -> list[dict]:
        self._laad()
        return list(self._rows or [])

    def voor_skill(self, skill: str) -> list[dict]:
        return [r for r in self.alles() if r.get("skill") == skill]

    def laatste(self, skill: str) -> dict | None:
        """De meest recente aanroep van deze skill, of None als hij nooit gedraaid heeft.

        None is een volwaardig antwoord en het belangrijkste dat deze module levert: "nog geen
        spoor" is precies de lijst die je wil zien."""
        rijen = self.voor_skill(skill)
        return max(rijen, key=lambda r: r.get("ts") or 0) if rijen else None

    def laatste_opbrengst(self, skill: str) -> dict | None:
        """De meest recente aanroep die iets ópleverde (`gelukt`).

        Los van `laatste`, want die twee zeggen verschillende dingen: een skill die vanmorgen draaide
        en `leeg` teruggaf is iets anders dan een skill die vanmorgen iets vond. Wie alleen naar
        'laatst gedraaid' kijkt, ziet een dode bron voor levend aan."""
        rijen = [r for r in self.voor_skill(skill) if r.get("uitkomst") == "gelukt"]
        return max(rijen, key=lambda r: r.get("ts") or 0) if rijen else None

    def samenvatting(self) -> dict[str, dict]:
        """Per skill: hoe vaak, per uitkomst, en de twee tijdstempels. De datalaag onder /skills."""
        uit: dict[str, dict] = {}
        for r in self.alles():
            naam = r.get("skill") or ""
            if not naam:
                continue
            s = uit.setdefault(naam, {"totaal": 0, "gelukt": 0, "leeg": 0, "fout": 0,
                                      "laatst": 0.0, "laatste_opbrengst": 0.0})
            s["totaal"] += 1
            k = r.get("uitkomst")
            if k in UITKOMSTEN:
                s[k] += 1
            ts = float(r.get("ts") or 0)
            s["laatst"] = max(s["laatst"], ts)
            if k == "gelukt":
                s["laatste_opbrengst"] = max(s["laatste_opbrengst"], ts)
        return uit


# ── Wie riep hem: een thread-lokaal label ────────────────────────────────────
# Een skill krijgt bij `run(payload, context)` geen aanroeper mee, en de context weet niet welke
# rol hem gebruikt. Dat label zit alleen bij de aanroeper zelf. Elke inwoner draait op zijn eigen
# thread (zie inhabitant.react), dus een thread-lokaal veld is hier de juiste vorm en niet een
# globale: twee inwoners die tegelijk een skill gebruiken schrijven elk hun eigen naam.
#
# Zet niemand een label, dan blijft `door` leeg. Dat is een eerlijk antwoord ("onbekend") en géén
# reden om de notitie over te slaan — een aanroep zonder naam is nog steeds een aanroep.

_lokaal = threading.local()


@contextmanager
def aanroeper(naam: str):
    """Markeer wie de skills binnen dit blok gebruikt. Nestbaar; herstelt altijd de vorige waarde."""
    vorige = getattr(_lokaal, "door", "")
    _lokaal.door = str(naam or "")
    try:
        yield
    finally:
        _lokaal.door = vorige


def huidige_aanroeper() -> str:
    return getattr(_lokaal, "door", "") or ""


# ── De omwikkeling ───────────────────────────────────────────────────────────

_GEMARKEERD = "_draaistaat_omwikkeld"


def _uitkomst_van(resultaat) -> str:
    """Classificeer één skill-resultaat met dezelfde lat als de rest van het dorp.

    Bewust `Inhabitant._classify_result` en geen eigen kopie: die functie kent de fail-conventies
    (`error`, `ok:False`, `no_data`) én de META-sleutels die niet als inhoud tellen. Een tweede
    lezer van diezelfde conventie is precies de fout die hier deze week vier keer is opgeruimd.

    Lazy import: `inhabitant` importeert `skills`, en `skills` roept deze module aan. Op modulehoogte
    importeren maakt daar een cirkel van."""
    try:
        from nooch_village.inhabitant import Inhabitant
        status, _archetype = Inhabitant._classify_result(resultaat)
        return status if status in UITKOMSTEN else "gelukt"
    except Exception as exc:                          # noqa: BLE001 — nooit de skill breken
        log.debug("draaistaat: kon resultaat niet classificeren: %s", exc)
        return "gelukt"


def _staat_voor(context):
    """De draaistaat die bij deze context hoort, of None als er geen data_dir is.

    Geen data_dir is de normale toestand in veel tests en in losse scripts. Dan noteren we niets en
    draait de skill ongewijzigd — observatie mag nooit een voorwaarde voor uitvoering worden."""
    dd = getattr(context, "data_dir", None)
    if not dd:
        return None
    try:
        return Draaistaat(pad_voor(str(dd)))
    except Exception as exc:                          # noqa: BLE001
        log.debug("draaistaat: geen staat voor deze context: %s", exc)
        return None


def omwikkel(skill) -> bool:
    """Vervang `skill.run` door een variant die zichzelf noteert. Geeft terug of er iets veranderde.

    Waarom de METHODE en niet het object: vijf plekken in het dorp doen
    `isinstance(skill, DataSourceSkill)` en één leest `type(skill).__module__`. Een proxy-object
    breekt die allemaal stil. Door de gebonden methode op de instantie te vervangen blijft het
    object exact wat het was, en wordt tóch élke aanroeper gelogd — ook `registry.all()`, de
    onderzoekspas, de CLI en de demo's, die geen van alle via de inwoner lopen.

    Idempotent: tweemaal registreren wikkelt niet tweemaal.
    """
    if skill is None or getattr(skill, _GEMARKEERD, False):
        return False
    origineel = getattr(skill, "run", None)
    if not callable(origineel):
        return False
    naam = getattr(skill, "name", "") or ""

    @functools.wraps(origineel)
    def run(payload, context):
        staat = _staat_voor(context)
        door = huidige_aanroeper()
        t0 = time.perf_counter()
        try:
            resultaat = origineel(payload, context)
        except Exception:
            # Een skill die gooit is een `fout`, en juist die wil je in de staat zien staan: een
            # gereedschap dat altijd klapt ziet er zonder dit spoor identiek uit aan een dat nooit
            # is gebruikt. De uitzondering gaat daarna ongewijzigd door naar de aanroeper.
            if staat is not None:
                staat.noteer(skill=naam, door=door, uitkomst="fout",
                             ms=int((time.perf_counter() - t0) * 1000))
            raise
        if staat is not None:
            staat.noteer(skill=naam, door=door, uitkomst=_uitkomst_van(resultaat),
                         ms=int((time.perf_counter() - t0) * 1000))
        return resultaat

    try:
        skill.run = run
        setattr(skill, _GEMARKEERD, True)
    except Exception as exc:                          # noqa: BLE001 — een skill die zich niet laat
        log.warning("draaistaat: kon '%s' niet omwikkelen: %s", naam, exc)   # wikkelen draait gewoon
        return False
    return True


def is_omwikkeld(skill) -> bool:
    return bool(getattr(skill, _GEMARKEERD, False))
