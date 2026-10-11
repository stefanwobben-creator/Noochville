"""Kostenimport uit Excel met bijlagen — Finance PR 3 (11 oktober 2026).

Stefan downloadde de kosten en facturen uit Basecone. Een voorstel in Excel (gemaakt buiten
NoochVille), Stefan corrigeert, daarna deze import: een XLSX of CSV met één regel per kostregel, plus
een zip met de PDF's, gekoppeld op de kolom `bestand`.

GEEN AI EN GEEN NETWERK. Alles deterministisch, zoals de historie-import. Finance-data komt nooit in
een LLM-context (zie de guard in `tests/test_finance_pr1.py`).

DE STAPPEN:
1. PREVIEW (`bewaar` + `beoordeel`): het Excel-bestand en de zip worden meteen geborgd (sha256,
   `data/finance/imports/`, nooit overschreven) en elke rij krijgt een oordeel — nieuw, waarschuwing,
   dubbel, fout of niet geïmporteerd — met de reden. Er komt NIETS in het register.
2. BEVESTIGEN (`toepassen`): de geborgde bestanden worden opnieuw gelezen (hash gecontroleerd) en
   opnieuw beoordeeld tegen de stand van NU; alleen nieuwe rijen en rijen met een waarschuwing gaan
   erin, in één append, elk met `import_id`. Een PDF onder twee regels wordt één keer bewaard.
3. TERUGDRAAIEN (`terugdraaien`): elke regel van die import die nog niet gecorrigeerd is, krijgt een
   tegenboeking ("import <id> undone"). Niets verdwijnt.

EEN GELDIGE RIJ WORDT NOOIT STIL AANGEPAST. Geen managementregel = een fout (ook al heeft de rekening
of de leverancier een standaard: die wordt GENOEMD, niet gekozen). Een andere valuta dan EUR = een fout
(het P&L telt getallen op zonder om te rekenen). Een negatief bedrag = de fout van `maak_kost`.

FINANCE-DATA BLIJFT HIER: zelfde guard als de registers.
"""
from __future__ import annotations

import datetime as _dt
import io
import os
import re
import uuid
import zipfile

from nooch_village import finance_config as fc
from nooch_village import finance_historie as fh
from nooch_village.finance_register import (MAP, KostenRegister, _Register, _tekst, controleer_bijlage,
                                            euro, maak_kost, sha256)

#: Wat de preview als bestand accepteert (de zip apart).
TABEL_EXT = fh.IMPORT_EXT
#: Een zip mag uitgepakt niet groter zijn dan dit (een zip-bom is een fout, geen crash).
MAX_UITGEPAKT = 300 * 1024 * 1024

# ── kolommen ────────────────────────────────────────────────────────────────
#: veld → de kolomnamen waaronder hij in het bestand mag staan (Nederlands zoals in het voorstel,
#: plus de Engelse veldnamen van het register). Kleine letters, spaties samengevouwen.
KOLOMMEN = {
    "actie": ("actie", "action"),
    "entry_date": ("factuurdatum", "entry_date", "invoice date"),
    "period": ("periode", "period"),
    "supplier": ("leverancier", "supplier"),
    "description": ("omschrijving", "description"),
    "currency": ("valuta", "currency"),
    "amount_excl": ("excl. btw", "excl btw", "amount_excl", "excl. vat"),
    "vat": ("btw", "vat"),
    "management_line": ("managementregel", "management_line", "management line"),
    "opmerking": ("opmerking / vraag", "opmerking/vraag", "opmerking", "note"),
    "bestand": ("bestand", "file", "filename"),
    "type": ("type", "document type"),
    "totaal": ("totaal op document", "document_total", "total on document"),
    "zekerheid": ("zekerheid", "confidence"),
    "basecone": ("status in basecone", "basecone status"),
    "boekstuk": ("boekstuknummer", "boekstuknummer venema", "venema boekstuknummer", "venema"),
    "paid_via": ("betaald via", "paid_via", "paid via"),
    "no_document_reason": ("no_document_reason", "no document reason"),
    "account_code": ("rekening", "account_code", "account"),
    "batch": ("batch",),
}
VERPLICHT = ("actie", "entry_date", "supplier", "description", "amount_excl", "management_line", "bestand")
ACTIES = {"importeren": "import", "import": "import", "overslaan": "skip", "skip": "skip",
          "vraag": "vraag", "question": "vraag"}
