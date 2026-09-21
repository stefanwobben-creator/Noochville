"""channels.py — één gesprek-laag voor project, cirkel en persoon (fase 8, 19 september 2026).

DRIE SOORTEN, ÉÉN VORM. Een kanaal is een trail van berichten met een auteur en een tijd. Dat is
alles. De drie soorten verschillen in waar ze OVER gaan, niet in wat ze zijn:

    project:<pid>      het gesprek bij een project (wat tot nu toe "de wall" heette)
    circle:<record>    het gesprek van een cirkel
    goal:<doel_id>     het gesprek bij een doel — de taxonomie die Projects al kent
    topic:<id>         een los kanaal dat een mens zelf aanmaakt
    dm:<a>|<b>         tussen twee mensen; de twee id's staan gesorteerd, zodat A→B en B→A
                       gegarandeerd hetzelfde kanaal zijn en er nooit twee halve gesprekken ontstaan

GEEN MIGRATIE, EN DAAROM TWEE OPSLAGPLEKKEN. Een project-kanaal schrijft en leest `project["log"]`
via de ProjectLedger — daar staan 442 projecten aan bestaande gesprekken in, en zeven andere plekken
lezen die lijst. Die verplaatsen zou een migratie zijn met een stille kans op verlies, voor precies
nul winst: de vorm is al dezelfde. Cirkel- en persoonskanalen hebben nog geen bestaande opslag en
wonen daarom hier, in `data/channels.json`.

Dat is bewust ÉÉN klasse met twee achterkanten en niet twee stores met dezelfde methodes: wie een
kanaal aanspreekt hoeft niet te weten welk soort het is, en er is geen tweede plek die na een
wijziging uit de pas gaat lopen.

WAT DIT NIET IS. Geen notificatie-laag. `NotifStore` en `/inbox` bestaan hiernaast ONGEWIJZIGD
verder; er is niets gemigreerd en kanaalberichten hebben geen afgehandeld-veld. Alleen de
@-vermelding — één mens die een ander aanspreekt — is een bericht geworden.

DAT WIJKT AF VAN DE OPDRACHT, en de twee redenen staan hier omdat ze anders over een half jaar als
"nooit afgemaakt" lezen in plaats van als een besluit. Gemeten op de productie-notificaties,
19 september 2026, 338 rol-gerichte items:

  1. EEN DM HEEFT TWEE MENSEN NODIG, en die zijn er niet. Vijf van de 338 hebben een MENS als
     afzender. De rest komt van rol-id's en systeemnamen: compliance (69), claims-checker (46),
     harry_hemp (45), librarian (22), website_watcher (19). Bij 333 is er maar één kant van het
     gesprek. Je zou ze eenzijdig in het persoonskanaal van de ontvanger kunnen duwen, maar dat is
     precies niet wat een DM-kanaal is.

  2. ZE DRAGEN EEN AFHANDEL-MODEL, geen gelezen-vlag:
         read 259 · processed 258 · archived 225 · outcome 185
         verwerkingen 83 · poort 54 · done 33
     Dat is een verwerkingsgeschiedenis met uitkomsten en een poort-oordeel. Overzetten is niet
     één veld erbij maar dat model opnieuw bouwen bovenop een chat-trail — of 185 vastgelegde
     uitkomsten en 54 poort-oordelen stil laten verdwijnen.

Het DUBBELE dat fase 8 moest opheffen is wél weg: een @-vermelding heeft nu precies één
bestemming. Wat hiernaast blijft staan is geen duplicaat maar een ander soort object.
"""
from __future__ import annotations

import time
import uuid

from nooch_village.util import JsonStore

#: Kanaalsoorten. De prefix staat in het id zelf, zodat een kanaal-id overal zelf-verklarend is.
PROJECT, CIRCLE, DM, TOPIC, GOAL = "project", "circle", "dm", "topic", "goal"

