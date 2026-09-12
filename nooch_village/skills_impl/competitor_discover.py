"""competitor_discover — spot nieuwe concurrenten door gids-artikelen UIT TE LEZEN.

Bron: SerpAPI Google-zoekopdracht (geeft échte artikel-URLs, geen Google News-redirects waar
een lezer niet doorheen komt). Per gevonden gids: pagina lezen, en de LLM de genoemde
merknamen laten extraheren ('15 Best Vegan Sneaker Brands' → Veja, Vesica Piscis, Etiko, ...).
Dependency-vrij (requests + stdlib) + de gedeelde LLM-ladder.

Fail-closed, drie uitkomsten (scope 55): geen SerpAPI-key of geen model → `ok: False, error`
(de bron/het model faalde, het item blijft open); gidsen gelezen maar geen merknaam →
`no_data: True, reason` (onderzocht, niets gevonden); anders records mét het zinnetje uit de
gids dat de merknaam draagt. Liever niets dan een verkeerde merknaam; de mens bevestigt de rest
in de cockpit.
"""
from __future__ import annotations

import json
import logging
import os
import re

from nooch_village.skills import Skill, resolve_source_scope

log = logging.getLogger("village.skill.discover")

# Engels, met een grounding-regel en een JSON-vorm (skill-review 12-09-2026: de prompt was
# Nederlands, vrije tekst en zonder token-plafond). De namen moeten LETTERLIJK in de tekst staan;
# `_zin_rond` toetst dat daarna nog eens deterministisch, zodat een naam uit het geheugen van het
# model nooit als kandidaat landt.
_PROMPT = (
    "Below is the text of an article about {topic}.\n"
    "List ONLY the names of shoe brands that the article presents as examples within "
    "'{topic}'. Do NOT include brands that are mentioned only for comparison, contrast or in "
    "passing (for example a mainstream brand used as a counterexample). No publication names, "
    "no authors, no generic words, not 'Nooch'. Use only names that literally appear in the "
    "text below; never add a brand from your own knowledge.\n"
    "Return ONLY a JSON array of strings, no prose, no code fences. Nothing found → []\n\n"
    "Article:\n{text}"
)
# Ruim genoeg voor een lange gids ('25 best …'): de merken onderaan vielen bij 6000 tekens buiten
# beeld, omdat strip_html het menu en de boilerplate vooraan laat staan.
_TEXT_CAP = 12000
_MAX_TOKENS = 400            # een JSON-lijst van hooguit enkele tientallen korte namen
_CITAAT_MAX = 240

_NOT_A_BRAND = {
    "none", "best", "top", "guide", "sustainable", "ethical", "vegan", "sneakers",
    "shoes", "footwear", "brands", "brand", "the", "good on you", "business insider",
    "esquire", "vogue", "nooch", "review", "and", "more", "vegnews", "peta",
}


def _strip_html(html: str) -> str:
    from nooch_village.web_read import strip_html
    return strip_html(html)


def _parse_brand_list(llm_out: str, known: list[str]) -> list[str]:
    """LLM-output → schone, ontdubbelde merknamenlijst, gefilterd op ruis + bekende merken.

    Leest de JSON-array van de huidige prompt én de kommagescheiden vorm van de oude (een model
    dat de JSON-instructie negeert levert nog steeds bruikbare namen op)."""
    if not llm_out or llm_out.strip().upper().startswith("NONE"):
        return []
    raw: list = []
    cleaned = re.sub(r"```(?:json)?", "", llm_out).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(cleaned[start:end + 1])
            raw = [str(x) for x in data if isinstance(x, (str, int, float))] if isinstance(data, list) else []
        except (ValueError, TypeError):
            raw = []
    if not raw:
        raw = re.split(r"[,\n;]+", llm_out)
    known_l = {k.lower() for k in known}
    seen, out = set(), []
    for part in raw:
        name = re.sub(r"^[\s\-\*\d\.\)]+", "", part).strip().strip('"').strip()
        low = name.lower()
        if (not name or len(name) < 2 or len(name) > 40 or low in _NOT_A_BRAND
                or low in known_l or "nooch" in low or low in seen):
            continue
        seen.add(low)
        out.append(name)
    return out


_ZINGRENS = re.compile(r"(?<=[.!?])\s+")


