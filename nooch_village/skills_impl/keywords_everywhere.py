from __future__ import annotations
import logging, os, re
import requests
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_VALID_DATA_SOURCES = {"gkp", "cli"}
_BATCH = 100                       # KE: max 100 keywords per call (1 credit per keyword)

# Rol-vriendelijke synoniemen → de twee echte KE-codes. Een skill die álle rollen gebruiken
# hoort geen API-jargon te eisen: "google" (de klassieke rol-gok) mag gewoon 'gkp' worden.
_DATA_SOURCE_ALIASES = {
    "gkp": "gkp", "google": "gkp", "google keyword planner": "gkp",
    "keyword planner": "gkp", "planner": "gkp", "keywordplanner": "gkp",
    "cli": "cli", "clickstream": "cli", "click stream": "cli", "clickstream data": "cli",
    "kliks": "cli", "klikstroom": "cli",
}


def resolve_data_source(value, default: str = "gkp") -> tuple[str, str | None]:
    """Normaliseer een (mogelijk door een rol verzonnen) data_source naar 'gkp' of 'cli'.

    Leeg → de default. Bekend synoniem → de juiste code. Onbekende waarde → val STIL terug op de
    default en geef een semantische waarschuwing terug (nooit crashen op rol-input). Geeft
    (bron, waarschuwing|None)."""
    if value is None or str(value).strip() == "":
        return (default if default in _VALID_DATA_SOURCES else "gkp"), None
    key = str(value).strip().lower()
    if key in _DATA_SOURCE_ALIASES:
        return _DATA_SOURCE_ALIASES[key], None
    veilig = default if default in _VALID_DATA_SOURCES else "gkp"
    return veilig, (f"onbekende zoekvolume-bron '{value}' — ik gebruik de vaste bron '{veilig}'")


def _approved_keywords(context) -> list[str]:
    """De gecureerde keywords uit de Library (status 'approved') — de dynamische veldenbron. Zo voedt
    de discovery-lus KE automatisch; geen aparte termenlijst."""
    lib = getattr(context, "library", None) if context is not None else None
    if lib is None:
        return []
    return [w for w, e in lib.all().items() if e.get("status") == "approved"]


def _sanitize_field(kw: str) -> str:
    """Keyword → veilige observatie-veldsleutel (keywordseverywhere_<veld>_day)."""
    return "".join(c if c.isalnum() else "_" for c in kw.strip().lower()).strip("_") or "kw"


def opportunity_score(volume, *, position=None, ranks=None) -> int | None:
    """Organische kans per zoekwoord: zoekvolume × hoeveel ruimte we nog hebben om te stijgen.

    kans = round(volume * gap), met:
      - ranks is False (we ranken niet voor deze term) of geen positie bekend → gap = 1.0 (volle upside)
      - wel een GSC-positie p → gap = clamp((p - 1) / 10, 0, 1): #1 ≈ benut (0), pagina 2+ ≈ vol (1)

    Bewust NIET op KE's 'competition': dat is Google Ads-veilingdruk (betaald), geen organische
    moeilijkheid — die zou commerciële termen ten onrechte op kans 0 zetten. Onze eigen GSC-stand
    is de eerlijke maat voor resterende organische ruimte. None als volume onbekend is.
    """
    if volume is None:
        return None
    try:
        v = int(volume)
    except (TypeError, ValueError):
        return None
    if ranks is False or position is None:
        gap = 1.0
    else:
        try:
            p = float(position)
        except (TypeError, ValueError):
            gap = 1.0
        else:
            gap = min(1.0, max(0.0, (p - 1.0) / 10.0))
    return round(v * gap)


def trend_change_pct(trend) -> float | None:
    """Procentuele verandering over de KE-trendreeks (laatste vs eerste maand, ~12 mnd).
    Voor volg-woorden: laat de échte trend zien over een jaar i.p.v. een 7-daagse momentopname.
    Accepteert een lijst getallen of dicts met 'value'. None als niet te bepalen."""
    if not trend:
        return None
    vals = []
    for t in trend:
        v = t.get("value") if isinstance(t, dict) else t
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    if len(vals) < 2 or vals[0] <= 0:
        return None
    return round((vals[-1] - vals[0]) / vals[0] * 100, 1)


