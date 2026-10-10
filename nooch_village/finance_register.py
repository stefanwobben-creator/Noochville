"""Het kostenregister — managementadministratie, Finance PR 1 (10 oktober 2026).

GEEN BOEKHOUDING. Venema blijft leidend (btw, vennootschapsbelasting, jaarrekening; Dutch GAAP, RJ).
Dit is een register van kostenregels met een PDF, een Venema-rekening en een managementregel, voor
eigen inzicht (marge-lagen, later budget en afstemming).

DRIE REGELS DIE JE NIET MAG OMDRAAIEN:
1. ALLEEN TOEVOEGEN. `data/finance/costs.jsonl` krijgt regels erbij en verliest er nooit een. Deze
   module heeft GEEN methode die een regel wijzigt of verwijdert — ook niet intern. Een fout wordt
   een correctie: een tegenboeking (omgekeerde bedragen, `corrects` = de oude regel) plus een nieuwe,
   juiste regel (`correctie`).
2. CENTEN, GEEN FLOATS. Elk bedrag is een integer in centen; euro's worden via `Decimal` omgezet.
3. BTW TELT NOOIT MEE. `vat_cents` wordt bewaard voor de afstemming met Venema, maar geen totaal,
   filter of P&L leest hem.

DE BIJLAGE IS BORGING. Elk bestand staat buiten git en buiten de webroot (`data/finance/attachments/
<jaar>/<uuid>.<ext>`), met zijn sha256 in de regel. Bij elke download wordt de hash opnieuw berekend;
klopt hij niet, dan is dat een fout, geen stille levering. Wie downloadt staat in `downloads.jsonl`.

FINANCE-DATA BLIJFT HIER. Geen LLM-context, geen Noochie-memo, geen radar, geen zoekindex. Een
guard-test (`tests/test_finance_pr1.py`) faalt zodra een andere module dit register leest.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import time
import uuid
from decimal import Decimal, InvalidOperation

MAP = "finance"
BETAALSTATUS = ("open", "paid")
EXTENSIES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
#: De eerste bytes die bij een toegestaan type horen. Een .pdf die geen PDF is, komt er niet in.
_MAGIE = {"pdf": (b"%PDF",), "png": (b"\x89PNG",), "jpg": (b"\xff\xd8",), "jpeg": (b"\xff\xd8",)}
MAX_BYTES = 10 * 1024 * 1024
_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERIODE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def centen(x) -> int | None:
    """Euro's (komma of punt, mag negatief) → centen, exact via Decimal. None bij onleesbaar."""
    s = str(x if x is not None else "").strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite():
        return None
    return int((d * 100).to_integral_value(rounding="ROUND_HALF_UP"))


def euro(c: int) -> str:
    """Centen → "1234.56" (punt), zonder floats."""
    teken = "-" if c < 0 else ""
    c = abs(int(c))
    return f"{teken}{c // 100}.{c % 100:02d}"


def _datum(s) -> str:
    s = str(s or "").strip()[:10]
    if not _DATUM.match(s):
        return ""
    try:
        time.strptime(s, "%Y-%m-%d")
    except ValueError:
        return ""
    return s


def _tekst(s, n: int = 200) -> str:
    return " ".join(str(s or "").split())[:n]