_HERINNERING = re.compile(r"herinnering|aanmaning|reminder", re.I)
_DMJ = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$")

# ── de statussen van een rij ────────────────────────────────────────────────
NIEUW, WAARSCHUWING, DUBBEL, FOUT, NIET = "new", "warning", "duplicate", "error", "not imported"
TELT = (NIEUW, WAARSCHUWING)


def _norm(s) -> str:
    return " ".join(str(s or "").split()).lower()


def _kopkaart(kop: list) -> tuple[dict[str, int], list[str]]:
    """{veld: kolomindex} en de ontbrekende verplichte kolommen."""
    namen = [_norm(k) for k in kop]
    kaart = {}
    for veld, aliassen in KOLOMMEN.items():
        idx = next((i for i, n in enumerate(namen) if n in aliassen), None)
        if idx is not None:
            kaart[veld] = idx
    return kaart, [v for v in VERPLICHT if v not in kaart]


def _datum(x) -> str:
    """Een factuurdatum → YYYY-MM-DD, of "" als hij onleesbaar is. Excel levert een datum als
    datetime; tekst mag YYYY-MM-DD of DD-MM-YYYY zijn. Geen gok tussen dag en maand verder."""
    if isinstance(x, (_dt.datetime, _dt.date)):
        return x.strftime("%Y-%m-%d")
    s = str(x or "").strip()[:10]
    m = _DMJ.match(s)
    if m:
        s = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    try:
        _dt.date.fromisoformat(s)
        return s
    except ValueError:
        return ""


def lees_tabel(bestandsnaam: str, blob: bytes) -> tuple[list[dict], list[str]]:
    """XLSX/CSV → ([{nr, ruw: {veld: waarde}}], fouten in het bestand zelf)."""
    ext = os.path.splitext(bestandsnaam or "")[1].lower().lstrip(".")
    if ext not in TABEL_EXT:
        return [], ["the cost file must be .xlsx or .csv"]
    try:
        rijen = fh._rijen_xlsx(blob) if ext == "xlsx" else fh._rijen_csv(blob)
    except Exception as e:                              # een kapot bestand is een fout, geen crash
        return [], [f"the file cannot be read: {type(e).__name__}"]
    if not rijen:
        return [], ["the file is empty"]
    kaart, ontbreekt = _kopkaart(rijen[0])
    if ontbreekt:
        return [], ["missing column(s): " + ", ".join(KOLOMMEN[v][0] for v in ontbreekt)]
    uit = []
    for nr, rij in enumerate(rijen[1:], start=2):
        if not any(str(c).strip() for c in rij):
            continue                                    # een lege regel is geen rij
        uit.append({"nr": nr, "ruw": {v: (rij[i] if i < len(rij) else "") for v, i in kaart.items()}})
    return uit, []


def lees_zip(blob: bytes) -> tuple[dict[str, str], set[str], zipfile.ZipFile | None, str]:
    """({bestandsnaam: lid in de zip}, namen die twee keer voorkomen, zip, fout).

    KOPPELEN OP DE NAAM ZONDER PAD (aanvulling 1): de zip heeft een map bovenaan. macOS-rommel telt
    niet: `__MACOSX/`, `._*` en `.DS_Store`. Twee bestanden met dezelfde naam in verschillende mappen
    is een fout voor de rij die ernaar verwijst — welke bedoeld is, is niet te raden."""
    if not blob:
        return {}, set(), None, ""
    try:
        z = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return {}, set(), None, "the zip cannot be read"
    if sum(i.file_size for i in z.infolist()) > MAX_UITGEPAKT:
        return {}, set(), None, "the zip is too large when unpacked"
    kaart, dubbel = {}, set()
    for info in z.infolist():
        if info.is_dir():
            continue
        delen = info.filename.replace("\\", "/").split("/")
        naam = delen[-1]
        if "__MACOSX" in delen or naam.startswith("._") or naam == ".DS_Store" or not naam:
            continue
        if naam in kaart:
            dubbel.add(naam)
        kaart[naam] = info.filename
    return kaart, dubbel, z, ""


