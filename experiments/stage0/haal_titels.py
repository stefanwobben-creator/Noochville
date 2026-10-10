#!/usr/bin/env python3
"""Stage 0 — haal de RUWE titel terug voor elke rij van de eval-set (10 oktober 2026).

Waarom. Tot 19 september 2026 ging elk radar-artikel door `news_distill` (de Gemini-ladder): die
herschreef de kop tot `content` en schreef `rationale` erbij. De gelabelde set bevat dus alleen
modeltekst — een lokaal wegveeg-filter dat VÓÓR de ladder draait, zou die nooit gezien hebben. Wat
zo'n filter wél ziet: de kop van het artikel, het domein, de feed. De kop is niet bewaard, de link
wel. Dit script haalt hem terug.

Wat het doet:
1. koppelt elke eval-rij (id = hash van feed + content, zie `eval_triage.row_id`) aan zijn
   radar-item op (feed, content) → link, source, published_at, en of het `[eigen merk]` was;
2. haalt per link de paginatitel: eerst `og:title`, dan `<title>`. Een pagina die niet laadt of
   geen titel heeft, krijgt GEEN titel maar een reden (`fout`) — nooit een gok of de herschreven tekst;
3. schrijft alles naar `titels.jsonl` (gitignored: interne verwijzingen), hervatbaar.

De titel van een pagina is niet altijd letterlijk de feed-kop (een productpagina heet anders dan het
nieuwsbericht erover). Dat is de beste benadering die terug te halen is; het rapport zegt het erbij.

Gebruik:
    RADAR=<pad naar een kopie van prod data/radar.json> python3 experiments/stage0/haal_titels.py
"""
from __future__ import annotations

import concurrent.futures as cf
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HIER)
from eval_triage import EXCLUDE_FEEDS, load_rows  # noqa: E402

RADAR = os.environ.get("RADAR", "")
UIT = os.environ.get("TITELS_FILE", os.path.join(_HIER, "titels.jsonl"))
WERKERS = int(os.environ.get("WERKERS", "8"))
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126.0 Safari/537.36")
_OG = re.compile(r"""<meta[^>]+(?:property|name)\s*=\s*["']og:title["'][^>]*>""", re.I)
_CONTENT = re.compile(r"""content\s*=\s*["']([^"']*)["']""", re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _schoon(t: str) -> str:
    return " ".join(html.unescape(t or "").split())[:300]


def titel_uit_html(h: str) -> str:
    """og:title, anders <title>, anders "". Puur — de toets staat in de tests van dit script."""
    m = _OG.search(h)
    if m:
        c = _CONTENT.search(m.group(0))
        if c and _schoon(c.group(1)):
            return _schoon(c.group(1))
    m = _TITLE.search(h)
    return _schoon(m.group(1)) if m else ""


#: Titels die niet het artikel zijn maar de site, een blokkade of een archief. Liever geen titel dan
#: deze: een filter dat "Reddit" leest, leest niets.
_GENERIEK = re.compile(r"^(reddit|youtube|just a moment|access denied|attention required|"
                       r"page not found|404|403 forbidden|are you a robot|.*\barchives\b.*|"
                       r"[a-z0-9.-]+\.(com|org|gov|net|de|nl))\W*$", re.I)


def _get(url: str, n: int = 400_000) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(n).decode(r.headers.get_content_charset() or "utf-8", "replace")


def _via_api(link: str) -> str | None:
    """Titel via een publieke API voor sites die een browser-scrape blokkeren. None = geen API."""
    host = urllib.parse.urlparse(link).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        d = json.loads(_get("https://www.youtube.com/oembed?format=json&url="
                            + urllib.parse.quote(link, safe="")))
        return _schoon(d.get("title", ""))
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", link)
    if m:
        d = json.loads(_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                            f"?db=pubmed&retmode=json&id={m.group(1)}"))
        return _schoon(d["result"][m.group(1)].get("title", ""))
    if "reddit.com" in host:
        d = json.loads(_get(link.split("?")[0].rstrip("/") + ".json"))
        return _schoon(d[0]["data"]["children"][0]["data"].get("title", ""))
    return None


def haal(link: str) -> dict:
    try:
        t = _via_api(link)
        if t is None:
            t = titel_uit_html(_get(link))
    except Exception as e:                                    # netwerk/HTTP-fout: een reden, geen titel
        return {"titel": "", "fout": f"{type(e).__name__}: {str(e)[:120]}"}
    if t and _GENERIEK.match(t):
        return {"titel": "", "fout": f"generieke titel: {t[:60]}"}
    return {"titel": t, "fout": "" if t else "geen titel op de pagina"}


def main() -> None:
    if not RADAR or not os.path.exists(RADAR):
        sys.exit("Zet RADAR op een kopie van prod data/radar.json (de evalset draagt geen link).")
    items = json.load(open(RADAR, encoding="utf-8"))["items"]
    norm = lambda s: " ".join((s or "").split())
    per_sleutel: dict[tuple, dict] = {}
    for it in items.values():
        if it.get("status") in ("goedgekeurd", "afgewezen"):
            per_sleutel.setdefault((it.get("feed", ""), norm(it.get("content"))), it)
    klaar = {}
    if os.path.exists(UIT):
        for line in open(UIT, encoding="utf-8"):
            e = json.loads(line)
            klaar[e["id"]] = e
    rows = [r for r in load_rows() if r["feed"] not in EXCLUDE_FEEDS]
    todo = []
    for r in rows:
        if r["id"] in klaar and klaar[r["id"]].get("titel"):
            continue
        it = per_sleutel.get((r["feed"], norm(r["content"])))
        if it is None:
            klaar[r["id"]] = {"id": r["id"], "titel": "", "fout": "geen radar-item gevonden"}
            continue
        todo.append((r["id"], it))
    print(f"{len(rows)} rijen, {len(todo)} op te halen, {len(klaar)} al gedaan")
    with cf.ThreadPoolExecutor(WERKERS) as ex:
        futs = {ex.submit(haal, it["link"]): (rid, it) for rid, it in todo}
        for i, f in enumerate(cf.as_completed(futs), 1):
            rid, it = futs[f]
            klaar[rid] = {"id": rid, "link": it["link"], "source": it.get("source", ""),
                          "published_at": it.get("published_at", ""),
                          "eigen_merk": str(it.get("rationale") or "").startswith("[eigen merk]"),
                          **f.result()}
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}")
    with open(UIT, "w", encoding="utf-8") as f:
        for e in klaar.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    met = sum(1 for e in klaar.values() if e.get("titel"))
    print(f"klaar: {met} van {len(klaar)} met titel → {UIT}")


if __name__ == "__main__":
    main()