def maak_kost(v: dict, cfg: dict, *, correctie: bool = False) -> tuple[dict | None, str]:
    """Valideer de velden van een nieuwe kostregel → (regel zonder id/created_*, "") of (None, reden).

    Fail-closed: een onbekende managementregel, een ongeldig bedrag of een regel zonder bijlage én
    zonder reden komt er niet in. Een negatief bedrag mag alleen op een regel die dat toestaat
    ("marketing contribution from suppliers") of in een correctie."""
    from nooch_village import finance_config as fc
    datum = _datum(v.get("entry_date"))
    if not datum:
        return None, "an invoice date (YYYY-MM-DD) is required"
    periode = str(v.get("period") or "").strip() or datum[:7]
    if not _PERIODE.match(periode):
        return None, "the period must be YYYY-MM"
    leverancier, omschrijving = _tekst(v.get("supplier"), 120), _tekst(v.get("description"))
    if not leverancier or not omschrijving:
        return None, "supplier and description are required"
    bedrag = centen(v.get("amount_excl"))
    btw = centen(v.get("vat")) if str(v.get("vat") or "").strip() else 0
    if bedrag is None or btw is None:
        return None, "amounts must be numbers (euros)"
    account = _tekst(v.get("account_code"), 80)
    regel_key = str(v.get("management_line") or "").strip() or fc.standaard_regel(account, cfg)
    regel = fc.regel(regel_key, cfg)
    if regel is None:
        return None, "pick a management line"
    if (bedrag < 0 or btw < 0) and not correctie and not regel["negatief"]:
        return None, "negative amounts are only allowed on 'marketing contribution from suppliers'"
    status = str(v.get("payment_status") or "open")
    if status not in BETAALSTATUS:
        return None, "payment status must be open or paid"
    betaald = _datum(v.get("paid_date")) if str(v.get("paid_date") or "").strip() else ""
    if str(v.get("paid_date") or "").strip() and not betaald:
        return None, "the paid date must be YYYY-MM-DD"
    bijlage = v.get("attachment") if isinstance(v.get("attachment"), dict) else None
    reden = _tekst(v.get("no_document_reason"), 200)
    if bijlage is None and not reden:
        return None, "attach the invoice, or say why there is no document"
    return {"entry_date": datum, "period": periode, "supplier": leverancier, "description": omschrijving,
            "amount_excl_cents": bedrag, "vat_cents": btw,
            "currency": _tekst(v.get("currency"), 3).upper() or "EUR",
            "account_code": account, "management_line": regel_key,
            "batch": _tekst(v.get("batch"), 60), "payment_status": status, "paid_date": betaald,
            "recurring_id": _tekst(v.get("recurring_id"), 40),
            "attachment": bijlage, "no_document_reason": "" if bijlage else reden,
            "note": _tekst(v.get("note"), 500), "corrects": _tekst(v.get("corrects"), 40)}, ""


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