# ── borging: de geüploade bestanden en het importlogboek ─────────────────────
class KostenImportLog(_Register):
    """`data/finance/cost_imports.jsonl` (alleen toevoegen: een nieuwe status is een nieuwe regel) plus
    de bestanden in `data/finance/imports/`, met hun sha256."""

    BESTAND = "cost_imports.jsonl"
    BEDRAGEN = ()

    def _borg(self, bestandsnaam: str, blob: bytes, ext: str, mime: str) -> dict:
        rel = os.path.join(MAP, "imports", f"{uuid.uuid4().hex}.{ext}")
        vol = os.path.join(os.path.dirname(self.dir), rel)
        os.makedirs(os.path.dirname(vol), exist_ok=True)
        with open(vol, "xb") as f:
            f.write(blob)
        return {"path": rel, "sha256": sha256(blob), "size": len(blob),
                "filename": os.path.basename(bestandsnaam)[:120], "mime": mime}

    def bewaar(self, tabel: tuple[str, bytes], zip_: tuple[str, bytes], *, door: str,
               limiet: int) -> tuple[dict | None, str]:
        """Borg het kostenbestand en de zip en log de import als `previewed` → (import, "") of
        (None, reden). Boven `limiet` een vaste melding: Stefan splitst de import per jaar."""
        tnaam, tblob = tabel
        znaam, zblob = zip_
        ext = os.path.splitext(tnaam or "")[1].lower().lstrip(".")
        if ext not in TABEL_EXT:
            return None, "choose the cost file (.xlsx or .csv)"
        if not tblob:
            return None, "the cost file is empty"
        if len(tblob) > limiet or len(zblob) > limiet:
            return None, f"File too large (limit {limiet // (1024 * 1024)} MB). Split the import by year."
        if ext == "xlsx" and not tblob.startswith(b"PK\x03\x04"):
            return None, "this file is not a real .xlsx"
        if zblob and (os.path.splitext(znaam or "")[1].lower() != ".zip" or not zblob.startswith(b"PK")):
            return None, "the documents must be one .zip file"
        r = {"import_id": uuid.uuid4().hex[:12], "status": "previewed",
             "attachment": self._borg(tnaam, tblob, ext, TABEL_EXT[ext]),
             "zip": self._borg(znaam, zblob, "zip", "application/zip") if zblob else None}
        r = self._stempel(r, door)
        self._append([r])
        return r, ""

    def lees(self, imp: dict) -> tuple[tuple | None, str]:
        """((tabelnaam, tabelblob, zipblob), "") of (None, reden) — hashes opnieuw gecontroleerd."""
        tblob, fout = self.lees_bijlage(imp)
        if tblob is None:
            return None, fout
        zblob = b""
        if imp.get("zip"):
            zblob, fout = self.lees_bijlage({"attachment": imp["zip"]})
            if zblob is None:
                return None, f"zip: {fout}"
        return (imp["attachment"]["filename"], tblob, zblob), ""

    def status(self, import_id: str) -> dict | None:
        eigen = [r for r in self.alle() if r.get("import_id") == import_id]
        return max(eigen, key=lambda x: x.get("created_at", 0)) if eigen else None

    def imports(self) -> list[dict]:
        """De actuele stand van elke import, nieuwste eerst."""
        laatste: dict[str, dict] = {}
        for r in self.alle():
            if r["import_id"] not in laatste or r.get("created_at", 0) >= laatste[r["import_id"]].get("created_at", 0):
                laatste[r["import_id"]] = r
        return sorted(laatste.values(), key=lambda x: x.get("created_at", 0), reverse=True)

    def meld(self, basis: dict, *, door: str, **velden) -> dict:
        r = self._stempel({k: v for k, v in basis.items() if k not in ("id", "created_at", "created_by")}
                          | velden, door)
        self._append([r])
        return r


