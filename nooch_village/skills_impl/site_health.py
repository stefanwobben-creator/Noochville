"""site_health — één echte GET op een publieke pagina: bereikbaar of niet, met status, titel en omvang.

De uitkomst van een health-check is een BEVINDING, geen skill-fout. Tot scope 58 gaf de skill
`ok: r.ok` terug en las de uitvoerlaag `ok is False` als fout: een 404 op de site werd "⚠️ niet
gelukt (fout, poging n): skill leverde geen resultaat" — de statuscode stond er niet bij en het item
bleef eeuwig open (skill-review 12-09-2026). Nu heet dat veld `bereikbaar`, zegt `text` wat er is
("HTTP 404 for … (title 'Not found', 1 KiB)"), en is `error` er alleen voor een echte netwerkfout
of een geweigerde URL.

Elke aangeleverde URL loopt langs `safe_fetch.controleer_url` (geen interne adressen, alleen
http(s)) en de body wordt op `safe_fetch.MAX_BYTES` afgekapt — dezelfde guardrail als de
claims-scan en mobiel_audit, niet een eigen kopie.
"""
from __future__ import annotations
import re
import requests
from nooch_village import safe_fetch
from nooch_village.skills import Skill
from nooch_village.skills_impl.mobiel_audit import DEFAULT_URL     # één plek voor 'de site zelf'
from nooch_village.sleutelmasker import masker

_TITEL_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TIMEOUT = 10
USER_AGENT = "NoochVillage/0.1"


class SiteHealthSkill(Skill):
    name = "site_health"
    cost = "free"
    side_effect_free = True
    description = (
        "Checks whether a public page is reachable with one real HTTP GET: status code, page title and "
        "size. A 404 or 500 is a finding (bereikbaar: false, said in `text`), not a failure; only a "
        "network error or a refused URL is an error. Default URL: the site itself (mobiel_audit_url in "
        "the settings, else https://nooch.earth/)."
    )
    input_schema = ("url: str (optional, default the site itself — `mobiel_audit_url` from the settings, "
                    "else https://nooch.earth/); must start with http:// or https://, public hosts only")
    output_schema = ("url, status_code, bereikbaar (bool, 2xx), title, bytes (capped at safe_fetch.MAX_BYTES), "
                     "text | error + url (network failure, refused URL)")

    @staticmethod
    def _default_url(context) -> str:
        settings = (getattr(context, "settings", None) or {}) if context is not None else {}
        return str(settings.get("mobiel_audit_url") or DEFAULT_URL).strip()

    def validate_payload(self, payload: dict, context) -> list:
        """Een 'url' die geen adres is (een plaatshouder van de planner: "PLACEHOLDER — url uit stap 1")
        hoort bij het PLANNEN te stranden, niet live de deur uit te gaan. Zelfde poort als mobiel_audit
        en haal_pagina."""
        url = str((payload or {}).get("url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            kort = url if len(url) <= 60 else url[:57] + "…"
            return [f"'url' is geen adres maar tekst ({kort!r})"]
        return []

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        url = str(payload.get("url") or "").strip() or self._default_url(context)
        try:
            url = safe_fetch.controleer_url(url)
        except safe_fetch.FetchGeweigerd as e:
            return {"error": f"URL refused: {e}", "url": url, "bereikbaar": False, "status_code": 0}
        except OSError as e:                              # een resolver die zelf omvalt (geen gaierror)
            return {"error": f"URL could not be resolved: {masker(e)[:200]}", "url": url,
                    "bereikbaar": False, "status_code": 0}
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, stream=True)
            body = r.raw.read(safe_fetch.MAX_BYTES, decode_content=True) or b""
            code = int(r.status_code)
        except Exception as e:                            # noqa: BLE001 — netwerk, time-out, DNS, TLS
            # Een echte fout: de bron antwoordde niet. Gemaskeerd, want een requests-fout herhaalt de
            # volledige URL (en bij andere skills de sleutel) in zijn tekst.
            return {"error": f"site check failed for {url}: {type(e).__name__}: {masker(e)[:300]}",
                    "url": url, "bereikbaar": False, "status_code": 0}
        html = body.decode(r.encoding or "utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        m = _TITEL_RE.search(html)
        title = " ".join(m.group(1).split())[:120] if m else ""
        bereikbaar = 200 <= code < 300
        kib = len(body) // 1024
        omvang = f"{kib} KiB" + (" (capped)" if len(body) >= safe_fetch.MAX_BYTES else "")
        text = (f"HTTP {code} for {url} (title {title!r}, {omvang}) — "
                + ("reachable" if bereikbaar else "not reachable"))
        return {"url": url, "status_code": code, "bereikbaar": bereikbaar, "title": title,
                "bytes": len(body), "text": text}