def _normalize_kw(raw) -> list[str]:
    """`kw` als schone lijst termen. Een planner geeft nogal eens één string ("barefoot shoes" of
    "a, b, c"); die werd tot scope 55 TEKEN VOOR TEKEN verstuurd (14 credits, 14 letters terug).
    Een string splitst op komma, puntkomma of regeleinde; een lijst wordt gestript en ontdubbeld."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = re.split(r"[,;\n]+", raw)
    elif not isinstance(raw, (list, tuple, set)):
        raw = [raw]
    seen, out = set(), []
    for t in raw:
        term = str(t or "").strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return out


def _rij_tekst(row: dict) -> str:
    """Eén leesbare regel per keyword ("12100/mo, cpc 0.42, trend +22%"): de strekking die het
    verslag en de note tonen. Zonder deze regel las het verslag de rij als ruwe JSON."""
    delen = [f"{int(row.get('vol') or 0)}/mo"]
    if row.get("cpc"):
        delen.append(f"cpc {row['cpc']:.2f}")
    if row.get("competition"):
        delen.append(f"competition {row['competition']:.2f}")
    tp = trend_change_pct(row.get("trend"))
    if tp is not None:
        delen.append(f"trend {tp:+.0f}% over 12 months")
    return ", ".join(delen)


class KeywordsEverywhereSkill(DataSourceSkill):
    name = "keywords_everywhere"
    input_schema = ("kw: list[str] (REQUIRED — the keywords to look up, max 100 per call; a comma-separated "
                    "string is accepted) · country: str (optional, ISO code like 'nl'; empty = global) · "
                    "currency: str (optional, default 'eur') · data_source: 'gkp' | 'cli' (optional; default "
                    "from the settings, synonyms like 'google' accepted, unknown falls back)")
    required_payload = ("kw",)
    output_schema = ("keywords: list[{term, keyword, vol, cpc, competition, trend, tekst}], text: str, "
                     "credits_consumed, credits_remaining | no_data: True, reason | raises on no key/HTTP error")
    SOURCE = "keywordseverywhere"
    # Flux-bron: zoekvolume is een niveau (geen cumulatieve stand) → de tegel toont de waarde/lijn zelf.
    # Weekly: KE-volume is een maand-gemiddelde, weekly meten is ruim voldoende.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    needs_secret = True
    cost = "credits"
    required_env = ("KEYWORDS_EVERYWHERE_API_KEY",)
    side_effect_free = True
    description = (
        "Real search volume, CPC, competition and a 12-month trend per keyword, from the Keywords "
        "Everywhere API. TWELVE MONTHS IS THIS SOURCE'S CEILING, not a setting: it is what the API "
        "returns. Twelve months shows seasonality, not whether something is structurally growing — "
        "for that question use `google_trends` with a multi-year timeframe."
    )

    def available_metrics(self, context=None) -> list[str]:
        """DYNAMISCHE velden: de approved Library-keywords als veilige sleutels (alleen zoekvolume).
        Zonder context → leeg (de keywords staan in de Library, niet vast in de skill)."""
        return [_sanitize_field(kw) for kw in _approved_keywords(context)]

    def is_configured(self, context) -> bool:
        """Betaalde API met credits → key vereist. Geen key = 'niet geconfigureerd' (los van 'dood')."""
        s = getattr(context, "settings", {}) or {}
        return bool(s.get("KEYWORDS_EVERYWHERE_API_KEY") or os.getenv("KEYWORDS_EVERYWHERE_API_KEY"))

    def daily_values(self, context, datum: str, *, _run=None) -> dict:
        """Zoekvolume per approved Library-keyword, via de batch-`run` (max 100 keywords/call, 1 credit
        per keyword — dus in blokken van 100, nooit één call per term). Alleen volume (geen CPC).
        Volledig fail-closed per veld: een falende chunk laat die keywords op None en crasht de puls
        niet. `_run` injecteerbaar voor tests (geen netwerk)."""
        keywords = _approved_keywords(context)
        out = {_sanitize_field(kw): None for kw in keywords}
        if not keywords:
            return out
        run = _run or self.run
        s = getattr(context, "settings", None)
        if s is None:
            log.error("Keywords Everywhere: geen settings beschikbaar — bron levert niets "
                      "(fail-closed, geen fallback-land).")
            return out
        country = (s.get("ke_country") or "").strip()     # leeg/afwezig = bewust global; GEEN 'nl'-fallback
        currency = s.get("keywordseverywhere_currency", "eur")
        vols: dict = {}
        for i in range(0, len(keywords), _BATCH):
            chunk = keywords[i:i + _BATCH]
            try:
                res = run({"kw": chunk, "country": country, "currency": currency}, context)
                for row in (res.get("keywords") or []):
                    vols[(row.get("keyword") or "").strip().lower()] = row.get("vol")
            except Exception as exc:                 # geen key, HTTP-fout, KE-wijziging → chunk faalt
                log.warning("Keywords Everywhere batch faalde (chunk %d): %s", i // _BATCH, exc)
        for kw in keywords:
            v = vols.get(kw.strip().lower())
            if v is not None:
                out[_sanitize_field(kw)] = v
        return out

    def run(self, payload: dict, context) -> dict:
        """Haal keyword-data op uit de Keywords Everywhere API.

        Input (payload):
          kw          list[str]  — verplicht, 1–100 termen; leeg → ValueError, >100 → ValueError
          country     str        — default "" (leeg = global; GEEN 'nl'-default)
          currency    str        — default "eur"
          data_source str        — 'gkp' (Google Keyword Planner) of 'cli' (Clickstream). Default uit
                                    settings (keywordseverywhere_data_source, standaard 'gkp'). Synoniemen
                                    als 'google' worden genormaliseerd; onbekende waarde valt stil terug
                                    op de vaste bron (geen crash).

        Output:
          source            str        — "keywords_everywhere"
          country           str
          currency          str
          data_source       str
          credits_consumed  int
          credits_remaining int
          keywords          list[dict] — keyword, vol (int), cpc (float), competition (float), trend (list)
        """
        key = context.settings.get("KEYWORDS_EVERYWHERE_API_KEY") or os.getenv("KEYWORDS_EVERYWHERE_API_KEY")
        if not key:
            raise RuntimeError("KEYWORDS_EVERYWHERE_API_KEY ontbreekt in .env — skill faalt bewust closed")

        kw: list[str] = _normalize_kw(payload.get("kw"))
        if not kw:
            raise ValueError("payload['kw'] mag niet leeg zijn")
        if len(kw) > 100:
            raise ValueError(f"payload['kw'] bevat {len(kw)} termen — max 100 per request (caller batcht zelf)")

        country     = payload.get("country", "")          # leeg = global; GEEN 'nl'-default
        currency    = payload.get("currency", "eur")
        # Vaste bron uit settings (x-boven-y-beleid, default 'gkp'); rol-input mag afwijken maar
        # wordt genormaliseerd. Onbekende waarde crasht niet, maar valt terug op de vaste bron.
        default_source = (getattr(context, "settings", {}) or {}).get(
            "keywordseverywhere_data_source", "gkp")
        default_source, _ = resolve_data_source(default_source, "gkp")   # settings zelf ook aliasbaar
        data_source, waarschuwing = resolve_data_source(payload.get("data_source"), default_source)
        if waarschuwing:
            log.warning("Keywords Everywhere: %s", waarschuwing)

        data = [("dataSource", data_source), ("country", country), ("currency", currency)]
        for term in kw:
            data.append(("kw[]", term))

        r = requests.post(
            "https://api.keywordseverywhere.com/v1/get_keyword_data",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            data=data,
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()

        keywords = []
        for item in raw.get("data", []):
            row = {
                "term":        item["keyword"],            # titelveld voor verslag en note
                "keyword":     item["keyword"],
                "vol":         int(item.get("vol") or 0),
                "cpc":         float((item.get("cpc") or {}).get("value") or 0),
                "competition": float(item.get("competition") or 0),
                "trend":       item.get("trend", []),
            }
            row["tekst"] = _rij_tekst(row)
            keywords.append(row)

        out = {
            "source":             "keywords_everywhere",
            "country":            country,
            "currency":           currency,
            "data_source":        data_source,
            "credits_consumed":   int(raw.get("credits_consumed", 0)),
            "credits_remaining":  int(raw.get("credits", 0)),
            "keywords":           keywords,
        }
        if not keywords:
            # Bevraagd, geen volume: een antwoord (📭). Tot scope 55 droegen `currency`/`data_source`
            # hier de "inhoud" en las de wall "eur" als resultaat.
            out["no_data"] = True
            out["reason"] = f"no search volume for {', '.join(kw[:5])}{'…' if len(kw) > 5 else ''}"
            return out
        top = sorted(keywords, key=lambda r: -r["vol"])[:3]
        out["text"] = (f"{len(keywords)} keyword(s) with search volume"
                       f"{' (' + country + ')' if country else ' (global)'}; top: "
                       + "; ".join(f"{r['term']} {r['vol']}/mo" for r in top))
        return out
