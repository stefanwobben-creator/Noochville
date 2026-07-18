"""De laatste regels uit de audit-trail, zonder het hele bestand te lezen.

`data/system_log.jsonl` is op productie ruim 200 MB. Een naïeve `for line in open(...)` om de
laatste tien regels te vinden leest dat allemaal in — per paginaweergave. Daarom leest deze
module van achteren: blokken vanaf het einde, tot er genoeg regels zijn.

Wat deze module NIET doet, en waarom dat expliciet is: doen alsof er tijdstempels zijn. Alleen
de twee cockpit-schrijvers zetten een `at`; de bus-events (verreweg het meeste volume) niet.
"Laatste tien" betekent hier dus laatste tien in bestandsvolgorde. Dat is eerlijk en bruikbaar;
een verzonnen tijd zou dat niet zijn.
"""
from __future__ import annotations

import json
import os

BLOK = 64 * 1024

# Events waarvan we weten waar ze heen wijzen. De rest krijgt geen link in plaats van een
# link die nergens op uitkomt.
_LINKVELDEN = ("role_id", "by")


def lees_staart(pad: str, max_regels: int = 4000) -> list[str]:
    """De laatste `max_regels` regels van een bestand, van achteren gelezen."""
    try:
        grootte = os.path.getsize(pad)
    except OSError:
        return []
    regels: list[str] = []
    with open(pad, "rb") as f:
        pos = grootte
        rest = b""
        while pos > 0 and len(regels) <= max_regels:
            stap = min(BLOK, pos)
            pos -= stap
            f.seek(pos)
            blok = f.read(stap) + rest
            stukken = blok.split(b"\n")
            rest = stukken.pop(0)               # mogelijk half; bewaren voor het volgende blok
            regels = [s.decode("utf-8", "replace") for s in stukken if s.strip()] + regels
        if rest.strip() and len(regels) <= max_regels:
            regels = [rest.decode("utf-8", "replace")] + regels
    return regels[-max_regels:]


def laatste_events(data_dir: str, rol_ids: set[str], aantal: int = 10) -> list[dict]:
    """De laatste gebeurtenissen van deze rollen, nieuwste eerst.

    Filtert op `by` (de rol die handelde) en `role_id` (de rol waar het over ging), want
    governance-events noemen de betrokken rol in dat tweede veld."""
    if not rol_ids:
        return []
    pad = os.path.join(data_dir, "system_log.jsonl")
    uit: list[dict] = []
    for regel in reversed(lees_staart(pad)):
        try:
            rij = json.loads(regel)
        except ValueError:
            continue
        door = rij.get("by") or ""
        over = rij.get("role_id") or ""
        if door not in rol_ids and over not in rol_ids:
            continue
        link = over if over else (door if door in rol_ids else "")
        uit.append({
            "rol": (door or over).split("__")[-1],
            "event": rij.get("event", "?"),
            "link": link,
            "link_label": link.split("__")[-1] if link else "",
            "detail": _detail(rij),
        })
        if len(uit) >= aantal:
            break
    return uit


def _detail(rij: dict) -> str:
    """Het meest zeggende veld dat deze regel heeft, zonder te gokken."""
    for sleutel in ("boodschap", "title", "description", "term", "word", "reason", "classification"):
        waarde = rij.get(sleutel)
        if waarde:
            return str(waarde)[:80]
    return ""