class LeveranciersStandaard(_Register):
    """`data/finance/supplier_defaults.jsonl` — per leverancier de managementregel die wordt
    VOORGESTELD (nooit stil gekozen). Alleen toevoegen, met wie en wanneer; de laatste telt.
    Niet in `config/finance.json`: dat bestand staat in git, en een wijziging op de server zou
    elke volgende deploy blokkeren."""

    BESTAND = "supplier_defaults.jsonl"
    BEDRAGEN = ()

    def standaarden(self) -> dict[str, dict]:
        """{genormaliseerde leverancier: {supplier, management_line}} — de laatste per leverancier."""
        uit: dict[str, dict] = {}
        for r in sorted(self.alle(), key=lambda x: x.get("created_at", 0)):
            uit[_norm(r.get("supplier"))] = r
        return uit

    def voor(self, leverancier: str) -> str:
        return (self.standaarden().get(_norm(leverancier)) or {}).get("management_line", "")

    def bewaar(self, leverancier: str, regel: str, *, door: str) -> dict:
        return self.voeg_toe({"supplier": _tekst(leverancier, 120), "management_line": regel}, door=door)


# ── beoordelen ──────────────────────────────────────────────────────────────
def _regel_key(waarde, cfg: dict) -> str | None:
    """Sleutel of label van een managementregel → de sleutel; "" als leeg; None als onbekend."""
    w = _norm(waarde)
    if not w:
        return ""
    return next((r["key"] for r in fc.regels(cfg) if w in {r["key"].lower(), _norm(r["label"])}), None)


def _levend(regels: list[dict]) -> list[dict]:
    """De regels die nu meetellen: geen tegenboeking en niet (meer) tegengeboekt. Een teruggedraaide
    import telt dus niet als dubbel — hij mag opnieuw."""
    weg = {r["corrects"] for r in regels if r.get("corrects")}
    return [r for r in regels if not r.get("corrects") and r["id"] not in weg]


