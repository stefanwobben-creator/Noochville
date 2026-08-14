"""De samengestelde policy-stack voor de copy-prompt: erfenis + bewuste cross-rol-inclusies.

Waarom dit bestaat. De generator las één rol en wat die rol ERFT. Overerving loopt omhoog door de
cirkelketen, dus de policies van een ZUSTERROL bereikte hij nooit — en precies daar wonen ze: de
copy-governance (COPYCHECK/TONEOFVOICE/POSITIONSTAT) bij Community and Email, de merk-policies
(BRANDPOSITIO/DESIGNSYSTEM) bij Brand & Visual Designer. Wie als Copywriter schreef kreeg dus een
lege stack, en wie als Community and Email schreef kreeg wél de copyregels maar nooit het merk.

De oplossing is NIET de policies verhuizen. Eigendom is governance: de rol die het domein houdt,
cureert. De oplossing is een tweede, expliciete relatie naast erfenis:

    erfenis   = automatisch, volgt de cirkelketen omhoog, niemand kiest hem
    inclusie  = iemand heeft BESLOTEN dat deze bron meetelt voor deze schrijvende rol

Een inclusie is dus geen stiekeme tweede overervingsregel; hij staat in `data/copy_stack.json`,
draagt wie hem zette, en is zichtbaar in de UI als eigen laag. Dat verschil moet leesbaar blijven
tot in de prompt, anders leest een lezer een merkregel als iets wat de rol zelf bezit.

De laag van een ingesloten bron volgt zijn DOMEIN, niet zijn id — een id kan hernoemd worden, een
domein is governance. Zonder domein-match valt hij terug op een neutrale inclusie-laag met de naam
van de bronrol erin; nooit stilzwijgend op 'eigen'.
"""
from __future__ import annotations

import logging
import os
import time

from nooch_village.util import JsonStore

log = logging.getLogger("village.copy_stack")

BESTAND = "copy_stack.json"

# ── De lagen ────────────────────────────────────────────────────────────────
LAAG_KADER, LAAG_MERK, LAAG_STEM, LAAG_ROL, LAAG_OVERIG = (
    "kader", "merk", "stem", "rol", "overig")

LAAG_LABEL = {
    LAAG_KADER:  "Circle governance",
    LAAG_MERK:   "Brand voice (included)",
    LAAG_STEM:   "Copy governance (included)",
    LAAG_ROL:    "This role's policies",
    LAAG_OVERIG: "Included from another role",
}

# Welk domein maakt een bron tot merk- of copy-laag. Domein-namen, geen rol-ids: governance
# hernoemt rollen, maar een domein dragen is een besluit.
_DOMEIN_LAAG = {
    "brand positioning": LAAG_MERK,
    "design system":     LAAG_MERK,
    "copycheck":         LAAG_STEM,
    "tone of voice":     LAAG_STEM,
    "position statements": LAAG_STEM,
}

# Standaard aan/uit per laag. Alles staat aan: een inclusie is al een bewust besluit, dus hem
# vervolgens standaard uitzetten zou dat besluit meteen weer ontkennen. `kader` blijft uit —
# geldregels en WIP-limieten horen niet in een schrijfopdracht (dat was de bug in #311).
LAAG_DEFAULT = {LAAG_KADER: False, LAAG_MERK: True, LAAG_STEM: True,
                LAAG_ROL: True, LAAG_OVERIG: True}


def laag_van_domeinen(domeinen) -> str:
    """De laag die bij deze domeinen hoort, of LAAG_OVERIG. Case-insensitief."""
    for d in domeinen or []:
        laag = _DOMEIN_LAAG.get(str(d).strip().lower())
        if laag:
            return laag
    return LAAG_OVERIG


class StackConfig(JsonStore):
    """Wie telt mee voor wie. Klein, expliciet, mens-leesbaar op schijf.

    Op JsonStore omdat cockpit en daemon dezelfde map delen: zonder slot overschrijft de een de
    inclusie die de ander net zette (lost update), en dat merk je pas als een merkregel onverklaard
    uit een prompt verdwijnt."""

    _STATE = "_data"
    _WRITE_METHODS = ("zet",)

    def inclusies(self, rol: str) -> list[str]:
        return list((self._data.get(rol) or {}).get("inclusies") or [])

    def door(self, rol: str, bron: str) -> str:
        return str(((self._data.get(rol) or {}).get("door") or {}).get(bron) or "")

    def zet(self, rol: str, bron: str, aan: bool, *, door: str = "") -> bool:
        """Zet een inclusie aan of uit. Geeft True als er iets veranderde."""
        if not rol or not bron or rol == bron:
            return False
        entry = self._data.setdefault(rol, {"inclusies": [], "door": {}, "ts": time.time()})
        huidig = list(entry.get("inclusies") or [])
        if aan and bron not in huidig:
            huidig.append(bron)
            entry.setdefault("door", {})[bron] = door or "onbekend"
        elif not aan and bron in huidig:
            huidig.remove(bron)
            entry.get("door", {}).pop(bron, None)
        else:
            return False
        entry["inclusies"] = huidig
        entry["ts"] = time.time()
        self._save()
        log.info("copy-stack: %s %s inclusie %s (door %s)",
                 rol, "krijgt" if aan else "verliest", bron, door or "onbekend")
        return True

    def zaad(self, rol: str, bronnen: list[str], *, door: str = "system") -> int:
        """Zet inclusies eenmalig klaar. Idempotent, en raakt een bestaande keuze NIET aan: zodra
        een mens de compositie heeft aangeraakt is dat de waarheid, niet de zaad-lijst."""
        if rol in self._data:
            return 0
        n = sum(1 for b in bronnen if self.zet(rol, b, True, door=door))
        return n