def _zin_rond(text: str, name: str) -> str:
    """De zin uit de gids waarin de merknaam staat (deterministisch, uit de tekst zelf — niet van het
    model). Leeg als de naam niet in de tekst voorkomt: dan is het geen kandidaat uit DEZE gids."""
    if not text or not name:
        return ""
    low = text.lower()
    pos = low.find(name.lower())
    if pos == -1:
        return ""
    # de dichtstbijzijnde zinsgrens vóór en na de naam, binnen een venster van 300 tekens; zonder
    # zinsgrens (een lijstje, een kop) een woordgrens op hooguit 120 tekens vóór en 160 erna
    begin = max(0, pos - 300)
    voor = text[begin:pos]
    grenzen = [m.end() for m in _ZINGRENS.finditer(voor)]
    if grenzen:
        zin_start = begin + grenzen[-1]
    else:
        kort = text[max(0, pos - 120):pos]
        zin_start = pos - len(kort) + (kort.find(" ") + 1 if " " in kort and pos > 120 else 0)
    na = text[pos:pos + 300]
    m = _ZINGRENS.search(na)
    if m:
        zin_eind = pos + m.start()
    else:
        kort = na[:160]
        zin_eind = pos + (kort.rfind(" ") if " " in kort and len(na) > 160 else len(kort))
    zin = " ".join(text[zin_start:zin_eind].split())
    return zin if len(zin) <= _CITAAT_MAX else zin[:_CITAAT_MAX - 1] + "…"