def beoordeel(tabelnaam: str, tabelblob: bytes, zipblob: bytes, *, register: list[dict], cfg: dict,
              history_until: str, standaarden: dict[str, dict], import_id: str = "") -> dict:
    """Het oordeel per rij, zonder iets te schrijven → {rijen, fouten, telling, totalen, cutover}.

    Elke rij: {nr, status, redenen, waarschuwingen, regel (de kostregel zoals hij erin zou gaan, zonder
    bijlage), bestand, hash, blob_naam}. `register` = de huidige kostregels."""
    rijen, fouten = lees_tabel(tabelnaam, tabelblob)
    zkaart, zdubbel, z, zfout = lees_zip(zipblob)
    if zfout:
        fouten.append(zfout)
    levend = _levend(register)
    op_hash = {}
    op_sleutel = set()
    for r in levend:
        h = (r.get("attachment") or {}).get("sha256")
        if h:
            op_hash.setdefault(h, set()).add((r["amount_excl_cents"], r["management_line"]))
        op_sleutel.add((_norm(r["supplier"]), r["entry_date"], r["amount_excl_cents"] + r["vat_cents"],
                        r["management_line"]))
    hashes: dict[str, str] = {}                         # zip-lid → sha256 (één keer lezen)
    gezien_hash, gezien_sleutel = set(), set()
    uit = []
    for rij in rijen:
        ruw = rij["ruw"]
        o = {"nr": rij["nr"], "status": NIEUW, "redenen": [], "waarschuwingen": [], "regel": None,
             "bestand": str(ruw.get("bestand") or "").strip(), "hash": "", "lid": "",
             "leverancier": str(ruw.get("supplier") or "").strip(), "actie": _norm(ruw.get("actie")),
             "ruw": {k: ruw.get(k) for k in ("entry_date", "management_line", "amount_excl", "vat")}}
        uit.append(o)
        actie = ACTIES.get(o["actie"])
        opm = str(ruw.get("opmerking") or "").strip()
        if actie is None:
            o.update(status=FOUT, redenen=[f"unknown action '{ruw.get('actie')}' (importeren, overslaan or vraag)"])
            continue
        if actie != "import":
            o.update(status=NIET, redenen=[f"action: {o['actie']}" + (f" — {opm}" if opm else "")])
            continue
        red = o["redenen"]
        datum = _datum(ruw.get("entry_date"))
        if not datum:
            red.append(f"invalid invoice date '{ruw.get('entry_date')}'")
        periode = fh._maand(ruw.get("period")) if str(ruw.get("period") or "").strip() else ""
        if str(ruw.get("period") or "").strip() and not periode:
            red.append(f"invalid period '{ruw.get('period')}'")
        excl, f1 = fh.bedrag(ruw.get("amount_excl"))
        btw, f2 = fh.bedrag(ruw.get("vat")) if str(ruw.get("vat") or "").strip() else (0, "")
        if excl is None:
            red.append(f1 or "the amount excl. VAT is missing")
        if btw is None:
            red.append(f2)
        totaal_ruw = str(ruw.get("totaal") or "").strip()
        if totaal_ruw and excl is not None and btw is not None:
            totaal, f3 = fh.bedrag(ruw.get("totaal"))
            if totaal is None:
                red.append(f3)
            elif excl + btw != totaal:
                red.append(f"excl. VAT + VAT ({euro(excl + btw)}) is not the total on the document ({euro(totaal)})")
        valuta = (_tekst(ruw.get("currency"), 3) or "EUR").upper()
        if valuta != "EUR":
            red.append(f"currency {valuta}: only EUR can be imported (the P&L does not convert)")
        lijn = _regel_key(ruw.get("management_line"), cfg)
        if lijn is None:
            red.append(f"unknown management line '{ruw.get('management_line')}'")
        elif lijn == "":
            std = (standaarden.get(_norm(o["leverancier"])) or {}).get("management_line")
            lab = (fc.regel(std, cfg) or {}).get("label") if std else ""
            red.append("pick a management line" + (f" (the default for this supplier is {lab})" if lab else ""))
        via = fc.betaald_via_key(ruw.get("paid_via"), cfg)
        if via is None:
            red.append(f"unknown 'paid via' '{ruw.get('paid_via')}': leave empty for the Nooch bank account, "
                       f"or use " + ", ".join(x["label"] for x in fc.betaald_via(cfg)))
        # DE BIJLAGE: uit de zip, op naam zonder pad.
        blob = b""
        if o["bestand"]:
            naam = os.path.basename(o["bestand"].replace("\\", "/"))
            if naam in zdubbel:
                red.append(f"two files named '{naam}' in the zip")
            elif naam not in zkaart or z is None:
                red.append(f"file '{naam}' is not in the zip")
            else:
                o["lid"] = zkaart[naam]
                blob = z.read(o["lid"])
                fout = controleer_bijlage(naam, blob)
                if fout:
                    red.append(f"{naam}: {fout}")
                else:
                    o["hash"] = hashes.setdefault(o["lid"], sha256(blob))
        elif not str(ruw.get("no_document_reason") or "").strip():
            red.append("no file, and no reason why there is no document")
        if red:
            o["status"] = FOUT
            continue
        noot = " · ".join(x for x in (
            f"import:{import_id}" if import_id else "",
            f"Basecone: {_tekst(ruw.get('basecone'), 60)}" if str(ruw.get("basecone") or "").strip() else "",
            f"Venema: {_tekst(ruw.get('boekstuk'), 60)}" if str(ruw.get("boekstuk") or "").strip() else "",
            opm) if x)
        v = {"entry_date": datum, "period": periode, "supplier": ruw.get("supplier"),
             "description": ruw.get("description"), "amount_excl": euro(excl), "vat": euro(btw),
             "currency": "EUR", "account_code": ruw.get("account_code") or "", "management_line": lijn,
             "batch": ruw.get("batch") or "",
             # BETAALD VIA (besluit Stefan, 11 oktober): de leverancier is betaald, dus `paid`. Een
             # betaaldatum eist `maak_kost` niet, dus die blijft leeg — niets verzonnen.
             "payment_status": "paid" if via else "open", "paid_date": "", "paid_via": via,
             "note": noot, "no_document_reason": "" if o["bestand"] else ruw.get("no_document_reason"),
             "import_id": import_id,
             "attachment": {"sha256": o["hash"]} if o["bestand"] else None}
        regel, fout = maak_kost(v, cfg)
        if regel is None:
            o.update(status=FOUT, redenen=[fout])
            continue
        o["regel"] = regel
        # DUBBEL: dezelfde PDF met hetzelfde bedrag op dezelfde regel, of dezelfde leverancier, datum,
        # totaal en regel. Een PDF onder TWEE regels (een ander bedrag of een andere regel) is geen
        # dubbel — dat is een document dat splitst.
        k_hash = (o["hash"], regel["amount_excl_cents"], regel["management_line"])
        k_sleutel = (_norm(regel["supplier"]), regel["entry_date"],
                     regel["amount_excl_cents"] + regel["vat_cents"], regel["management_line"])
        if o["hash"] and k_hash[1:] in op_hash.get(o["hash"], set()):
            o.update(status=DUBBEL, redenen=["this document with this amount and line is already in the register"])
            continue
        if k_sleutel in op_sleutel:
            o.update(status=DUBBEL, redenen=["same supplier, date, total and line already in the register"])
            continue
        if (o["hash"] and k_hash in gezien_hash) or k_sleutel in gezien_sleutel:
            o.update(status=DUBBEL, redenen=["the same row appears earlier in this file"])
            continue
        if o["hash"]:
            gezien_hash.add(k_hash)
        gezien_sleutel.add(k_sleutel)
        w = o["waarschuwingen"]
        if history_until and regel["period"] <= history_until:
            w.append(f"before the cutover ({history_until}): kept, but not counted in the P&L")
        if _norm(ruw.get("zekerheid")) in ("laag", "low"):
            w.append("confidence: low")
        if "?" in opm:
            w.append(f"the note asks a question: {opm}")
        if _HERINNERING.search(str(ruw.get("type") or "")):
            w.append("the document is a reminder; the real invoice is missing")
        if w:
            o["status"] = WAARSCHUWING
    telling = {s: sum(1 for o in uit if o["status"] == s) for s in (NIEUW, WAARSCHUWING, DUBBEL, FOUT, NIET)}
    totalen: dict[str, dict] = {}
    for o in uit:
        if o["status"] in TELT:
            t = totalen.setdefault(o["regel"]["currency"], {"aantal": 0, "excl": 0, "btw": 0})
            t["aantal"] += 1
            t["excl"] += o["regel"]["amount_excl_cents"]
            t["btw"] += o["regel"]["vat_cents"]
    telt = [o for o in uit if o["status"] in TELT]
    voor = [o for o in telt if history_until and o["regel"]["period"] <= history_until]
    cutover = {"tot": history_until, "aantal": len(telt), "voor_aantal": len(voor),
               "voor_excl": sum(o["regel"]["amount_excl_cents"] for o in voor)}
    if z is not None:
        z.close()
    return {"rijen": uit, "fouten": fouten, "telling": telling, "totalen": totalen, "cutover": cutover}


