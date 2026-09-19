"""channels.py — één gesprek-laag voor project, cirkel en persoon (fase 8, 19 september 2026).

DRIE SOORTEN, ÉÉN VORM. Een kanaal is een trail van berichten met een auteur en een tijd. Dat is
alles. De drie soorten verschillen in waar ze OVER gaan, niet in wat ze zijn:

    project:<pid>      het gesprek bij een project (wat tot nu toe "de wall" heette)
    circle:<record>    het gesprek van een cirkel
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

WAT DIT NIET IS. Geen notificatie-laag. De 338 rol-notificaties in `NotifStore` zijn werk dat
afgehandeld moet worden en horen op `/inbox`, niet in een chat-stroom. Alleen de @-vermelding — één
mens die een ander aanspreekt — is een bericht, en die landt sinds fase 8 in het DM-kanaal tussen
die twee.
"""
from __future__ import annotations

import time
import uuid

from nooch_village.util import JsonStore

#: Kanaalsoorten. De prefix staat in het id zelf, zodat een kanaal-id overal zelf-verklarend is.
PROJECT, CIRCLE, DM = "project", "circle", "dm"

TEKST_MAX = 1500
TRAIL_MAX = 500          # per kanaal bewaard; ouder verdwijnt niet, maar wordt niet meer getoond


def project_kanaal(pid: str) -> str:
    return f"{PROJECT}:{pid}"


def circle_kanaal(record_id: str) -> str:
    return f"{CIRCLE}:{record_id}"


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

    _WRITE_METHODS = ("post",)
    _STATE = "_data"
    _default = dict

    def __init__(self, path: str, ledger=None):
        # `_ledger` VOOR `super().__init__`: die roept `_load()` aan, en een verse store schrijft
        # dan meteen — wat via `post` bij het project-pad langs de ledger zou willen.
        self._ledger = ledger
        super().__init__(path)
        self._data.setdefault("kanalen", {})

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

    def laatste(self, kanaal: str) -> dict | None:
        rij = self.trail(kanaal, limit=1)
        return rij[-1] if rij else None
