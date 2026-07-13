"""Scout destilleert concurrent-nieuws tot voorstellen — mens-gated.

De ConcurrentScout houdt per merk het laatste nieuwsfeit bij (competitor_news.json). Deze module
laat de Scout die koppen LÉZEN en destilleren tot één bruikbaar voorstel per artikel:

  kaart      = een kenniskaartje (herbruikbaar feit/insight voor Nooch's kennisbasis)
  seed       = een breed zoekwoord dat de radar voedt (functie 'volg')
  doelwit    = een specifiek rank-zoekwoord waar we content voor willen maken (functie 'doelwit')
  concurrent = een nog niet gevolgd merk dat het volgen waard is

Net als de rest van het dorp produceert dit UITSLUITEND voorstellen; de mens bevestigt of negeert
in de cockpit. Geen LLM beschikbaar of niets bruikbaars in de kop → niets (fail-closed).
Bevestigen routeert naar de juiste store (notes / library / competitor_brands).
"""
from __future__ import annotations
import json, os, re, time, uuid
from nooch_village.util import atomic_write_json

_KINDS = ("kaart", "seed", "doelwit", "concurrent")


class NewsProposals:
    """Wachtrij van uit nieuws gedestilleerde voorstellen (data/news_proposals.json).
    `seen` houdt verwerkte artikel-links bij zodat dezelfde kop niet opnieuw wordt gedestilleerd."""

    def __init__(self, path: str):
        self.path = path
        self._data = {"items": {}, "seen": []}
        if os.path.exists(path):
            try:
                loaded = json.load(open(path))
                self._data["items"] = loaded.get("items", {})
                self._data["seen"] = loaded.get("seen", [])
            except Exception:
                pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._data)

    def seen(self, link: str) -> bool:
        return bool(link) and link in self._data["seen"]

    def mark_seen(self, link: str) -> None:
        if link and link not in self._data["seen"]:
            self._data["seen"].append(link)
            self._save()

    def add(self, kind: str, content: str, rationale: str = "", brand: str = "",
            title: str = "", link: str = "") -> str | None:
        """Voeg een voorstel toe. Dedup op (kind, content) over niet-genegeerde items."""
        kind = (kind or "").strip().lower()
        content = (content or "").strip()
        if kind not in _KINDS or not content:
            return None
        cl = content.lower()
        for it in self._data["items"].values():
            if (it["kind"] == kind and it["content"].lower() == cl
                    and it["status"] != "rejected"):
                return it["id"]
        pid = uuid.uuid4().hex[:12]
        self._data["items"][pid] = {
            "id": pid, "kind": kind, "content": content[:160], "rationale": rationale[:240],
            "brand": brand, "title": title[:160], "link": link, "status": "pending",
            "at": time.time()}
        self._save()
        return pid

    def pending(self) -> list[dict]:
        return sorted((it for it in self._data["items"].values() if it["status"] == "pending"),
                      key=lambda it: it["at"], reverse=True)

    def get(self, pid: str) -> dict | None:
        return self._data["items"].get(pid)

    def set_status(self, pid: str, status: str) -> bool:
        it = self._data["items"].get(pid)
        if it is None or status not in ("pending", "confirmed", "rejected"):
            return False
        it["status"] = status
        self._save()
        return True


