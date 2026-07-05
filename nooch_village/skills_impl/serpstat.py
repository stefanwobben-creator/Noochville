"""SerpstatSkill — domein-zichtbaarheid (organisch) uit de Serpstat API.

Meet de domein-BREDE organische SEO-stand van het eigen domein (curator-instelbaar via
`serpstat_domain`, default nooch.earth) — GEEN per-keyword volume (dat doet Keywords Everywhere;
dubbele meting en dubbele kosten vermeden). Betaalde API met credit-limieten: token vereist, en één
call per run (`SerpstatDomainProcedure.getDomainsInfo`).

Velden (available_metrics):
  keywords   — aantal organische keywords waarvoor het domein rankt (Serpstat 'keywords')
  traffic    — geschatte organische maandtraffic (Serpstat 'traff')
  visibility — Serpstat-zichtbaarheidsindex (positie-gewogen aanwezigheid, Serpstat 'visible')

Fail-closed per veld: geen token / API-fout / domein niet in respons → None (geen mock).
"""
from __future__ import annotations
import logging
import os
import urllib.parse

import requests

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.serpstat.com/v4/"


class SerpstatSkill(DataSourceSkill):
    name = "serpstat_domain"
    SOURCE = "serpstat"
    # Flux-bron: zichtbaarheid/keyword-count/traffic zijn niveaus op een moment (geen cumulatieve stand)
    # → de tegel toont de waarde/lijn zelf. Weekly: SEO-zichtbaarheid beweegt traag.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    needs_secret = True
    cost = "credits"
    required_env = ("SERPSTAT_API_TOKEN",)
    description = ("Domein-zichtbaarheid (organisch): rankende keywords, geschatte traffic en "
                   "zichtbaarheidsindex voor het eigen domein via de Serpstat API (geen mock).")

    def available_metrics(self, context=None) -> list[str]:
        """Vaste domein-metrics (het domein is het subject, de metrics zijn vast — geen keyword-volume)."""
        return ["keywords", "traffic", "visibility"]

    def is_configured(self, context) -> bool:
        """Betaalde API met credits → token vereist. Geen token = 'niet geconfigureerd' (los van 'dood')."""
        s = getattr(context, "settings", {}) or {}
        return bool(s.get("SERPSTAT_API_TOKEN") or os.getenv("SERPSTAT_API_TOKEN"))

    def _call(self, token: str, domain: str, se: str) -> dict:
        """Eén JSON-RPC-call naar getDomainsInfo (één domein). Aparte functie zodat tests 'm injecteren."""
        r = requests.post(
            _ENDPOINT + "?token=" + urllib.parse.quote(token),
            json={"id": "1", "method": "SerpstatDomainProcedure.getDomainsInfo",
                  "params": {"domains": [domain], "se": se}},
            timeout=20)
        r.raise_for_status()
        return r.json()

    def daily_values(self, context, datum: str, *, _post=None) -> dict:
        """Domein-zichtbaarheid voor het geconfigureerde domein, in één call. Fail-closed per veld: geen
        token / API-fout / geen domein-rij → None (geen mock). `datum` is het periode-label (weekly)."""
        out = {"keywords": None, "traffic": None, "visibility": None}
        s = getattr(context, "settings", {}) or {}
        token = s.get("SERPSTAT_API_TOKEN") or os.getenv("SERPSTAT_API_TOKEN")
        if not token:
            return out
        domain = (s.get("serpstat_domain") or "nooch.earth").strip()
        se = (s.get("serpstat_se") or "g_nl").strip()
        try:
            data = (_post or self._call)(token, domain, se)
        except Exception as exc:
            log.warning("Serpstat daily_values faalde (%s): %s", domain, exc)
            return out
        result = (data or {}).get("result") or {}
        rows = result.get("data") or []
        if not rows:
            return out                    # domein (nog) niet in Serpstat's index → None (geen 'dood')
        row = rows[0]
        out["keywords"] = int(row.get("keywords") or 0)
        out["traffic"] = int(row.get("traff") or 0)
        out["visibility"] = float(row.get("visible") or 0.0)
        left = (result.get("summary_info") or {}).get("left_lines")
        if left is not None:
            log.info("Serpstat: %s (%s) → keywords=%s traff=%s visible=%s | credits over: %s",
                     domain, se, out["keywords"], out["traffic"], out["visibility"], left)
        return out

    def run(self, payload: dict, context) -> dict:
        """Ad-hoc domein-info (payload['domain'] of de config), zelfde call. Fail-closed."""
        s = getattr(context, "settings", {}) or {}
        token = s.get("SERPSTAT_API_TOKEN") or os.getenv("SERPSTAT_API_TOKEN")
        if not token:
            return {"error": "SERPSTAT_API_TOKEN ontbreekt in .env -> skill faalt closed"}
        domain = (payload.get("domain") or s.get("serpstat_domain") or "nooch.earth").strip()
        se = (payload.get("se") or s.get("serpstat_se") or "g_nl").strip()
        try:
            data = (payload.get("_post") or self._call)(token, domain, se)
        except Exception as exc:
            return {"error": f"Serpstat-call mislukt: {exc}"}
        rows = ((data or {}).get("result") or {}).get("data") or []
        return {"domain": domain, "se": se, "data": rows}
