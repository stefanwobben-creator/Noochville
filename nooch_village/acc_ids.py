"""Stabiele ids voor accountabilities.

Een accountability is tekst in het rol-record. Koppelingen (AI-taken, skill-links) verwezen
tot nu toe naar de *index* van die tekst binnen de rol — en die index verschuift zodra
governance een accountability toevoegt (de adoptie sorteert de lijst) of verwijdert. Dan wijst
een bestaande koppeling stilletjes naar de verkeerde belofte.

Daarom draagt elke accountability een stabiel id. Opslag: `RoleDefinition.accountability_ids`,
positioneel parallel aan `RoleDefinition.accountabilities`. Governance houdt beide lijsten in
lockstep (zie `governance.py::_adopt`); koppelingen verwijzen alleen nog naar het id.

Fail-soft: een record zonder (of met een te korte/lange) id-lijst krijgt bij de eerste load
ontbrekende ids bijgemunt. De migratie is idempotent — een tweede load muteert niets.
"""
from __future__ import annotations

import uuid


def _mint() -> str:
    return uuid.uuid4().hex[:12]


def ensure_acc_ids(defn) -> bool:
    """Zorg dat `defn.accountability_ids` even lang is als `defn.accountabilities`.

    Ontbrekende ids worden bijgemunt, overtollige afgekapt. Geeft True als er iets veranderde
    (de aanroeper weet dan dat hij moet opslaan). Fail-soft: een definitie zonder de velden
    laat de functie ongemoeid.
    """
    accs = getattr(defn, "accountabilities", None)
    if accs is None or not hasattr(defn, "accountability_ids"):
        return False
    ids = list(defn.accountability_ids or [])
    changed = False

    # Afkappen (meer ids dan teksten) — kan alleen door handmatige edits ontstaan.
    if len(ids) > len(accs):
        ids = ids[: len(accs)]
        changed = True
    # Bijmunten: ontbrekende of lege posities.
    while len(ids) < len(accs):
        ids.append(_mint())
        changed = True
    for i, v in enumerate(ids):
        if not v:
            ids[i] = _mint()
            changed = True
    # Duplicaten opheffen: een id moet binnen de rol uniek zijn.
    seen: set[str] = set()
    for i, v in enumerate(ids):
        if v in seen:
            ids[i] = _mint()
            changed = True
        seen.add(ids[i])

    if changed:
        defn.accountability_ids = ids
    return changed


def acc_id_at(defn, index: int) -> str:
    """Het stabiele id van de accountability op deze positie ("" als de positie niet bestaat)."""
    ensure_acc_ids(defn)
    ids = getattr(defn, "accountability_ids", None) or []
    if 0 <= index < len(ids):
        return ids[index]
    return ""


def index_of(defn, acc_id: str) -> int:
    """Positie van dit id binnen de rol, of -1 als het er niet (meer) is."""
    if not acc_id:
        return -1
    ids = getattr(defn, "accountability_ids", None) or []
    try:
        return ids.index(acc_id)
    except ValueError:
        return -1


def text_for(defn, acc_id: str) -> str:
    """De accountability-tekst achter dit id ("" als het id niet meer bestaat)."""
    i = index_of(defn, acc_id)
    accs = getattr(defn, "accountabilities", None) or []
    return accs[i] if 0 <= i < len(accs) else ""


def pairs(defn) -> list[tuple[str, str]]:
    """[(acc_id, tekst), …] in recordvolgorde."""
    ensure_acc_ids(defn)
    ids = getattr(defn, "accountability_ids", None) or []
    accs = getattr(defn, "accountabilities", None) or []
    return list(zip(ids, accs))


def apply_accountability_change(defn, add: list[str], remove: list[str]) -> None:
    """Pas een governance-wijziging toe op tekst én ids in lockstep.

    Zelfde semantiek als de oude losse regels in `_adopt` (toevoegen dedupliceert en sorteert,
    verwijderen filtert op letterlijke tekst) — maar het id reist met zijn tekst mee, zodat
    bestaande koppelingen aan dezelfde belofte blijven hangen na een herordening.
    """
    ensure_acc_ids(defn)
    items = pairs(defn)

    if remove:
        drop = set(remove)
        items = [(i, t) for (i, t) in items if t not in drop]

    if add:
        have = {t for (_, t) in items}
        for t in add:
            if t not in have:
                items.append((_mint(), t))
                have.add(t)
        # De adoptie sorteerde de teksten; het id reist mee.
        items.sort(key=lambda p: p[1])

    defn.accountabilities = [t for (_, t) in items]
    defn.accountability_ids = [i for (i, _) in items]