class _Register:
    """De gedeelde borging van elk finance-register (Finance PR 1b: kosten én opbrengsten): één
    JSONL-bestand dat alleen groeit, bijlagen met hun sha256 in `data/finance/attachments/`, en één
    downloadlog `data/finance/downloads.jsonl` voor beide.

    LET OP: deze klasse heeft bewust GEEN update/delete. Wie er een toevoegt, breekt de borging.
    Een subklasse zet alleen `BESTAND` (en eventueel wat er bij een tegenboeking omdraait)."""

    BESTAND = ""
    #: De bedragvelden die een tegenboeking omdraait.
    BEDRAGEN = ("amount_excl_cents", "vat_cents")

    def __init__(self, data_dir: str):
        self.dir = os.path.join(data_dir, MAP)
        self.pad = os.path.join(self.dir, self.BESTAND)
        self.bijlagen = os.path.join(self.dir, "attachments")
        self.downloads = os.path.join(self.dir, "downloads.jsonl")

    # ── lezen ──────────────────────────────────────────────────────────────
    def alle(self) -> list[dict]:
        if not os.path.exists(self.pad):
            return []
        uit = []
        with open(self.pad, encoding="utf-8") as f:
            for regel in f:
                if regel.strip():
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue                             # een halve laatste regel: geen regel
        return uit

    def get(self, kid: str) -> dict | None:
        return next((r for r in self.alle() if r.get("id") == kid), None)

    def met_hash(self, h: str) -> list[dict]:
        return [r for r in self.alle() if (r.get("attachment") or {}).get("sha256") == h]

    def correcties_van(self, kid: str) -> list[dict]:
        return [r for r in self.alle() if r.get("corrects") == kid]

    # ── toevoegen (de ENIGE schrijfweg) ───────────────────────────────────
    def _append(self, regels: list[dict]) -> None:
        os.makedirs(self.dir, exist_ok=True)
        with open(self.pad, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                for r in regels:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _stempel(self, regel: dict, door: str) -> dict:
        return {"id": uuid.uuid4().hex, "created_at": time.time(), "created_by": door, **regel}

    def voeg_toe(self, regel: dict, *, door: str = "") -> dict:
        r = self._stempel(regel, door)
        self._append([r])
        return r

    def correctie(self, oud_id: str, nieuw: dict, *, door: str = "") -> tuple[dict, dict] | None:
        """Corrigeer een regel in één stap: een tegenboeking (omgekeerde bedragen, `corrects` = de
        oude regel, zelfde periode/regel/rekening) en de nieuwe, juiste regel. Samen één append."""
        oud = self.get(oud_id)
        if oud is None:
            return None
        storno = {k: v for k, v in oud.items() if k not in ("id", "created_at", "created_by")}
        storno.update({k: -oud[k] for k in self.BEDRAGEN if isinstance(oud.get(k), int)})
        storno.update(corrects=oud_id, note=f"Reversal of {oud_id}",
                      attachment=oud.get("attachment"), no_document_reason=oud.get("no_document_reason", ""))
        s, n = self._stempel(storno, door), self._stempel({**nieuw, "corrects": ""}, door)
        n["note"] = (n.get("note") + " · " if n.get("note") else "") + f"Replaces {oud_id}"
        self._append([s, n])
        return s, n

    # ── bijlagen ───────────────────────────────────────────────────────────
    def bewaar_bijlage(self, bestandsnaam: str, blob: bytes, *, jaar: str = "") -> tuple[dict | None, str]:
        """Schrijf een bijlage weg (nooit overschrijven: een nieuwe uuid) → (attachment, "") of
        (None, reden). pdf/png/jpg, maximaal 10 MB, en de inhoud moet bij de extensie passen."""
        ext = os.path.splitext(bestandsnaam or "")[1].lower().lstrip(".")
        if ext not in EXTENSIES:
            return None, "only pdf, png or jpg"
        if not blob:
            return None, "the file is empty"
        if len(blob) > MAX_BYTES:
            return None, "the file is larger than 10 MB"
        if not blob.startswith(_MAGIE[ext]):
            return None, f"this file is not a real .{ext}"
        jaar = jaar or time.strftime("%Y")
        rel = os.path.join(MAP, "attachments", jaar, f"{uuid.uuid4().hex}.{ext}")
        vol = os.path.join(os.path.dirname(self.dir), rel)
        os.makedirs(os.path.dirname(vol), exist_ok=True)
        with open(vol, "xb") as f:                          # "x": bestaat hij al, dan een fout
            f.write(blob)
        return {"path": rel, "sha256": sha256(blob), "filename": os.path.basename(bestandsnaam)[:120],
                "size": len(blob), "mime": EXTENSIES[ext]}, ""

    def lees_bijlage(self, regel: dict) -> tuple[bytes | None, str]:
        """(inhoud, "") of (None, reden). De hash wordt OPNIEUW berekend; klopt hij niet, dan niets."""
        b = regel.get("attachment") or {}
        vol = os.path.join(os.path.dirname(self.dir), b.get("path", ""))
        if not b.get("path") or not os.path.isfile(vol):
            return None, "the file is missing"
        with open(vol, "rb") as f:
            blob = f.read()
        if sha256(blob) != b.get("sha256"):
            return None, "the file does not match its recorded hash — it was changed or damaged"
        return blob, ""

    def log_download(self, kid: str, door: str) -> None:
        os.makedirs(self.dir, exist_ok=True)
        with open(self.downloads, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps({"id": kid, "register": self.BESTAND, "door": door,
                                "at": time.time()}) + "\n")
            fcntl.flock(f, fcntl.LOCK_UN)


class KostenRegister(_Register):
    """Het kostenregister: `data/finance/costs.jsonl`."""

    BESTAND = "costs.jsonl"


def filter_regels(regels: list[dict], *, periode: str = "", account: str = "", regel: str = "",
                  batch: str = "", leverancier: str = "", status: str = "",
                  zonder_document: bool = False) -> list[dict]:
    """De regels die aan alle opgegeven filters voldoen (leeg = geen filter)."""
    uit = []
    for r in regels:
        if periode and r.get("period") != periode:
            continue
        if account and r.get("account_code") != account:
            continue
        if regel and r.get("management_line") != regel:
            continue
        if batch and r.get("batch") != batch:
            continue
        if leverancier and leverancier.lower() not in str(r.get("supplier", "")).lower():
            continue
        if status and r.get("payment_status") != status:
            continue
        if zonder_document and r.get("attachment"):
            continue
        uit.append(r)
    return uit


def totalen(regels: list[dict], sleutel: str) -> dict[str, int]:
    """{waarde van `sleutel`: som exclusief btw (centen)}. Correcties tellen mee — dat is de bedoeling:
    een tegenboeking heft de oude regel op."""
    uit: dict[str, int] = {}
    for r in regels:
        k = str(r.get(sleutel) or "—")
        uit[k] = uit.get(k, 0) + int(r["amount_excl_cents"])
    return uit


def posten(regels: list[dict]) -> list[tuple[str, str, int, str]]:
    """De regels als bron-agnostische posten voor het P&L: (maand, managementregel, centen, bron)."""
    return [(r["period"], r["management_line"], int(r["amount_excl_cents"]), "register") for r in regels]