class CompetitorDiscoverSkill(Skill):
    name = "competitor_discover"
    cost = "credits"               # SerpAPI-zoekopdracht
    side_effect_free = True
    required_env = ("SERPAPI_API_KEY",)
    description = ("Discovers candidate competitor brands: finds guide articles ('best X brands') "
                   "via SerpAPI, reads each page and lets the model extract the brand names that "
                   "literally appear in the text, each with the sentence that names it. Fail-closed: "
                   "no key or no model is an error; guides without brand names is 'nothing found'.")
    input_schema = ("topic: str (the subject — the category of brands to discover, DERIVED from the "
                    "project goal, e.g. 'best barefoot shoe brands'; `query` is accepted as alias; "
                    "omitted = the standing category from the config `discover_query`) · brands: "
                    "list[str] (OPTIONAL — known brands filtered out of the candidates; empty = filter "
                    "nothing) · limit: int (number of guides to read, default 4)")
    # Geen hard-verplicht payload-veld: `brands` is een optioneel filter, en het onderwerp (topic/query)
    # heeft een config-fallback (discover_query). run() weigert bij de bron zichtbaar als noch onderwerp
    # noch config een categorie geeft (resolve_source_scope), dus die grens ligt op de uitvoer, niet in een
    # payload-precheck die de config-fallback toch niet kan zien.
    # Geen `required_payload`: de eis is VOORWAARDELIJK. Het onderwerp mag uit de payload komen
    # (topic of query) óf uit de staande config (`discover_query`) — een platte verplichting zou een
    # geldige config-only-aanroep blokkeren. Daarom bewaakt `validate_payload` het, met de config
    # erbij; dat is dezelfde route die `community_listening` voor zijn of-of-eis gebruikt.
    required_payload = ()
    output_schema = ("ok: bool, candidates: list[{brand, article, link, citaat}], text: str (the summary), "
                     "query: str, gescand: int (guides found), gelezen: int (guides readable) "
                     "| no_data: True, reason | ok: False, error")

    def validate_payload(self, payload: dict, context) -> list:
        """Is er een onderwerp? Uit de payload of uit de config — anders is dit item niet uitvoerbaar.

        Zonder deze poort gaf de planner het item groen en weigerde de skill pas bij het draaien
        ("geen onderwerp (topic)"), waarna het project parkeerde op een fout die vóór de aanroep
        te zien was."""
        payload = payload or {}
        topic = (payload.get("topic") or payload.get("query") or "").strip()
        config_scope = str((getattr(context, "settings", {}) or {}).get("discover_query", "")).strip()
        _scope, err = resolve_source_scope(topic, config_scope, veld="onderwerp (topic)",
                                           config_key="discover_query")
        return [err] if err else []

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        brands = payload.get("brands") or []
        topic = (payload.get("topic") or payload.get("query") or "").strip()
        config_scope = str((getattr(context, "settings", {}) or {}).get("discover_query", "")).strip()
        # Scope-contract: onderwerp uit het project of de config, nooit een code-default. Ontbreekt het,
        # dan weigert de skill zichtbaar i.p.v. een categorie te gokken (de vegan-in-plaats-van-barefoot-fout).
        query, err = resolve_source_scope(topic, config_scope, veld="onderwerp (topic)",
                                          config_key="discover_query")
        if err:
            log.warning("competitor_discover: %s", err)
            return {"ok": False, "error": err}
        try:
            limit = int(payload.get("limit", 4))
        except (TypeError, ValueError):
            limit = 4
        try:
            guides = self._serpapi_guides(context, query)
        except Exception as exc:
            from nooch_village.sleutelmasker import masker      # een ConnectionError draagt de URL mét api_key
            log.warning("competitor_discover: SerpAPI-zoekopdracht faalde: %s", masker(exc))
            return {"ok": False, "error": masker(exc)}
        if not guides:
            # Onderzocht, niets gevonden: de zoekmachine gaf geen gids terug. Dat is een antwoord
            # (📭), geen bronfout — de bron werkte, er is alleen niets over dit onderwerp.
            return {"ok": True, "no_data": True, "candidates": [], "gescand": 0, "gelezen": 0,
                    "query": query, "reason": f"no guide articles found for '{query}'"}

        from nooch_village.llm import reason
        ladder = (str(payload.get("ladder") or "").strip() or None)   # zelfde afspraak als tegenspraak
        seen, candidates = set(), []
        gelezen = 0
        for g in guides[:limit]:
            text = self._fetch_text(g["link"])
            if len(text) < 200:                          # niet leesbaar → overslaan
                continue
            gelezen += 1
            out = reason(_PROMPT.format(topic=query, text=text[:_TEXT_CAP]),
                         call_site="skill_competitor_discover", max_tokens=_MAX_TOKENS,
                         json_mode=True, ladder=ladder)
            if out is None:
                # "Geen model" is ALTIJD een fout, nooit een lege lijst: tot scope 55 maakte
                # `_parse_brand_list(None)` hier stil `[]` van en las de wall dat als "4" (gelukt).
                return {"ok": False, "error": "no model available (all LLM tiers failed or no key) — "
                                              f"{gelezen} of {len(guides)} guides read, none extracted",
                        "gescand": len(guides), "gelezen": gelezen, "query": query}
            for name in _parse_brand_list(out, brands):
                if name.lower() in seen:
                    continue
                citaat = _zin_rond(text, name)
                if not citaat:
                    # Grounding: de naam staat niet in de gids → uit het geheugen van het model,
                    # geen kandidaat uit deze bron.
                    log.info("competitor_discover: '%s' staat niet in de tekst van %s — overgeslagen",
                             name, g["link"][:60])
                    continue
                seen.add(name.lower())
                candidates.append({"brand": name, "article": g["title"], "link": g["link"],
                                   "citaat": citaat})
        if not candidates:
            return {"ok": True, "no_data": True, "candidates": [], "gescand": len(guides),
                    "gelezen": gelezen, "query": query,
                    "reason": f"{gelezen} of {len(guides)} guides read, no brand names"}
        namen = ", ".join(c["brand"] for c in candidates[:8])
        if len(candidates) > 8:
            namen += f", … (+{len(candidates) - 8})"
        return {"ok": True, "candidates": candidates, "gescand": len(guides), "gelezen": gelezen,
                "query": query,
                "text": (f"{len(candidates)} candidate brand(s) from {gelezen} of {len(guides)} guides "
                         f"read for '{query}': {namen}")}

    def _serpapi_guides(self, context, query: str) -> list[dict]:
        from nooch_village import web_read
        key = ((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
               or os.getenv("SERPAPI_API_KEY"))
        if not key:
            raise RuntimeError("SERPAPI_API_KEY ontbreekt — skill faalt bewust closed")
        return web_read.serpapi_search(query, key)

    def _fetch_text(self, link: str) -> str:
        """Lees een echte artikel-URL en geef platte tekst terug. Faalt → lege string."""
        from nooch_village import web_read
        return web_read.fetch_text(link)
