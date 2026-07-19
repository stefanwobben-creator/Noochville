"""Wekelijkse tag-onderhoudslus — de Library houdt de taglijst schoon (founder, 19 jul).

Tags zijn dé taal van Oracle (de onderwerpen-chips zijn al vervangen door de A–Z-taglijst).
Maar een taglijst die alleen groeit wordt ruis: synoniemen ("vegan-leer"/"veganleer"),
wegwerp-tags met één vondst, en micro-tags die samen één bruikbare abstractie zouden zijn.
Deze lus laat de LLM daar wekelijks VOORSTELLEN voor doen; een mens keurt ze op
/kennisbank/tags, en pas dán worden alle betrokken kaartjes bijgewerkt (NotesStore.retag).

Ontwerp:
- Mens-gated: de lus schrijft alleen voorstellen (TagVoorstellenStore), nooit direct tags.
- Beschermd: het vaste onderwerp-vocabulaire (SUBJECTS — dragend voor hubs/clusters zolang
  fase 3 niet gedraaid is), de functionele tags (signal, flags) en hint:*-tags worden nooit
  als bron voorgesteld; SUBJECTS mag wél het doel van een merge zijn.
- Fail-closed: geen LLM → geen voorstellen; onparseerbaar → leeg.
- Idempotent: een voorstel dat (zelfde van→naar) al open staat of eerder is afgewezen wordt
  niet opnieuw opgevoerd; de wekelijkse marker voorkomt dubbele runs binnen 7 dagen.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta

from nooch_village.kennisbank_intake import INTAKE_LADDER, SUBJECTS, FLAG_VERIFICATIE
from nooch_village.llm import reason
from nooch_village.notes_store import NotesStore
from nooch_village.util import JsonStore

# Nooit als bron van een merge/weg/abstractie: dragend of functioneel.
BESCHERMD = frozenset(SUBJECTS) | {"signal", FLAG_VERIFICATIE, "quote", "contested"}

_MAX_VOORSTELLEN = 15
INTERVAL_DAGEN = 7


def tag_telling(notes: NotesStore) -> dict[str, int]:
    """Alle tags met aantallen over de niet-verwijderde kaartjes; hint:*-tags niet."""
    tel: dict[str, int] = {}
    for a in notes.all():
        if a.archived:
            continue
        for t in a.tags or []:
            if t.startswith("hint:"):
                continue
            tel[t] = tel.get(t, 0) + 1
    return tel


def build_tag_prompt(telling: dict[str, int]) -> str:
    vrij = {t: n for t, n in telling.items() if t not in BESCHERMD}
    regels = "\n".join(f"- {t} ({n})" for t, n in sorted(vrij.items(),
                                                         key=lambda kv: kv[0].lower()))
    vast = ", ".join(sorted(BESCHERMD & set(telling)))
    return (
        "Je bent de bibliothecaris van een kennisbank en houdt de TAGLIJST schoon. Hieronder\n"
        "alle vrije tags met hun aantal vondsten. Stel onderhoud voor, drie soorten acties:\n"
        "- \"merge\": twee of meer tags zijn hetzelfde begrip (spelling/synoniem) → één tag.\n"
        "  \"naar\" mag een bestaande tag zijn (ook een beschermde) of een betere spelling.\n"
        "- \"weg\": een tag voegt niets toe (te specifiek, eenmalig, betekenisloos).\n"
        "- \"abstractie\": meerdere micro-tags zijn samen één bruikbaar begrip → één nieuwe\n"
        "  overkoepelende tag.\n"
        "Wees terughoudend: alleen voorstellen waar je zeker van bent, MAXIMAAL "
        f"{_MAX_VOORSTELLEN}. Geef per voorstel één korte motivatie.\n"
        f"BESCHERMDE tags (nooit als bron opvoeren): {vast or '-'}\n\n"
        f"VRIJE TAGS:\n{regels or '- (geen)'}\n\n"
        "OUTPUT: ALLEEN een JSON-array, geen proza, geen code-fences:\n"
        '[ { "actie": "merge|weg|abstractie", "van": ["tag", ...], '
        '"naar": "<doeltag of leeg bij weg>", "waarom": "<kort>" } ]')


def parse_tag_voorstellen(text: str | None, telling: dict[str, int]) -> list[dict]:
    """LLM-output → gevalideerde voorstellen. Fail-closed: onparseerbaar → []; bron-tags
    moeten bestaan en onbeschermd zijn; merge/abstractie vereist een niet-lege doeltag."""
    if not text:
        return []
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end < start:
        return []
    try:
        rows = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return []
    uit: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        actie = str(r.get("actie") or "").strip().lower()
        if actie not in ("merge", "weg", "abstractie"):
            continue
        van = [str(t).strip().lower() for t in (r.get("van") or []) if str(t).strip()]
        van = [t for t in van if t in telling and t not in BESCHERMD]
        naar = str(r.get("naar") or "").strip().lower()
        if not van:
            continue
        if actie == "weg":
            naar = ""
        elif not naar or naar in van:
            continue
        uit.append({"actie": actie, "van": sorted(set(van)), "naar": naar,
                    "waarom": str(r.get("waarom") or "").strip()[:200]})
    return uit[:_MAX_VOORSTELLEN]


class TagVoorstellenStore(JsonStore):
    """{"voorstellen": {vid: {...status open|doorgevoerd|afgewezen}}, "last_run": iso}."""

    _WRITE_METHODS = ("voeg_toe", "besluit", "stempel_run")

    def open_voorstellen(self) -> list[dict]:
        vs = self._items.get("voorstellen") or {}
        return sorted((v for v in vs.values() if v.get("status") == "open"),
                      key=lambda v: v.get("at") or "")

    def _sleutel(self, v: dict) -> str:
        return f"{v['actie']}|{','.join(v['van'])}|{v['naar']}"

    def voeg_toe(self, voorstellen: list[dict]) -> int:
        """Nieuwe voorstellen opnemen; dubbelen t.o.v. ALLE bestaande (ook afgewezen —
        een afgewezen voorstel komt niet elke week terug) worden overgeslagen."""
        vs = self._items.setdefault("voorstellen", {})
        bekend = {self._sleutel(v) for v in vs.values()}
        n = 0
        for v in voorstellen:
            if self._sleutel(v) in bekend:
                continue
            vid = "tv_" + uuid.uuid4().hex[:8]
            vs[vid] = {**v, "id": vid, "status": "open",
                       "at": datetime.now().isoformat(timespec="seconds")}
            bekend.add(self._sleutel(v))
            n += 1
        if n:
            self._save()
        return n

    def besluit(self, vid: str, status: str) -> dict | None:
        v = (self._items.get("voorstellen") or {}).get(vid)
        if v is None or v.get("status") != "open" or status not in ("doorgevoerd", "afgewezen"):
            return None
        v["status"] = status
        v["besloten_at"] = datetime.now().isoformat(timespec="seconds")
        self._save()
        return v

    def stempel_run(self) -> None:
        self._items["last_run"] = datetime.now().isoformat(timespec="seconds")
        self._save()

    def week_voorbij(self) -> bool:
        laatst = self._items.get("last_run")
        if not laatst:
            return True
        try:
            return datetime.now() - datetime.fromisoformat(laatst) >= timedelta(days=INTERVAL_DAGEN)
        except ValueError:
            return True


def draai_onderhoud(data_dir: str, *, reason_fn=None, force: bool = False,
                    dry_run: bool = False) -> dict:
    """De lus: telling → LLM-voorstellen → store (mens keurt op /kennisbank/tags).
    Respecteert de week-marker tenzij force. Geeft {"gedraaid", "voorstellen", "nieuw"}."""
    store = TagVoorstellenStore(f"{data_dir}/tag_voorstellen.json")
    if not force and not store.week_voorbij():
        return {"gedraaid": False, "voorstellen": 0, "nieuw": 0}
    notes = NotesStore(f"{data_dir}/notes.json")
    telling = tag_telling(notes)
    if not telling:
        return {"gedraaid": False, "voorstellen": 0, "nieuw": 0}
    fn = reason_fn or (lambda p: reason(p, ladder=INTAKE_LADDER, call_site="tag_onderhoud"))
    uit = parse_tag_voorstellen(fn(build_tag_prompt(telling)), telling)
    if dry_run:
        return {"gedraaid": True, "voorstellen": len(uit), "nieuw": 0, "dry": uit}
    nieuw = store.voeg_toe(uit)
    if uit or store.week_voorbij():
        store.stempel_run()
    return {"gedraaid": True, "voorstellen": len(uit), "nieuw": nieuw}


def voer_voorstel_uit(notes: NotesStore, v: dict) -> int:
    """Een GOEDGEKEURD voorstel doorvoeren op alle kaartjes. Geeft het aantal bijgewerkte
    kaartjes. merge/abstractie: elke van-tag wordt naar; weg: van-tags verdwijnen."""
    n = 0
    doel = v.get("naar") or None
    for t in v.get("van") or []:
        n += notes.retag(t, doel)
    return n
