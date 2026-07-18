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

import hashlib
import uuid


def _mint(text: str = "") -> str:
    """Het id van een accountability, AFGELEID uit zijn tekst.

    Deterministisch met opzet. Op prod laden de daemon én het cockpit-proces dezelfde
    records-file; met willekeurige uuid's zou elk proces zijn eigen ids munten, allebei
    opslaan, en zou de laatste schrijver winnen — koppelingen die naar de verliezende set
    wijzen zijn dan stil kapot. Een hash van de tekst geeft in elk proces hetzelfde id, dus
    de race is onschadelijk en de migratie is echt idempotent.

    Uniek hoeft alleen BINNEN een rol te zijn (elke query is `role` + `acc_id`), dus de
    tekst volstaat als bron. Zonder tekst (mag niet voorkomen) valt hij terug op een uuid.

    Nevengevolg, bewust: wordt een accountability verwijderd en later letterlijk opnieuw
    aangenomen, dan krijgt ze haar oude id terug — dezelfde belofte, dezelfde koppelingen.
    """
    if not text:
        return uuid.uuid4().hex[:12]
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


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
    # Bijmunten: ontbrekende of lege posities, afgeleid uit de tekst op die positie.
    while len(ids) < len(accs):
        ids.append(_mint(accs[len(ids)]))
        changed = True
    for i, v in enumerate(ids):
        if not v:
            ids[i] = _mint(accs[i])
            changed = True
    # Duplicaten opheffen: een id moet binnen de rol uniek zijn. Alleen hier is een uuid
    # nodig — twee identieke teksten geven per definitie dezelfde hash.
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


def is_herformulering(add: list[str], remove: list[str]) -> bool:
    """Is deze change een HERFORMULERING: dezelfde belofte, andere woorden?

    Governance kent geen 'bewerk' — een herformulering komt binnen als precies één remove plus
    precies één add binnen dezelfde rol. `governance.py` herkent die vorm al (de orphan-check
    op verweesd werk wordt er expliciet voor overgeslagen); wij laten er het acc_id op meereizen.
    """
    return len(remove or []) == 1 and len(add or []) == 1


def apply_accountability_change(defn, add: list[str], remove: list[str]) -> list[str]:
    """Pas een governance-wijziging toe op tekst én ids in lockstep.

    Zelfde semantiek als de oude losse regels in `_adopt` (toevoegen dedupliceert en sorteert,
    verwijderen filtert op letterlijke tekst) — maar het id reist met zijn tekst mee, zodat
    bestaande koppelingen aan dezelfde belofte blijven hangen na een herordening.

    Bij een HERFORMULERING (één remove + één add) erft de nieuwe tekst het id van de oude:
    het is dezelfde belofte in andere woorden, dus koppelingen horen mee te verhuizen.

    Geeft de acc_ids terug die door deze change VERDWIJNEN. De aanroeper kan daarmee
    waarschuwen dat er koppelingen wees raken — stil laten vallen is nooit goed genoeg.
    """
    ensure_acc_ids(defn)
    items = pairs(defn)
    voor = {i for (i, _) in items}

    # Herformulering: het id van de verwijderde tekst verhuist naar de nieuwe tekst.
    erft: str = ""
    if is_herformulering(add, remove):
        erft = next((i for (i, t) in items if t == remove[0]), "")

    if remove:
        drop = set(remove)
        items = [(i, t) for (i, t) in items if t not in drop]

    if add:
        have = {t for (_, t) in items}
        for t in add:
            if t not in have:
                items.append((erft or _mint(t), t))
                erft = ""                      # het geërfde id gaat maar naar één tekst
                have.add(t)
        # De adoptie sorteerde de teksten; het id reist mee.
        items.sort(key=lambda p: p[1])

    defn.accountabilities = [t for (_, t) in items]
    defn.accountability_ids = [i for (i, _) in items]
    return sorted(voor - set(defn.accountability_ids))