# ── bevestigen en terugdraaien ──────────────────────────────────────────────
def toepassen(reg: KostenRegister, oordeel: dict, zipblob: bytes, *, door: str) -> list[dict]:
    """Schrijf de rijen die meetellen (nieuw en waarschuwing) in ÉÉN append. Een PDF onder twee
    regels wordt één keer bewaard; beide regels krijgen dezelfde bijlage. → de nieuwe regels."""
    telt = [o for o in oordeel["rijen"] if o["status"] in TELT]
    bijlagen: dict[str, dict] = {}
    z = zipfile.ZipFile(io.BytesIO(zipblob)) if zipblob else None
    try:
        regels = []
        for o in telt:
            regel = dict(o["regel"])
            if o["lid"]:
                if o["hash"] not in bijlagen:
                    blob = z.read(o["lid"])
                    b, fout = reg.bewaar_bijlage(os.path.basename(o["lid"]), blob, jaar=regel["entry_date"][:4])
                    if b is None:                       # na de preview kan dit niet meer; toch nooit stil
                        raise ValueError(f"row {o['nr']}: {fout}")
                    bijlagen[o["hash"]] = b
                regel["attachment"] = bijlagen[o["hash"]]
            regels.append(regel)
    finally:
        if z is not None:
            z.close()
    return reg.voeg_toe_alle(regels, door=door)


def terugdraaien(reg: KostenRegister, import_id: str, *, door: str) -> tuple[int, int]:
    """Annuleer elke regel van deze import die nog niet gecorrigeerd is → (geannuleerd, overgeslagen).
    Een gecorrigeerde regel blijft staan zoals hij is: de correctie is een eigen besluit."""
    gedaan = overgeslagen = 0
    for r in reg.alle():
        if r.get("import_id") != import_id or r.get("corrects"):
            continue
        if reg.niet_te_corrigeren(r["id"]):
            overgeslagen += 1
            continue
        reg.annuleer(r["id"], f"import {import_id} undone", door=door)
        gedaan += 1
    return gedaan, overgeslagen