# ── De compositie ───────────────────────────────────────────────────────────

def _own_policies(rol: str, records, att) -> list[dict]:
    """De EIGEN policies van een rol (niet wat hij erft) — dat is wat een inclusie meeneemt.
    Een ingesloten bron leent zijn eigen curatie uit, niet het kader waar hij zelf onder valt."""
    from nooch_village import artefacts
    ctx = artefacts.serialize_context(rol, records, att)
    return list((ctx.get("policies") or {}).get("own") or [])


def _naam(records, rol: str) -> str:
    rec = records.get(rol)
    if rec is None:
        return rol
    return getattr(rec.definition, "name", "") or getattr(rec, "id", rol)


def _domeinen(records, rol: str) -> list[str]:
    rec = records.get(rol)
    return list(getattr(rec.definition, "domains", None) or []) if rec is not None else []


def kandidaten(records, att, *, behalve: str = "") -> list[dict]:
    """Rollen die iets te lenen HEBBEN: eigen, actieve policies. De admin kiest hieruit; de lijst
    komt uit de organisatie, zodat er geen rol-id in de code hoeft te staan."""
    uit = []
    for rec in records.all():
        if getattr(rec, "archived", False) or rec.id == behalve:
            continue
        eigen = [p for p in att.list(rec.id, "policy")
                 if getattr(p, "status", "active") == "active"]
        if not eigen:
            continue
        dom = _domeinen(records, rec.id)
        uit.append({"id": rec.id, "naam": _naam(records, rec.id), "aantal": len(eigen),
                    "laag": laag_van_domeinen(dom), "domeinen": dom})
    uit.sort(key=lambda r: (r["laag"], r["naam"]))
    return uit


def uit_context(ctx: dict, *, uit: set | None = None) -> list[dict]:
    """Stack-items uit een kale rol-context, zonder inclusies.

    Voor aanroepers die alleen een `serialize_context`-dict hebben (de prompt-bouwer in tests, het
    /context-pad). Zonder records is er niets te classificeren, dus valt alles in de rol-laag en
    staat alles aan: liever alles tonen dan stilletjes een laag wegfilteren op een aanname."""
    uit = uit or set()
    blok = ctx.get("policies") or {}
    items = []
    for a in blok.get("inherited") or []:
        items.append({**a, "laag": LAAG_ROL, "bron": "erfenis",
                      "herkomst": a.get("origin_path") or "", "aan": a.get("id") not in uit})
    for a in blok.get("own") or []:
        items.append({**a, "laag": LAAG_ROL, "bron": "eigen", "herkomst": "",
                      "aan": a.get("id") not in uit})
    return items


def componeer(rol: str, records, att, config: StackConfig, *, uit: set | None = None) -> list[dict]:
    """De volle stack voor één schrijvende rol: erfenis + eigen + bewuste inclusies.

    Elk item draagt `bron` ∈ {erfenis, eigen, inclusie} zodat de UI én de prompt kunnen laten zien
    waar een regel vandaan komt. Dedup op policy-id: erft een rol iets dat ook via een inclusie
    binnenkomt, dan telt hij één keer — met de eerst gevonden herkomst."""
    from nooch_village import artefacts, org

    uit = uit or set()
    ctx = artefacts.serialize_context(rol, records, att)
    blok = ctx.get("policies") or {}

    try:
        keten = org.breadcrumb(records.all(), rol)
        wortel = keten[0] if keten else ""
    except Exception:                                     # noqa: BLE001 — weergave mag nooit breken
        wortel = ""

    items: list[dict] = []
    gezien: set[str] = set()

    def _voeg_toe(a: dict, laag: str, bron: str, herkomst: str) -> None:
        pid = a.get("id") or ""
        if pid in gezien:
            return
        gezien.add(pid)
        items.append({**a, "laag": laag, "bron": bron, "herkomst": herkomst,
                      "aan": LAAG_DEFAULT.get(laag, True) and pid not in uit})

    # 1. Erfenis: het kader van de cirkels waar deze rol onder hangt.
    for a in blok.get("inherited") or []:
        # Alles wat je ERFT komt uit de cirkelketen boven je: dat is per definitie kader. Merk- en
        # copy-lagen kunnen hier niet ontstaan — die wonen bij zusterrollen en komen via inclusie.
        herkomst_id = a.get("origin_id") or ""
        _voeg_toe(a, LAAG_KADER, "erfenis",
                  a.get("origin_path") or _naam(records, herkomst_id) or wortel)

    # 2. Eigen policies van de schrijvende rol.
    for a in blok.get("own") or []:
        _voeg_toe(a, LAAG_ROL, "eigen", "")

    # 3. Bewuste inclusies — de laag volgt het domein van de BRON.
    for bron_id in config.inclusies(rol):
        if records.get(bron_id) is None:
            log.warning("copy-stack: inclusie '%s' bestaat niet meer (rol %s)", bron_id, rol)
            continue
        laag = laag_van_domeinen(_domeinen(records, bron_id))
        naam = _naam(records, bron_id)
        for a in _own_policies(bron_id, records, att):
            _voeg_toe(a, laag, "inclusie", naam)

    volgorde = [LAAG_ROL, LAAG_STEM, LAAG_MERK, LAAG_OVERIG, LAAG_KADER]
    items.sort(key=lambda i: volgorde.index(i["laag"]) if i["laag"] in volgorde else 99)
    return items
