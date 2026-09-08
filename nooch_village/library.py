from __future__ import annotations
from datetime import datetime
from nooch_village.util import JsonStore

# Een goedgekeurd woord heeft een FUNCTIE in de ontdekkingslus:
#   "volg"    = seed: te breed om op te ranken, maar voedt de radar (Trends/SerpAPI/ngram)
#   "doelwit" = rank-target: specifiek, intentie, hier maken we content voor en willen we ranken
_HEAD_VOLUME = 100000   # mega-breed zoekvolume → bijna altijd een seed, geen rank-doel


def classify_function(word: str, evidence: dict | None = None) -> str:
    """Heuristiek voor de functie van een woord. Mega-volume of één generiek woord → 'volg';
    specifiek meerwoord → 'doelwit'. De mens corrigeert uitzonderingen (set_function)."""
    vol = (evidence or {}).get("volume")
    if vol is not None and vol >= _HEAD_VOLUME:
        return "volg"
    if len((word or "").split()) <= 1:
        return "volg"
    return "doelwit"


class Library(JsonStore):
    """De woordenschat-bibliotheek: een DOMEIN dat de Librarian beheert.
    Lezen is vrij voor iedereen; cureren (schrijven) is voorbehouden aan de Librarian.
    Een entry draagt niet alleen een oordeel maar ook het WAAROM (het is een ontologie,
    geen blocklist).

    HET DOMEIN HEEFT TWEE SCHRIJVERS, en dat is de reden voor `JsonStore`. De Librarian
    cureert vanuit de daemon; het cockpit cureert via de woordenschat-knoppen. Beide
    schreven het hele bestand terug vanuit hun eigen geheugenkopie, dus een curatie op het
    scherm verdween bij de eerstvolgende Librarian-beslissing. De guard-test noemde deze
    store nog "single-writer: alleen de Librarian-daemon"; dat klopte niet meer.

    Domein-eigenaarschap en concurrency zijn twee verschillende dingen: dat alléén de
    Librarian MAG cureren maakt niet dat er maar één proces schrijft."""

    _STATE = "_data"
    _WRITE_METHODS = ("curate", "set_function", "set_evidence", "link_concept")

    # --- lezen (vrij) ---
    def status(self, word: str) -> dict | None:
        return self._data.get(word.lower())

    def is_forbidden(self, word: str) -> bool:
        e = self.status(word)
        return bool(e and e["status"] in ("forbidden", "avoid"))

    def is_approved(self, word: str) -> bool:
        e = self.status(word)
        return bool(e and e["status"] == "approved")

    def all(self) -> dict:
        return self._data

    def function_of(self, word: str) -> str:
        """Functie van een woord: 'volg' of 'doelwit'. Mens-override wint; anders heuristiek."""
        e = self._data.get(word.lower())
        if e is None:
            return classify_function(word, None)
        fn = e.get("function")
        return fn if fn in ("volg", "doelwit") else classify_function(word, e.get("evidence"))

    # --- cureren (alleen de Librarian hoort dit aan te roepen) ---
    def curate(self, word: str, status: str, rationale: str = "",
               evidence: dict | None = None, by: str = "Librarian") -> dict:
        existing = self._data.get(word.lower(), {})
        entry = {**existing,
                 "status": status,            # approved | forbidden | avoid | escalated
                 "rationale": rationale,
                 "evidence": evidence or {},
                 "by": by,
                 "date": datetime.now().strftime("%Y-%m-%d")}
        if not existing:
            # Echt nieuw woord: leg het geboortemoment vast. De woordenschat toont hierop
            # 28 dagen een ster (nieuw-markering); her-curatie verplaatst dit moment nooit.
            entry["first_seen"] = entry["date"]
        # Functie (volg/doelwit) alleen voor approved; een eerdere mens-override blijft staan.
        if status == "approved" and entry.get("function") not in ("volg", "doelwit"):
            entry["function"] = classify_function(word, entry.get("evidence"))
        self._data[word.lower()] = entry
        self._save()
        return entry

    def set_function(self, word: str, function: str) -> dict | None:
        """Mens-override van de functie (cockpit-knop). Raakt status/datum/evidence niet."""
        if function not in ("volg", "doelwit"):
            raise ValueError(f"functie moet 'volg' of 'doelwit' zijn, niet {function!r}")
        key = word.lower()
        entry = self._data.get(key)
        if entry is None:
            return None
        entry["function"] = function
        self._save()
        return entry

    def set_evidence(self, word: str, updates: dict) -> dict | None:
        """Verrijk de evidence van een bestaand woord (merge), zonder status/datum/rationale
        te raken. Bedoeld voor verrijking achteraf (bv. KE-volume/concurrentie/kans toevoegen
        aan al goedgekeurde woorden). Retourneert het bijgewerkte entry, of None als onbekend."""
        key = word.lower()
        entry = self._data.get(key)
        if entry is None:
            return None
        entry["evidence"] = {**(entry.get("evidence") or {}), **(updates or {})}
        self._save()
        return entry

    def link_concept(self, word: str, concept_id: str) -> dict:
        key = word.lower()
        if key not in self._data:
            raise KeyError(f"Woord '{word}' staat niet in de bibliotheek")
        self._data[key]["concept_id"] = concept_id
        self._save()
        return self._data[key]

    def keywords_for_concept(self, concept_id: str) -> list[str]:
        return [
            word for word, entry in self._data.items()
            if entry.get("concept_id") == concept_id
        ]
