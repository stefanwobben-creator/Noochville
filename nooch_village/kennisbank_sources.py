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

import io
import re

# Chunk-maat voor lange documenten: ruim onder wat één intake-call aankan, liever iets
# grover en deduppen dan afkappen (taak 5b: kwaliteit boven de laatste token).
CHUNK_TEKENS = 7000
_MIN_TEKST = 200          # minder dan dit uit een hele PDF = vermoedelijk scan zonder tekstlaag


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
