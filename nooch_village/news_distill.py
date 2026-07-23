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


def _distill_prompt(title: str, brand: str, known: str, mission: str, strict: bool,
                    focus: str = "competitor") -> str:
    """De destilleer-prompt. `focus='materials'` geeft de wetenschapper een materiaal-bril (geen
    concurrent-bril): nieuwe/bio-based materialen, afbreekbaarheids-bewijs, certificeringen, labresultaten.
    `strict=True` (Inoreader-ingest): hoge lat, standaard 'geen'. `strict=False`: de gulle Scout-prompt."""
    m = mission or "organische groei via missie-gedreven SEO; duurzaam, vegan, plasticvrij"
    if focus == "materials":
        return (
            "Je bent de materiaalwetenschapper van NoochVille (plasticvrij, vegan, biologisch afbreekbaar "
            f"schoeisel — Nooch.earth). Missie: {m}.\n\n"
            f"Bron: {brand}. Nieuwskop:\n\"{title}\"\n\n"
            "Je zoekt ECHTE materiaal-signalen: een nieuw of verbeterd (bio-based, plasticvrij, gerecycled) "
            "materiaal, bewijs of onderbouwing van afbreekbaarheid (labresultaat, certificering, norm), een "
            "doorbraak in recycling of biofabricage, of een grondstof/vezel die relevant is voor duurzaam "
            "schoeisel.\n\n"
            "Types:\n"
            "- kaart: een concreet materiaal-signaal (nieuw materiaal, afbreekbaarheids-bewijs, "
            "certificering, labresultaat, recycling/biofabricage-doorbraak)\n"
            "- seed: een pril, opkomend materiaal-idee dat het volgen waard is (spaarzaam)\n"
            "- geen: alles wat NIET over materialen of materiaalinnovatie gaat\n\n"
            "GEEN bij: mode/trends zonder materiaal-inhoud, algemene duurzaamheids-marketing zonder "
            "onderbouwing, bedrijfs-/financieel nieuws, en niet-materiaal-onderwerpen. Bij echte twijfel: 'geen'.\n\n"
            "Antwoord EXACT zo:\nSOORT: kaart|seed|geen\n"
            "INHOUD: <kort: het materiaal of het signaal>\nWAAROM: <één korte zin>")
    if strict:
        return (
            "Je bent de scherpe concurrentie-analist van NoochVille (duurzaam, vegan schoenenmerk Nooch.earth). "
            f"Missie: {m}.\n\n"
            f"Bron: {brand}. Nieuwskop:\n\"{title}\"\n\n"
            "Je zoekt ECHTE marktsignalen over schoenen, schoenmaterialen of schoenenmerken. Een signaal "
            "hoeft GEEN hard cijfer te zijn: een concurrent-zet (lancering, campagne, samenwerking), een "
            "zwakte of kritiek op een merk (slechte review, controverse), of een marktverschuiving (bijv. "
            "barefoot wordt mainstream) telt óók als signaal.\n\n"
            "Types:\n"
            "- concurrent: een NOG NIET gevolgd schoenenmerk dat opduikt\n"
            "- kaart: een concreet signaal over de markt of een (al gevolgd) merk — een zet, een "
            "zwakte/sentiment, of een marktverschuiving\n"
            "- doelwit: een SPECIFIEK meerwoord-zoekwoord met koopintentie\n"
            "- seed: alleen als een breed zoekwoord echt nieuw radar-signaal is (spaarzaam)\n"
            "- geen: alles wat NIET over schoenen of schoenenmerken gaat\n\n"
            "GEEN bij: persoonlijke gezondheid, fitness of oefeningen, mode-accessoires (parfum, zonnebril), "
            "reis/lifestyle, en niet-schoenenmerken. Een merknaam die alleen als SPONSOR of zijdelings "
            "voorkomt is ook 'geen'. Bij echte twijfel: 'geen'.\n\n"
            f"Al gevolgde merken (NIET als concurrent kiezen; wél bruikbaar als kaart): {known}\n\n"
            "Antwoord EXACT zo:\nSOORT: concurrent|kaart|doelwit|seed|geen\n"
            "INHOUD: <kort: merk, zoekwoord of het signaal>\nWAAROM: <één korte zin>")
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
                    strict: bool = False, focus: str = "competitor") -> dict | None:
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
    prompt = _distill_prompt(title, brand, known, mission, strict, focus)
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


