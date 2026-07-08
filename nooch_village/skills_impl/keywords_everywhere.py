from __future__ import annotations
import logging, os
import requests
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_VALID_DATA_SOURCES = {"gkp", "cli"}
_BATCH = 100                       # KE: max 100 keywords per call (1 credit per keyword)


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


class KeywordsEverywhereSkill(DataSourceSkill):
    name = "keywords_everywhere"
    SOURCE = "keywordseverywhere"
    # Flux-bron: zoekvolume is een niveau (geen cumulatieve stand) → de tegel toont de waarde/lijn zelf.
    # Weekly: KE-volume is een maand-gemiddelde, weekly meten is ruim voldoende.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    needs_secret = True
    cost = "credits"
    required_env = ("KEYWORDS_EVERYWHERE_API_KEY",)
    side_effect_free = True
    description = "Haalt echte search volume, CPC, competitie en 12-maands trend per keyword uit de Keywords Everywhere API (geen mock)."

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
          data_source str        — "gkp" (default) of "cli"; andere waarde → ValueError

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

        kw: list[str] = payload.get("kw", [])
        if not kw:
            raise ValueError("payload['kw'] mag niet leeg zijn")
        if len(kw) > 100:
            raise ValueError(f"payload['kw'] bevat {len(kw)} termen — max 100 per request (caller batcht zelf)")

        country     = payload.get("country", "")          # leeg = global; GEEN 'nl'-default
        currency    = payload.get("currency", "eur")
        data_source = payload.get("data_source", "gkp")
        if data_source not in _VALID_DATA_SOURCES:
            raise ValueError(f"Onbekende data_source '{data_source}' — kies 'gkp' of 'cli'")

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

        keywords = [
            {
                "keyword":     item["keyword"],
                "vol":         int(item.get("vol") or 0),
                "cpc":         float((item.get("cpc") or {}).get("value") or 0),
                "competition": float(item.get("competition") or 0),
                "trend":       item.get("trend", []),
            }
            for item in raw.get("data", [])
        ]

        return {
            "source":             "keywords_everywhere",
            "country":            country,
            "currency":           currency,
            "data_source":        data_source,
            "credits_consumed":   int(raw.get("credits_consumed", 0)),
            "credits_remaining":  int(raw.get("credits", 0)),
            "keywords":           keywords,
        }
