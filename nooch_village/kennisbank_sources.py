"""Source-adapters voor de kennisbank-intake: URL en PDF → (ruwe tekst, bron-label).

GEEN nieuwe pijplijn (guardrail): deze adapters produceren alleen ruwe tekst + een
bron-label en voeden dat aan de bestaande atomiser (kennisbank_intake.intake). De
provenance leidt de atomiser af uit de inhoud, niet hardgecodeerd op "pdf" of "url".

    URL  → trafilatura (hoofdtekst, boilerplate eruit) ─┐
    PDF  → pypdf, gechunkt op alinea-grenzen ───────────┼─→ (raw, label) → intake → atomen
    plakken/typen (bestaand) ───────────────────────────┘

Fail netjes: een onbereikbare pagina of een scan zonder tekstlaag geeft een duidelijke
None/melding terug — nooit halve rommel doorsturen (master-brief: fail-closed).
"""
from __future__ import annotations

import csv
import io
import re

# Chunk-maat voor lange documenten: ruim onder wat één intake-call aankan, liever iets
# grover en deduppen dan afkappen (taak 5b: kwaliteit boven de laatste token).
CHUNK_TEKENS = 7000
_MIN_TEKST = 200          # minder dan dit uit een hele PDF = vermoedelijk scan zonder tekstlaag
_TABEL_RIJEN_PER_CHUNK = 40   # tabeldata per blok rijen, zodat één intake-call behapbaar blijft


def van_url(url: str) -> tuple[str, str] | None:
    """Haal een pagina op en extraheer de leesbare hoofdtekst (trafilatura strip't
    nav/footer/boilerplate). Geeft (raw, label) met label = titel + URL, of None als
    de pagina niet op te halen of niet leesbaar te maken is."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        return None
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        tekst = trafilatura.extract(downloaded, include_comments=False,
                                    include_tables=True)
        if not tekst or len(tekst.strip()) < _MIN_TEKST:
            return None
        titel = ""
        try:
            meta = trafilatura.extract_metadata(downloaded)
            titel = (meta.title or "").strip() if meta else ""
        except Exception:
            pass
        label = f"{titel} — {url}" if titel else url
        return tekst.strip(), label[:160]
    except Exception:
        return None                      # netwerk/parse-fout → fail netjes, geen halve rommel


def van_pdf(data: bytes, filename: str = "") -> list[tuple[str, str]] | None:
    """Extraheer tekst uit een PDF en lever chunks van ~CHUNK_TEKENS op alinea-grenzen,
    elk met hetzelfde bron-label (documenttitel of bestandsnaam → één onafhankelijkheids-
    groep, precies wat de woozle-guard wil). None = geen tekstlaag gevonden (scan; OCR
    valt buiten v1 — de caller meldt dat expliciet i.p.v. stil niets te doen)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        paginas = [(p.extract_text() or "") for p in reader.pages]
    except Exception:
        return None
    heel = "\n\n".join(t.strip() for t in paginas if t.strip())
    if len(heel) < _MIN_TEKST:
        return None                      # scan zonder tekstlaag → expliciete melding bij caller
    titel = ""
    try:
        titel = ((reader.metadata or {}).get("/Title") or "").strip()
    except Exception:
        pass
    label = (titel or filename or "pdf-upload").strip()[:120]
    return [(chunk, label) for chunk in _chunk(heel)]


# ── Tabellaire bronnen (Excel / CSV / Google Sheet) ──────────────────────────
# Guardrail (layout-brief): tabeldata NIET blind door de proza-atomiser. Een tabel wordt
# een compacte "kolom: waarde"-weergave per rij; de atomiser krijgt de tabeldata-vlag en
# maakt er feiten/metingen van, geen verhaaltjes. Volledige MetricStore-reeks-koppeling is
# een aparte vervolgstap; hier landt een rij als schoon feit mét zijn getal + context.

def _tabel_chunks(headers: list[str], rijen: list[list], label: str) -> list[tuple[str, str]]:
    """Zet kop + rijen om in tekst-chunks: per rij één regel 'kol: waarde | kol: waarde'.
    Lege cellen worden overgeslagen; blokken van _TABEL_RIJEN_PER_CHUNK rijen."""
    headers = [str(h or f"kol{i+1}").strip() for i, h in enumerate(headers)]
    schoon = [r for r in rijen if any(str(c).strip() for c in r)]
    if not headers or not schoon:
        return []
    chunks: list[tuple[str, str]] = []
    for i in range(0, len(schoon), _TABEL_RIJEN_PER_CHUNK):
        blok = schoon[i:i + _TABEL_RIJEN_PER_CHUNK]
        regels = [f"Kolommen: {', '.join(headers)}"]
        for r in blok:
            paren = [f"{headers[j]}: {str(c).strip()}"
                     for j, c in enumerate(r) if j < len(headers) and str(c).strip()]
            if paren:
                regels.append(" | ".join(paren))
        chunks.append(("\n".join(regels), label[:120]))
    return chunks


def van_csv(data: bytes, filename: str = "") -> list[tuple[str, str]] | None:
    try:
        tekst = data.decode("utf-8-sig", errors="replace")
        rijen = list(csv.reader(io.StringIO(tekst)))
    except Exception:
        return None
    if len(rijen) < 2:
        return None
    label = (filename or "csv-upload").strip()[:120]
    return _tabel_chunks(rijen[0], rijen[1:], label) or None