def _distill_prompt(title: str, brand: str, known: str, mission: str, strict: bool) -> str:
    """De destilleer-prompt. `strict=True` (Inoreader-ingest): hoge lat, standaard 'geen', geen
    geforceerde missie-links. `strict=False` (Google-News-pijplijn): de oorspronkelijke, gulle prompt."""
    m = mission or "organische groei via missie-gedreven SEO; duurzaam, vegan, plasticvrij"
    if strict:
        return (
            "Je bent de KRITISCHE Scout van NoochVille (duurzaam, vegan schoenenmerk Nooch.earth). "
            f"Missie: {m}.\n\n"
            f"Bron: {brand}. Nieuwskop:\n\"{title}\"\n\n"
            "WEES STRENG. De standaard is 'geen'. Kies ALLEEN iets anders als de kop DIRECT en CONCREET "
            "over schoenen, schoenmaterialen of een schoenenmerk gaat én NoochVille echt verder helpt. "
            "Forceer GEEN missie-link: een kop die alleen zijdelings met duurzaamheid, gezondheid, mode of "
            "lifestyle te maken heeft is 'geen'. Celebrity-, reis-, deal- en algemene trendkoppen zijn 'geen'.\n\n"
            "Types:\n"
            "- concurrent: een NOG NIET gevolgd schoenenmerk dat een concrete zet doet (lancering, claim, groei)\n"
            "- doelwit: een SPECIFIEK meerwoord-zoekwoord met koopintentie\n"
            "- kaart: een HARD, herbruikbaar feit of cijfer over de markt of een concurrent (geen mening, geen fluff)\n"
            "- seed: alleen als een breed zoekwoord echt NIEUW radar-signaal is (spaarzaam)\n"
            "- geen: al het andere — bij twijfel ALTIJD 'geen'\n\n"
            f"Al gevolgde merken (NIET als concurrent kiezen): {known}\n\n"
            "Antwoord EXACT zo:\nSOORT: concurrent|doelwit|kaart|seed|geen\n"
            "INHOUD: <kort: het merk, zoekwoord of feit>\nWAAROM: <één korte zin>")
    return (
        "Je bent de Scout van NoochVille (duurzaam, vegan schoenenmerk Nooch.earth). "
        f"Missie/strategie: {m}.\n\n"
        f"Lees deze nieuwskop over '{brand}':\n\"{title}\"\n\n"
        "Destilleer ER ÉÉN ding uit dat NoochVille verder helpt. Kies het type:\n"
        "- kaart: een herbruikbaar feit/inzicht voor onze kennisbasis (geen zoekwoord)\n"
        "- seed: een BREED zoekwoord dat onze radar voedt (één/twee woorden)\n"
        "- doelwit: een SPECIFIEK zoekwoord met intentie waar we op willen ranken (meerwoord)\n"
        "- concurrent: een nog niet gevolgd merk dat we zouden moeten volgen\n"
        "- geen: er zit niets bruikbaars in deze kop\n\n"
        f"Al gevolgde merken (kies die NIET als concurrent): {known}\n\n"
        "Antwoord EXACT zo:\nSOORT: kaart|seed|doelwit|concurrent|geen\n"
        "INHOUD: <het feit, het zoekwoord, of de merknaam>\nWAAROM: <één korte zin>")


def distill_article(article: dict, *, mission: str = "", known_brands=(), llm_reason=None,
                    strict: bool = False) -> dict | None:
    """Destilleer één nieuwsartikel tot één voorstel {kind, content, rationale}, of None.
    Fail-closed zonder LLM of zonder bruikbaar antwoord."""
    title = (article.get("title") or "").strip()
    if not title:
        return None
    if llm_reason is None:
        import functools
        from nooch_village.llm import reason as _reason
        llm_reason = functools.partial(_reason, call_site="news_distill_article")
    brand = article.get("brand", "")
    known = ", ".join(known_brands) if known_brands else "(geen)"
    prompt = _distill_prompt(title, brand, known, mission, strict)
    out = (llm_reason(prompt) or "").strip()
    if not out:
        return None
    sm = re.search(r"SOORT\s*:\s*(\w+)", out, re.IGNORECASE)
    im = re.search(r"INHOUD\s*:\s*(.+)", out, re.IGNORECASE)
    wm = re.search(r"WAAROM\s*:\s*(.+)", out, re.IGNORECASE)
    kind = (sm.group(1).strip().lower() if sm else "")
    content = (im.group(1).strip().strip('"').strip() if im else "")
    rationale = (wm.group(1).strip() if wm else "")
    if kind not in _KINDS or not content:
        return None
    if kind == "concurrent" and content.lower() in {b.lower() for b in known_brands}:
        return None
    return {"kind": kind, "content": content, "rationale": rationale}


def distill_news(news: dict, proposals: NewsProposals, *, mission: str = "",
                 known_brands=(), llm_reason=None, limit: int = 8) -> dict:
    """Loop de gemonitorde nieuwsfeiten langs (één per merk) en destilleer nieuwe artikelen tot
    voorstellen. Slaat al verwerkte links over (idempotent). Geeft {scanned, proposed}."""
    scanned = proposed = 0
    for brand, item in list(news.items())[:limit]:
        link = (item or {}).get("link", "")
        title = (item or {}).get("title", "")
        if not title or proposals.seen(link):
            continue
        scanned += 1
        d = distill_article({"brand": brand, "title": title, "link": link,
                             "date": (item or {}).get("date", "")},
                            mission=mission, known_brands=known_brands, llm_reason=llm_reason)
        proposals.mark_seen(link)
        if d and proposals.add(d["kind"], d["content"], d["rationale"], brand, title, link):
            proposed += 1
    return {"scanned": scanned, "proposed": proposed}
