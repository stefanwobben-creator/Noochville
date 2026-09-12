"""OpenLibrarySearchInsideSkill — zinnen uit boeken waarin een term voorkomt (voltekst).

DE BELOFTE EN HET GEDRAG LIEPEN UITEEN (skill-review 12-09-2026). Naam, description, input_schema,
skill_labels ("Searches the full text of books") en zoekstrategie.BRONNEN ("full text of books")
beloofden allemaal voltekst-zoeken, en de code bevroeg `openlibrary.org/search.json` — de CATALOGUS
(titel/auteur/onderwerp) — en gaf titels, subjects en de eerste zin terug. De planner koos de skill
dus voor iets wat hij niet deed. Sinds scope 54 doet hij wat hij belooft:

Endpoint: https://openlibrary.org/search/inside.json?q=<term>  (open, geen key vereist)
  Zoekt in de gescande boekteksten van het Internet Archive en geeft per treffer de editie plus de
  tekstfragmenten ("highlights") waarin de term staat. Verwachte vorm:
    {"hits": {"total": N, "hits": [{"edition": {"key": "/books/OL…M", "title": …, "authors": …},
                                    "ia": "<archive-id>", "highlight": {"text": ["…{{{term}}}…"]}}]}}
  De parse is DEFENSIEF: elk niveau wordt op type gecontroleerd en valt terug op leeg, want dit is
  een publiek endpoint zonder contract. De `{{{`/`}}}`-markering om het gezochte woord gaat eruit.

Records: {title, url (archive.org/details/<ia>, anders openlibrary.org<edition.key>), tekst (de
fragmenten samengevoegd), authors, year}. Een `text` als leeswijzer.

Drie uitkomsten (de conventie van het dorp): nul treffers → `no_data` + reason (tot scope 54 kwam er
`{"total": 0, "hits": []}` zonder `no_data` terug, en dat las de uitvoerlaag als 'geen inhoud' — een
vals kennisgat voor de critic); netwerkfout → `error` (timeout 20 s, één herhaling); anders records.
"""
from __future__ import annotations
import logging
import re
import time
from nooch_village.skills import Skill

log = logging.getLogger(__name__)

_ENDPOINT = "https://openlibrary.org/search/inside.json"
_UA = "NoochVillage/1.0 (nooch.earth research bot)"
_TIMEOUT = 20
_RETRY_PAUZE = 2.0
_MAX_TEKST = 2000               # per boek: de fragmenten samen; boven de leesextract-drempel van 600
_MARKERING = re.compile(r"\{\{\{|\}\}\}")


def _lijst(v) -> list:
    return v if isinstance(v, list) else []


def _dictje(v) -> dict:
    return v if isinstance(v, dict) else {}


def _jaar(edition: dict):
    """Het publicatiejaar uit een editie-dict, defensief: `publish_year` (int, str of lijst) of het
    eerste viercijferige getal in `publish_date`. None als er niets bruikbaars staat."""
    py = edition.get("publish_year")
    if isinstance(py, list):
        py = py[0] if py else None
    for kandidaat in (py, edition.get("publish_date")):
        m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", str(kandidaat or ""))
        if m:
            return int(m.group(1))
    return None


def _auteurs(edition: dict) -> list[str]:
    """Auteursnamen: `authors` (lijst van dicts met `name`, of strings) of `author_name` (strings)."""
    uit = []
    for a in _lijst(edition.get("authors")) + _lijst(edition.get("author_name")):
        naam = a.get("name") if isinstance(a, dict) else a
        if isinstance(naam, str) and naam.strip() and naam.strip() not in uit:
            uit.append(naam.strip())
    return uit[:3]