def van_excel(data: bytes, filename: str = "") -> list[tuple[str, str]] | None:
    """Alle werkbladen; per blad kop + rijen → tabel-chunks met bladnaam in het label."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        return None
    basis = (filename or "excel-upload").strip()[:100]
    uit: list[tuple[str, str]] = []
    for ws in wb.worksheets:
        rijen = [[("" if c is None else c) for c in row]
                 for row in ws.iter_rows(values_only=True)]
        if len(rijen) < 2:
            continue
        label = f"{basis} · {ws.title}" if len(wb.worksheets) > 1 else basis
        uit += _tabel_chunks(rijen[0], rijen[1:], label)
    return uit or None


_GSHEET_RE = re.compile(r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)")


def van_gsheet(url: str) -> list[tuple[str, str]] | None:
    """Publieke Google Sheet → CSV-export → tabel-chunks. Alleen publiek leesbare sheets
    (geen auth); een privé-sheet geeft geen bruikbare CSV → None (nette melding bij caller)."""
    m = _GSHEET_RE.search(url or "")
    if not m:
        return None
    gid_m = re.search(r"[#&]gid=(\d+)", url)
    gid = gid_m.group(1) if gid_m else "0"
    export = (f"https://docs.google.com/spreadsheets/d/{m.group(1)}"
              f"/export?format=csv&gid={gid}")
    try:
        import urllib.request
        with urllib.request.urlopen(export, timeout=20) as resp:
            data = resp.read()
    except Exception:
        return None
    if b"<html" in data[:200].lower():       # login/permissie-pagina i.p.v. CSV
        return None
    return van_csv(data, filename="Google Sheet")


# ── Auto-detectie: één ingang, verklaarbaar type ─────────────────────────────

def detect_and_extract(text: str = "", filename: str = "",
                       data: bytes = b"") -> dict:
    """Herken het brontype en extraheer. Geeft {kind, chunks, tabular, error}:
    - kind: mensvriendelijk label ("website", "PDF", "Excel", "Google Sheet", "tekst")
    - chunks: [(raw, label), ...] of None bij een fout
    - tabular: True voor tabeldata (atomiser krijgt dan de tabeldata-hint)
    - error: korte melding bij None (verklaarbaar; geen stille mislukking)"""
    fn = (filename or "").lower().strip()
    if data and fn:
        if fn.endswith(".pdf"):
            c = van_pdf(data, filename)
            return {"kind": "PDF", "chunks": c, "tabular": False,
                    "error": None if c else "geen tekstlaag gevonden (scan? OCR valt buiten v1)"}
        if fn.endswith((".xlsx", ".xlsm", ".xls")):
            c = van_excel(data, filename)
            return {"kind": "Excel", "chunks": c, "tabular": True,
                    "error": None if c else "geen leesbare tabel in het werkblad"}
        if fn.endswith(".csv"):
            c = van_csv(data, filename)
            return {"kind": "CSV", "chunks": c, "tabular": True,
                    "error": None if c else "geen leesbare rijen in het CSV-bestand"}
        # onbekend bestand → als platte tekst proberen
        text = data.decode("utf-8", errors="replace")
    t = (text or "").strip()
    if not t:
        return {"kind": "leeg", "chunks": None, "tabular": False, "error": "geen invoer"}
    if re.match(r"^https?://", t) and "\n" not in t:
        if "docs.google.com/spreadsheets" in t:
            c = van_gsheet(t)
            return {"kind": "Google Sheet", "chunks": c, "tabular": True,
                    "error": None if c else "sheet niet publiek leesbaar (deel 'iedereen met de link')"}
        if "docs.google.com/presentation" in t:
            return {"kind": "Google Slides", "chunks": None, "tabular": False,
                    "error": "Google Slides wordt nog niet ondersteund — exporteer als PDF"}
        c = van_url(t)
        return {"kind": "website", "chunks": [c] if c else None, "tabular": False,
                "error": None if c else "kon de pagina niet ophalen of leesbaar maken"}
    # platte tekst: één chunk, label = eerste regel of 'notitie'
    label = (t.splitlines()[0][:80] if t.splitlines() else "notitie") or "notitie"
    return {"kind": "tekst", "chunks": [(t, label)], "tabular": False, "error": None}


def _chunk(tekst: str, maat: int = CHUNK_TEKENS) -> list[str]:
    """Splits op alinea-grenzen in blokken van ~maat tekens. De staart gaat nooit
    verloren; een alinea die zelf groter is dan de maat wordt als eigen blok geleverd."""
    blokken: list[str] = []
    huidig: list[str] = []
    lengte = 0
    for alinea in re.split(r"\n\s*\n", tekst):
        alinea = alinea.strip()
        if not alinea:
            continue
        if lengte + len(alinea) > maat and huidig:
            blokken.append("\n\n".join(huidig))
            huidig, lengte = [], 0
        huidig.append(alinea)
        lengte += len(alinea) + 2
    if huidig:
        blokken.append("\n\n".join(huidig))
    return blokken