def _distill_batch_prompt(articles: list, *, mission: str, known: str,
                          strict: bool, focus: str) -> str:
    """Batch-variant van de destilleer-prompt: N koppen in één call (founder 23 jul, tegen de 20/dag-cap).
    Hergebruikt de EXACTE regels van `_distill_prompt` via een sentinel-render, zodat de single-prompt
    ongemoeid blijft en de regels nooit uit elkaar lopen."""
    single = _distill_prompt("§T§", "§B§", known, mission, strict, focus)
    i1 = single.index("\n\n")
    i2 = single.index("\n\n", i1 + 2)
    persona = single[:i1]                                   # persona + missie (kop-onafhankelijk)
    rest = single[i2 + 2:]                                  # regels + antwoordformat (art-intro eruit)
    ai = rest.index("Antwoord EXACT zo:")
    regels = rest[:ai].rstrip()
    fmt = rest[ai:].split("\n", 1)[1]                       # SOORT/INHOUD/WAAROM-regels (zonder de aanhef)
    koppen = "\n".join(f'[[N: {i + 1}]] Bron: {a.get("brand", "")} — kop: "{a.get("title", "")}"'
                       for i, a in enumerate(articles))
    return (persona + "\n\nJe krijgt MEERDERE nieuwskoppen; beoordeel ELKE los.\n\n" + regels
            + "\n\nKOPPEN:\n" + koppen
            + "\n\nGeef voor ELKE kop, in DEZELFDE nummering, exact dit blok (niets ertussen):\n"
            + "[[N: <nummer>]]\n" + fmt)


def _parse_distill_batch(out: str | None) -> dict:
    """LLM-batch-output → {nummer(1-based): (kind, content, rationale)}. Split op [[N: n]]; fail-soft."""
    res: dict = {}
    if not out:
        return res
    delen = re.split(r"\[\[N:\s*(\d+)\s*\]\]", out)
    for i in range(1, len(delen) - 1, 2):
        try:
            n = int(delen[i])
        except ValueError:
            continue
        body = delen[i + 1]
        sm = re.search(r"SOORT\s*:\s*(\w+)", body, re.I)
        im = re.search(r"INHOUD\s*:\s*(.+)", body, re.I)
        wm = re.search(r"WAAROM\s*:\s*(.+)", body, re.I)
        kind = sm.group(1).strip().lower() if sm else ""
        content = im.group(1).strip().strip('"').strip() if im else ""
        rationale = wm.group(1).strip() if wm else ""
        res[n] = (kind, content, rationale)
    return res


def distill_articles(articles: list, *, mission: str = "", known_brands=(), llm_reason=None,
                     strict: bool = False, focus: str = "competitor", batch: int = 10) -> list:
    """Destilleer een LIJST artikelen in BATCHES (default 10 per LLM-call) i.p.v. één call per artikel.
    Geeft een lijst even lang als de input: per artikel {kind, content, rationale} of None. Fail-closed
    per artikel (onparseerbaar of buiten de types → None)."""
    if not articles:
        return []
    if llm_reason is None:
        import functools
        from nooch_village.llm import reason as _reason
        llm_reason = functools.partial(_reason, call_site="news_distill_article", max_tokens=1500)
    known = ", ".join(known_brands) if known_brands else "(geen)"
    uit: list = [None] * len(articles)
    for s in range(0, len(articles), batch):
        groep = articles[s:s + batch]
        try:
            out = llm_reason(_distill_batch_prompt(groep, mission=mission, known=known,
                                                   strict=strict, focus=focus))
        except Exception:
            out = None
        parsed = _parse_distill_batch(out or "")
        for gi, a in enumerate(groep):
            d = parsed.get(gi + 1)
            if not d:
                continue
            kind, content, rationale = d
            if kind not in _KINDS or not content:
                continue
            if kind == "concurrent" and content.lower() in {b.lower() for b in known_brands}:
                continue
            uit[s + gi] = {"kind": kind, "content": content, "rationale": rationale}
    return uit


def distill_news(news: dict, proposals: NewsProposals, *, mission: str = "",
                 known_brands=(), llm_reason=None, limit: int = 8) -> dict:
    """Loop de gemonitorde nieuwsfeiten langs (één per merk) en destilleer nieuwe artikelen tot
    voorstellen. Slaat al verwerkte links over (idempotent). Geeft {scanned, proposed}."""
    scanned = proposed = 0
    # Eerst verzamelen (nieuw + niet-gezien), dan in één batch destilleren i.p.v. één call per merk.
    te_doen = []
    for brand, item in list(news.items())[:limit]:
        link = (item or {}).get("link", "")
        title = (item or {}).get("title", "")
        if not title or proposals.seen(link):
            continue
        te_doen.append({"brand": brand, "title": title, "link": link,
                        "date": (item or {}).get("date", "")})
    scanned = len(te_doen)
    resultaten = distill_articles(te_doen, mission=mission, known_brands=known_brands,
                                  llm_reason=llm_reason)
    for art, d in zip(te_doen, resultaten):
        proposals.mark_seen(art["link"])
        if d and proposals.add(d["kind"], d["content"], d["rationale"], art["brand"],
                               art["title"], art["link"]):
            proposed += 1
    return {"scanned": scanned, "proposed": proposed}