#: Berichtsoorten binnen een kanaal. Een `notificatie` is een gemigreerd inbox-item: dezelfde
#: trail, maar met een verwerkingsgeschiedenis eronder die een gewoon bericht niet heeft.
COMMENT, NOTIFICATIE = "comment", "notificatie"


TEKST_MAX = 1500
TRAIL_MAX = 500          # per kanaal bewaard; ouder verdwijnt niet, maar wordt niet meer getoond


def project_kanaal(pid: str) -> str:
    return f"{PROJECT}:{pid}"


def circle_kanaal(record_id: str) -> str:
    return f"{CIRCLE}:{record_id}"



def topic_kanaal(topic_id: str) -> str:
    return f"{TOPIC}:{topic_id}"


def goal_kanaal(doel_id: str) -> str:
    """Het kanaal van een doel (`data/doelen.json`).

    EEN EIGEN SOORT, EN GEEN VOORAF AANGEMAAKT LOS KANAAL met de doelnaam erin. Dat laatste was de
    goedkopere weg — `maak_topic("MITH")` en klaar — en precies daarom fout: de naam van een doel
    is een weergavestring die een mens verandert, en dan wijst het kanaal nergens meer naar. Met
    `goal:<doel_id>` verwijst het kanaal naar het DOEL, en volgt een hernoeming vanzelf. Dezelfde
    afweging als bij `maak_topic`, waar het id bewust geen slug van de naam is.

    Geen tweede opslag: de trail leeft in `channels.json`, net als die van een topic."""
    return f"{GOAL}:{doel_id}"


def _sleutel(naam: str) -> str:
    """De naam gestript tot waar hij op botst: spaties samengevouwen, hoofdletters weg.

    "Batch 4", "batch-4" en "Batch  4" zijn voor een mens hetzelfde kanaal. Zonder deze normalisatie
    krijg je er drie, en dan heeft niemand meer het gesprek dat hij zoekt."""
    return " ".join(str(naam or "").replace("-", " ").split()).casefold()


def dm_kanaal(person_a: str, person_b: str) -> str:
    """Het DM-kanaal tussen twee mensen. Gesorteerd, dus richting-onafhankelijk."""
    a, b = sorted([str(person_a or ""), str(person_b or "")])
    return f"{DM}:{a}|{b}"


def soort_van(kanaal: str) -> str:
    return str(kanaal or "").split(":", 1)[0]


def doel_van(kanaal: str) -> str:
    """Het deel achter de prefix: een project-id, een record-id of 'a|b'."""
    return str(kanaal or "").split(":", 1)[1] if ":" in str(kanaal or "") else ""


def dm_leden(kanaal: str) -> list[str]:
    """De twee persoon-id's van een DM-kanaal. Leeg voor de andere soorten."""
    return doel_van(kanaal).split("|") if soort_van(kanaal) == DM else []