def parse_hits(data) -> tuple[int, list[dict]]:
    """(total, records) uit de search/inside-respons. Elk niveau op type gecontroleerd; een treffer
    zonder editie-titel én zonder fragment valt weg (daar valt niets over te zeggen)."""
    hits_blok = _dictje(_dictje(data).get("hits"))
    try:
        total = int(hits_blok.get("total") or 0)
    except (TypeError, ValueError):
        total = 0
    records: list[dict] = []
    for hit in _lijst(hits_blok.get("hits")):
        hit = _dictje(hit)
        edition = _dictje(hit.get("edition"))
        fragmenten = [" ".join(_MARKERING.sub("", str(f)).split())
                      for f in _lijst(_dictje(hit.get("highlight")).get("text")) if str(f or "").strip()]
        tekst = " … ".join(f for f in fragmenten if f)[:_MAX_TEKST]
        title = str(edition.get("title") or "").strip()
        if not title and not tekst:
            continue
        ia = hit.get("ia") or edition.get("ia") or ""
        ia = str((ia[0] if ia else "") if isinstance(ia, list) else ia).strip()
        key = str(edition.get("key") or "").strip()
        url = (f"https://archive.org/details/{ia}" if ia
               else (f"https://openlibrary.org{key}" if key.startswith("/") else ""))
        records.append({"source": "openlibrary", "title": title, "url": url, "tekst": tekst,
                        "authors": _auteurs(edition), "year": _jaar(edition)})
    return max(total, len(records)) if records else total, records


def _als_tekst(term: str, total: int, records: list[dict]) -> str:
    kop = f"{total} book(s) with '{term}' in their full text (Open Library search inside)"
    eerste = records[0] if records else None
    if not eerste:
        return kop + "."
    detail = f"“{eerste.get('title') or '(untitled)'}”"
    if eerste.get("year"):
        detail += f", {eerste['year']}"
    frag = (eerste.get("tekst") or "")[:160]
    return f"{kop}; first: {detail}" + (f" — {frag}" if frag else "") + "."


class OpenlibrarySearchInsideSkill(Skill):
    name = "openlibrary_search_inside"
    input_schema = ("term: str (required — a word or short phrase as it would appear in a book, mostly "
                    "English; exact wording, e.g. 'barefoot running'). Optional: limit: int (default 5, "
                    "max 20)")
    required_payload = ("term",)
    output_schema = ("list: total: int, hits: list[{title, url (archive.org or openlibrary.org), tekst "
                     "(the passages that contain the term), authors, year}], text (summary for the "
                     "wall) | no_data + reason | error")
    cost = "rate_limited"          # publiek endpoint zonder key; beleefde pauze, geen quota
    description = (
        "Full-text search inside scanned books (Open Library / Internet Archive): give a word or short "
        "phrase as it appears in a book, mostly English. Returns per book the title, a link and the "
        "passages that contain the term; 'no_data' when no book mentions it. Keyless, read-only."
    )

    def run(self, payload: dict, context) -> dict:
        from nooch_village.sleutelmasker import masker
        term = str((payload or {}).get("term") or "").strip()
        if not term:
            return {"error": "geen term opgegeven", "hits": []}
        try:
            limit = max(1, min(int((payload or {}).get("limit", 5)), 20))
        except (TypeError, ValueError):
            limit = 5

        import requests
        data, fout = None, ""
        for poging in (1, 2):
            try:
                resp = requests.get(_ENDPOINT, params={"q": term, "limit": limit},
                                    headers={"User-Agent": _UA}, timeout=_TIMEOUT)
                status = int(getattr(resp, "status_code", 200) or 200)
                if status >= 500 and poging == 1:
                    fout = f"Open Library gaf HTTP {status}"
                    time.sleep(_RETRY_PAUZE)
                    continue
                if status >= 400:
                    from nooch_village.sleutelmasker import http_fout
                    return {"error": http_fout(resp, "Open Library"), "hits": [], "term": term}
                data = resp.json()
                break
            except Exception as e:                      # noqa: BLE001 — timeout, DNS, geen JSON
                fout = masker(f"Open Library niet bereikbaar: {e}")
                if poging == 1:
                    time.sleep(_RETRY_PAUZE)
        if data is None:
            return {"error": fout or "Open Library gaf geen bruikbaar antwoord", "hits": [], "term": term}

        total, records = parse_hits(data)
        if not records:
            return {"term": term, "total": 0, "hits": [], "no_data": True,
                    "reason": f"geen boek met '{term}' in de voltekst gevonden"}
        time.sleep(0.5)   # vriendelijk voor het openbare endpoint
        return {"term": term, "total": total, "hits": records[:limit],
                "text": _als_tekst(term, total, records)}
