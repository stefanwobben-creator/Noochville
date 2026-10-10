"""Het opbrengstregister — handmatige omzet en subsidie, Finance PR 1b (10 oktober 2026).

Besluit Stefan: eerst het systeem werkend zien, daarna koppelen. Tot Shopify gekoppeld is, komt
Net sales hier met de hand in, ook met terugwerkende kracht: de PERIODE is een veld, los van de
invoerdatum. Voer omzet in op de periode van LEVERING, zoals Venema hem erkent.

Zelfde borging als het kostenregister (`finance_register._Register`): alleen toevoegen
(`data/finance/revenue.jsonl`), centen, btw bewaard maar nooit geteld, bijlagen met sha256 en
downloadlog, correctie = tegenboeking + nieuwe regel. Een tegenboeking draait ook het aantal PAREN
om, zodat "per paar" netto klopt.

Twee opbrengstregels (`config/finance.json` → `revenue_lines`):
* `net_sales` — de basis van alle percentages en marges. Mag een batch en een aantal paren dragen.
  Negatief alleen voor een retour of creditnota, met verplichte notitie.
* `other_income_grants` — subsidies. Niet in Net sales, niet in de percentagebasis, niet in CM1–CM3;
  wél vanaf de laag in `from_layer` (standaard EBITDA). Die plek is een instelling, want Venema boekt
  een subsidie mogelijk anders.

`net_sales_source_from` (YYYY-MM of leeg): vanaf die maand komt Net sales uit een andere bron
(Shopify, later); daarvoor uit dit register. Nooit allebei voor dezelfde maand
(`net_sales_per_maand`). De Shopify-koppeling zelf is er nog NIET.
"""
from __future__ import annotations

import time

from nooch_village.finance_register import (BETAALSTATUS, _PERIODE, _Register, _datum, _tekst,  # noqa: F401
                                            centen)

NET_SALES = "net_sales"
BRON_HANDMATIG = "manual"


class OpbrengstRegister(_Register):
    """`data/finance/revenue.jsonl`. Alleen toevoegen — zie `_Register`."""

    BESTAND = "revenue.jsonl"
    BEDRAGEN = ("amount_excl_cents", "vat_cents", "pairs")


def regels(cfg: dict) -> list[dict]:
    return list(cfg.get("revenue_lines") or [])


def regel(key: str, cfg: dict) -> dict | None:
    return next((r for r in regels(cfg) if r["key"] == key), None)


def maak_opbrengst(v: dict, cfg: dict, *, correctie: bool = False) -> tuple[dict | None, str, str]:
    """(regel, "", waarschuwing) of (None, reden, ""). Een periode in de toekomst is een
    WAARSCHUWING, geen blokkade (een vooruitbetaalde subsidie bestaat)."""
    datum = _datum(v.get("entry_date"))
    if not datum:
        return None, "a booking date (YYYY-MM-DD) is required", ""
    periode = str(v.get("period") or "").strip() or datum[:7]
    if not _PERIODE.match(periode):
        return None, "the period must be YYYY-MM", ""
    lijn = regel(str(v.get("revenue_line") or ""), cfg)
    if lijn is None:
        return None, "pick a revenue line", ""
    omschrijving = _tekst(v.get("description"))
    if not omschrijving:
        return None, "a description is required", ""
    bedrag = centen(v.get("amount_excl"))
    btw = centen(v.get("vat")) if str(v.get("vat") or "").strip() else 0
    if bedrag is None or btw is None:
        return None, "amounts must be numbers (euros)", ""
    notitie = _tekst(v.get("note"), 500)
    if (bedrag < 0 or btw < 0) and not correctie:
        if lijn["key"] != NET_SALES:
            return None, "negative amounts are only allowed on net sales (a return or credit note)", ""
        if not notitie:
            return None, "a negative net-sales line (return or credit note) needs a note", ""
    paren = None
    if str(v.get("pairs") or "").strip():
        try:
            paren = int(str(v["pairs"]).strip())
        except ValueError:
            return None, "pairs must be a whole number", ""
        if lijn["key"] != NET_SALES:
            return None, "pairs only belong on net sales", ""
    bijlage = v.get("attachment") if isinstance(v.get("attachment"), dict) else None
    waarschuwing = ("the period is in the future — saved anyway"
                    if periode > time.strftime("%Y-%m") else "")
    return {"entry_date": datum, "period": periode, "revenue_line": lijn["key"],
            "description": omschrijving, "amount_excl_cents": bedrag, "vat_cents": btw,
            "currency": _tekst(v.get("currency"), 3).upper() or "EUR",
            "batch": _tekst(v.get("batch"), 60), "pairs": paren, "attachment": bijlage,
            "note": notitie, "corrects": _tekst(v.get("corrects"), 40), "source": BRON_HANDMATIG}, "", waarschuwing


def posten(regels_: list[dict]) -> list[tuple[str, str, int, str]]:
    """De opbrengsten als posten: (maand, opbrengstregel, centen, bron)."""
    return [(r["period"], r["revenue_line"], int(r["amount_excl_cents"]), r.get("source") or BRON_HANDMATIG)
            for r in regels_]


def paren_per_maand(regels_: list[dict]) -> dict[str, int]:
    """Netto paren per maand (alleen net sales; een tegenboeking telt negatief)."""
    uit: dict[str, int] = {}
    for r in regels_:
        if r.get("revenue_line") == NET_SALES and isinstance(r.get("pairs"), int):
            uit[r["period"]] = uit.get(r["period"], 0) + r["pairs"]
    return uit


def net_sales_per_maand(opbrengsten: list[tuple], vanaf: str = "",
                        andere_bron: str = "shopify") -> tuple[dict[str, int], dict[str, str]]:
    """({maand: centen}, {maand: bron}) voor Net sales, met de bronregel: vóór `vanaf` alleen het
    register (handmatig), vanaf `vanaf` alleen de andere bron. Leeg `vanaf` = alles uit het
    register. Een maand komt NOOIT uit twee bronnen — wat er uit de andere bron in een registermaand
    staat (of andersom) telt niet mee."""
    som: dict[str, int] = {}
    bron: dict[str, str] = {}
    for maand, lijn, cents, b in opbrengsten:
        if lijn != NET_SALES:
            continue
        verwacht = andere_bron if (vanaf and maand >= vanaf) else BRON_HANDMATIG
        if b != verwacht:
            continue
        som[maand] = som.get(maand, 0) + int(cents)
        bron[maand] = b
    return som, bron
