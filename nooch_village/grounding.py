"""Grondings-poort (De Kroniek fase 1): toetst een mens-gerichte tekst tegen de bron-data, zodat een
LLM-duiding geen cijfers of datums verzint die niet uit de data volgen. Fase 1 dekt de FIELD NOTE — de
scherpste pijnplek (de '22 mei 2024 / 12 bezoekers'-drift van 12 juli 2026).

Twee false-positive-arme checks:
  1. datum-drift — een volledige 'dag maand jaar'-datum in de tekst met een ander jaar dan de puls.
  2. ongegrond bezoekers-getal — een 'N bezoekers'-claim waarvan N NERGENS in de plausible-data voorkomt.
     (Per-pagina/-bron/-land-aantallen zijn wél gegrond: die staan als waarde in de data. Alleen een
     verzonnen getal — dat in de hele bron niet bestaat — wordt gemarkeerd.)

`ground_field_note` geeft een lijst ongegronde bevindingen terug (leeg = alles gegrond). De caller
markeert de tekst i.p.v. 'm schoon te publiceren, en logt de uitkomst in de Kroniek.
"""
from __future__ import annotations

import re

_MONTHS = r"(?:jan|feb|maart|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)"
_DATE_RE = re.compile(rf"\b\d{{1,2}}\s+{_MONTHS}\w*\s+(\d{{4}})\b", re.IGNORECASE)
# getal direct vóór 'bezoekers' — alleen spaties/tabs ertussen (géén newline: anders bindt een getal
# uit bv. de datumkop '2026-07-12' aan het kopwoord 'Bezoekers' twee regels verder).
_VIS_RE = re.compile(r"\b(\d[\d.]*)[ \t ]{0,2}bezoekers\b", re.IGNORECASE)


def _to_int(s: str):
    try:
        return int(re.sub(r"[.\s]", "", s))
    except (TypeError, ValueError):
        return None


def _all_numbers(obj) -> set[int]:
    """Alle gehele getallen die ergens (recursief) in de bron-data voorkomen — de 'gegronde' waarden.
    Getallen in strings tellen mee (Plausible levert waarden soms als string)."""
    out: set[int] = set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
        elif isinstance(x, bool):
            return                                   # bool is een int-subtype; niet meetellen
        elif isinstance(x, int):
            out.add(x)
        elif isinstance(x, float):
            if x == int(x):
                out.add(int(x))
        elif isinstance(x, str):
            for tok in re.findall(r"\d+", x):
                out.add(int(tok))

    walk(obj)
    return out


def ground_field_note(body: str, plausible: dict, today: str) -> list[str]:
    """Toets de field-note-body tegen de plausible-data + de pulsdatum. Geeft ongegronde bevindingen."""
    issues: list[str] = []
    body = body or ""
    year = (today or "")[:4]

    # 1) datum-drift
    for m in _DATE_RE.finditer(body):
        if year and m.group(1) != year:
            issues.append(f"datum-drift: tekst noemt {m.group(0)!r} maar de puls is van {today}")

    # 2) ongegrond bezoekers-getal
    grounded = _all_numbers(plausible or {})
    for m in _VIS_RE.finditer(body):
        n = _to_int(m.group(1))
        if n is not None and n not in grounded:
            issues.append(f"ongegrond getal: tekst noemt {n} bezoekers, dat komt nergens in de plausible-data voor")
    return issues