class ChannelStore(JsonStore):
    """De kanalen die hier wonen: cirkel en DM. Project-kanalen lopen via de ProjectLedger.

    `ledger` wordt geïnjecteerd en niet geïmporteerd: dezelfde discipline als bij de EventBus —
    een store die zelf zijn buren opzoekt is een store die je niet los kunt testen."""

    _WRITE_METHODS = ("post", "maak_topic", "hernoem_topic", "plaats_notificatie",
                      "add_reaction")
    _STATE = "_data"
    _default = dict

    def __init__(self, path: str, ledger=None):
        # `_ledger` VOOR `super().__init__`: die roept `_load()` aan, en een verse store schrijft
        # dan meteen — wat via `post` bij het project-pad langs de ledger zou willen.
        self._ledger = ledger
        super().__init__(path)
        self._data.setdefault("kanalen", {})
        self._data.setdefault("namen", {})

    # ── schrijven ────────────────────────────────────────────────────────────
    def post(self, kanaal: str, tekst: str, *, author_type: str = "human",
             author_id: str = "", herkomst: dict | None = None) -> dict | None:
        """Eén bericht. None bij een lege tekst — fail-closed, geen leeg bericht in een trail."""
        tekst = " ".join(str(tekst or "").split())[:TEKST_MAX]
        if not tekst or not kanaal:
            return None
        if soort_van(kanaal) == PROJECT:
            if self._ledger is None:
                return None
            return self._ledger.add_feed_entry(doel_van(kanaal), tekst, kind="comment",
                                               author_type=author_type, author_id=author_id)
        entry = {"id": uuid.uuid4().hex[:10], "kind": "comment",
                 "author": {"type": author_type, "id": author_id or ""},
                 "text": tekst, "at": time.time()}
        if herkomst:
            entry["herkomst"] = herkomst
        self._data.setdefault("kanalen", {}).setdefault(kanaal, []).append(entry)
        self._save()
        return entry

    def add_reaction(self, kanaal: str, entry_id: str, emoji: str) -> bool:
        """Een emoji-reactie op een bericht in dit kanaal. Per emoji een teller.

        EEN PROJECTKANAAL GAAT LANGS DE LEDGER, net als `post` en `trail`. Daar woont de trail
        (`project["log"]`) en daar staat de teller dus ook — `ProjectLedger.add_reaction` deed dit
        al voor de projectfeed, en dat is precies hetzelfde bericht. Het hier nog eens uitschrijven
        zou betekenen dat een reactie op de projectpagina en een reactie in Messages op twee
        plekken worden bijgehouden, op dezelfde regel.

        Geen id op het bericht = geen reactie. Dat is het oude schema; fail-closed."""
        emoji = (emoji or "").strip()
        if not (kanaal and entry_id and emoji):
            return False
        if soort_van(kanaal) == PROJECT:
            if self._ledger is None:
                return False
            return bool(self._ledger.add_reaction(doel_van(kanaal), entry_id, emoji))
        for e in (self._data.get("kanalen") or {}).get(kanaal) or []:
            if e.get("id") == entry_id:
                r = e.setdefault("reactions", {})
                r[emoji] = int(r.get(emoji, 0)) + 1
                self._save()
                return True
        return False

    def maak_topic(self, naam: str, *, door: str = "") -> str:
        """Een los kanaal met een eigen naam. Geeft het kanaal-id terug, of "" bij een lege naam.

        HET ID IS GEEN SLUG. Een `topic:<id>` met de naam apart in `namen`, en niet `topic:<naam>`.
        Zelfde argument als bij het gesorteerde DM-id: identiteit hoort niet aan een weergavestring
        te hangen. Hernoemen breekt de trail dus niet, en dat is geen theorie — dit is het eerste
        kanaal waarvan de naam door een mens is verzonnen en dus ooit verandert.

        IDEMPOTENT OP DE GENORMALISEERDE NAAM. Wie "Batch 4" maakt terwijl "batch-4" al bestaat,
        krijgt het bestaande kanaal. Twee halve gesprekken onder bijna dezelfde naam is precies het
        probleem dat een losse-kanaal-functie hoort op te lossen, niet te veroorzaken."""
        naam = " ".join(str(naam or "").split())[:80]
        if not naam:
            return ""
        sleutel = _sleutel(naam)
        for kanaal, bestaande_naam in (self._data.get("namen") or {}).items():
            if _sleutel(bestaande_naam) == sleutel:
                return kanaal
        kanaal = topic_kanaal(uuid.uuid4().hex[:10])
        self._data.setdefault("namen", {})[kanaal] = naam
        self._data.setdefault("kanalen", {}).setdefault(kanaal, [])
        self._data.setdefault("makers", {})[kanaal] = door or ""
        self._save()
        return kanaal

    def hernoem_topic(self, kanaal: str, naam: str) -> bool:
        """Alleen de naam verandert; het kanaal-id en dus de hele trail blijven staan.

        Dit is waarvóór het losse id bestaat. Zonder deze methode koopt optie A niets."""
        naam = " ".join(str(naam or "").split())[:80]
        if not naam or soort_van(kanaal) != TOPIC or kanaal not in (self._data.get("namen") or {}):
            return False
        self._data["namen"][kanaal] = naam
        self._save()
        return True

    def plaats_notificatie(self, kanaal: str, n: dict) -> dict | None:
        """Eén NotifStore-rij als bericht in een kanaal. Alleen voor de migratie.

        TWEE DINGEN DIE HIER ANDERS ZIJN DAN BIJ `post`, allebei met opzet:

        1. **Het id van de notificatie wordt het id van het bericht.** Daardoor is de migratie
           idempotent (tweemaal draaien voegt niets toe) én blijft elk bericht terug te voeren op
           de rij waar het uit komt, zolang `NotifStore` er nog staat.
        2. **`at` komt uit de notificatie**, niet van de klok. Anders staat de hele historie op de
           dag van de migratie en is de volgorde van drie maanden gesprek weg.

        ER GAAT GEEN VERWERKINGSSTATE MEE. Een eerdere versie kopieerde read/processed/outcome/poort
        mee in een `verwerking`-blok. Stefan heeft die eis op 20 september ingetrokken: *"alles wat
        tot dusver in de inbox is gekomen kon ik niet echt veel mee, dus dat werkte sowieso niet,
        dus ook niet om te houden."* Het is nu een gewoon bericht; de ontvanger is verantwoordelijk,
        zoals bij elk ander bericht.

        Geeft None als het bericht er al staat — dat is geen fout maar de idempotentie."""
        nid = str(n.get("id") or "")
        if not nid or not kanaal:
            return None
        rij = self._data.setdefault("kanalen", {}).setdefault(kanaal, [])
        if any(e.get("id") == nid for e in rij):
            return None
        entry = {
            "id": nid,
            "kind": NOTIFICATIE,
            "author": {"type": str(n.get("author_type") or "role"), "id": str(n.get("by") or "")},
            "text": str(n.get("tekst") or n.get("snippet") or ""),
            "at": float(n.get("at") or 0),
        }
        rij.append(entry)
        rij.sort(key=lambda e: float(e.get("at") or 0))
        self._save()
        return entry


    # ── lezen ────────────────────────────────────────────────────────────────
    def trail(self, kanaal: str, limit: int = TRAIL_MAX) -> list[dict]:
        """De berichten van dit kanaal, oudste eerst (een gesprek lees je van boven naar beneden)."""
        if soort_van(kanaal) == PROJECT:
            if self._ledger is None:
                return []
            p = self._ledger.get(doel_van(kanaal))
            rij = list((p or {}).get("log") or [])
        else:
            rij = list((self._data.get("kanalen") or {}).get(kanaal) or [])
        return rij[-limit:]

    def kanalen_van(self, person_id: str) -> list[str]:
        """De DM-kanalen waar deze persoon in zit."""
        return sorted(k for k in (self._data.get("kanalen") or {})
                      if soort_van(k) == DM and person_id in dm_leden(k))

    def bestaande(self, soort: str = "") -> list[str]:
        """De kanalen met minstens één bericht, eventueel op soort gefilterd. Project-kanalen
        staan hier NIET in: die leven in de ledger (zie de kop van deze module)."""
        return sorted(k for k, v in (self._data.get("kanalen") or {}).items()
                      if v and (not soort or soort_van(k) == soort))

    def topics(self) -> list[str]:
        """Alle losse kanalen, ook lege. Anders zie je een kanaal dat je net hebt aangemaakt niet
        staan tot iemand er iets in zegt — en dan lijkt het aanmaken mislukt.

        Iedereen ziet ze allemaal: er is bewust GEEN lidmaatschap-begrip in deze ronde (besluit
        Stefan, 20 september 2026). Dat is een tweede nieuw datamodel-concept en hoort niet in
        dezelfde ronde als het eerste."""
        return sorted((self._data.get("namen") or {}), key=lambda k: self.naam_van(k).lower())

    def naam_van(self, kanaal: str) -> str:
        return str((self._data.get("namen") or {}).get(kanaal) or "")

    def laatste(self, kanaal: str) -> dict | None:
        rij = self.trail(kanaal, limit=1)
        return rij[-1] if rij else None
