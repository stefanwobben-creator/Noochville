"""mobiel_audit — een echte Lighthouse-run op mobiel, via Google's PageSpeed Insights API.

Aanleiding (11 september 2026). Het mobiel-project van de Website Developer zat vast op één item:
"Voer een technische audit uit van CSS/HTML-broncode en performance-metrics (bv. Core Web Vitals,
Lighthouse-score) specifiek voor mobiele weergave — ○ no skill". Stefan: "kunnen we deze skill
maken?" En: "de skill is bedoeld voor nooch.earth (eigenlijk de dev-versie die ik via preview
bekijk); wekelijks of dagelijks een soort QA-check van de website."

Dat zijn twee gebruiken van dezelfde meting, en ze zitten allebei in deze klasse:

1. **Op afroep** (`run`): één URL, één Lighthouse-run met `strategy=mobile`; terug komen de vier
   categoriescores, de lab-metrics (LCP, CLS, TBT, FCP, Speed Index), de velddata van echte
   Chrome-gebruikers als Google die heeft (CrUX, p75), de kansen met geschatte winst, en de
   mobiel-specifieke audits (viewport, tikdoelen, lettergrootte) voor zover Lighthouse ze nog kent.
   Dit is het item uit het uitvoerplan, en het is wat Noochie draait als ze een pagina wil wegen.
2. **Als meetbron** (`DataSourceSkill`): de morgenpuls schrijft per periode één punt per veld weg
   (`mobiel_audit_<veld>_day`), zodat een score die zakt zichtbaar is als trend en niet als een
   losse indruk. Standaard wekelijks (`mobiel_audit_frequency`), want de labscore schommelt van
   run tot run tientallen punten; dagelijks kan, maar dan lees je vooral ruis. De URL komt uit
   `mobiel_audit_url` in `config/settings.ini`, en dat mag een Shopify-preview zijn
   (`https://nooch.earth/?preview_theme_id=…`): Google laadt die net als een bezoeker.

Wat deze skill NIET kan, en dat staat hier omdat het de reden is dat het item op een mens wachtte:
een pagina achter een login. PageSpeed ziet wat een anonieme bezoeker ziet. Voor
village.nooch.earth is dat de loginpagina, meer niet; de cockpit erachter meet je met een echte
browser op de repo, niet met een externe dienst.

Fail-closed, geen mock: zonder antwoord van Google is er geen score, en een pagina die Lighthouse
niet kon laden is een `error` met Google's eigen reden, geen nul. Velddata die er niet is, is
`None` per veld: dat is de reden dat de collector die velden gewoon overslaat.

**De key is verplicht, en dat is gemeten.** Google documenteert de API als "werkt zonder key";
in de praktijk delen alle keyless aanroepers wereldwijd één anoniem project, en dat quotum is
op. Stefan, 11 september om 10:40, vanaf zijn Mac, eerste aanroep van de dag: HTTP 429 "Quota
exceeded for quota metric 'Queries' and limit 'Queries per day' … for consumer
'project_number:583797351490'" — niet zijn project. Dus `PAGESPEED_API_KEY` in `.env` (gratis,
25.000 per dag op een eigen Google Cloud-project), anders draait de skill niet: zonder key zegt hij
dat met zoveel woorden in plaats van een 429 te delen. De key gaat mee als parameter en komt NOOIT
in de uitvoer, ook niet in een foutmelding.
"""
from __future__ import annotations

import logging
import os
import time

from nooch_village import safe_fetch
from nooch_village.skills import DataSourceSkill

log = logging.getLogger("village.mobiel_audit")

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
DEFAULT_URL = "https://nooch.earth/"
STRATEGIEEN = ("mobile", "desktop")
CATEGORIEEN = ("performance", "accessibility", "best-practices", "seo")
#: Google's Lighthouse-run duurt gerust 30 tot 60 seconden; korter afkappen geeft alleen valse storingen.
TIMEOUT = 120
MAX_KANSEN = 8
MAX_BEVINDINGEN = 10          # per categorie

#: De lab-metrics die de memo en de meetreeks dragen: (veld, audit-id, eenheid).
_LAB = (("lcp_ms", "largest-contentful-paint", "ms"),
        ("cls", "cumulative-layout-shift", ""),
        ("tbt_ms", "total-blocking-time", "ms"),
        ("fcp_ms", "first-contentful-paint", "ms"),
        ("speed_index_ms", "speed-index", "ms"),
        ("tti_ms", "interactive", "ms"))
#: De velddata (CrUX, p75 over 28 dagen): (veld, PSI-sleutel, deler naar de eenheid van het veld).
#: CLS komt uit de API als percentiel ×100 (5 betekent 0,05).
_VELD = (("veld_lcp_ms", "LARGEST_CONTENTFUL_PAINT_MS", 1),
         ("veld_inp_ms", "INTERACTION_TO_NEXT_PAINT", 1),
         ("veld_cls", "CUMULATIVE_LAYOUT_SHIFT_SCORE", 100),
         ("veld_fcp_ms", "FIRST_CONTENTFUL_PAINT_MS", 1))
#: Mobiel-specifieke audits, voor zover de Lighthouse-versie van Google ze nog kent. Ontbreekt er
#: één, dan staat hij er gewoon niet in — we verzinnen geen oordeel voor een audit die niet draaide.
_MOBIEL = ("viewport", "content-width", "font-size", "tap-targets", "target-size", "meta-viewport")

#: De meetreeks: de score en de drie Core Web Vitals-achtige labwaarden, plus wat het veld zegt.
_METRICS = ("performance", "lcp_ms", "cls", "tbt_ms", "veld_lcp_ms", "veld_inp_ms", "veld_cls")


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _score100(s):
    n = _num(s)
    return None if n is None else int(round(n * 100))


def _pct(x):
    """Getal → nette weergave zonder overbodige decimalen."""
    if x is None:
        return "?"
    return str(int(x)) if float(x).is_integer() else f"{x:.2f}"


class MobielAuditSkill(DataSourceSkill):
    name = "mobiel_audit"
    SOURCE = "mobiel_audit"
    CATALOG_LABEL = "PageSpeed Insights (mobiel)"
    DEFAULT_FREQUENCY = "weekly"
    kind = "flux"                   # de waarde van de meting zelf, geen oplopende stand
    cost = "rate_limited"           # Google's publieke quota; met key ruimer, maar nooit onbegrensd
    side_effect_free = True         # leest alleen; de collector schrijft de observaties, niet de skill
    required_env = ("PAGESPEED_API_KEY",)   # zie de docstring: keyless deelt een uitgeput anoniem quotum
    optional_env = ()
    description = (
        "Runs a real Lighthouse audit on a public page through Google's PageSpeed Insights API, "
        "mobile by default: the four category scores, the lab metrics (LCP, CLS, TBT, FCP, Speed "
        "Index), the field data from real Chrome users when Google has it, the opportunities with "
        "their estimated savings, and the mobile-specific checks (viewport, tap targets, font size). "
        "Also a weekly data source for the metrics board. Needs PAGESPEED_API_KEY; cannot see pages "
        "behind a login."
    )
    input_schema = ("url: str (optioneel — default `mobiel_audit_url` uit de settings, "
                    "https://nooch.earth/; een Shopify-preview met ?preview_theme_id= mag); "
                    "strategie: 'mobile' | 'desktop' (optioneel, default mobile)")
    output_schema = ("ok, url, strategie, lighthouse_versie, gemeten_op, "
                     "scores{performance, accessibility, best_practices, seo} (0-100), "
                     "lab{lcp_ms, cls, tbt_ms, fcp_ms, speed_index_ms, tti_ms}[{waarde, weergave, score}], "
                     "veld{bron: url|origin, oordeel, lcp_ms, inp_ms, cls, fcp_ms} of veld{bron: None, reden}, "
                     "kansen[{audit, titel, winst_ms}], mobiel[{audit, titel, geslaagd, weergave}], "
                     "bevindingen[{categorie, audit, titel, score, weergave, gewicht}] (falende audits, "
                     "per categorie gewogen), lcp_element{element, selector, snippet, fases_ms}, "
                     "waarschuwingen[], text | error + tijdelijk")

    def __init__(self, haal=None, controleer=None):
        # Injecteerbaar zodat een test dit bewijst zonder netwerk en zonder quota, net als `_haal`
        # in haal_pagina. `haal(params) -> (status, json|None)`.
        self._haal = haal or self._standaard_haal
        self._controleer = controleer or safe_fetch.controleer_url

    # ── config ────────────────────────────────────────────────────────────────

    @staticmethod
    def _settings(context) -> dict:
        return (getattr(context, "settings", {}) or {}) if context is not None else {}

    def _key(self, context) -> str:
        return str(self._settings(context).get("PAGESPEED_API_KEY") or os.getenv("PAGESPEED_API_KEY") or "")

    def _url(self, context) -> str:
        return str(self._settings(context).get("mobiel_audit_url") or DEFAULT_URL).strip()

    def frequency(self, field: str) -> str:
        """Wekelijks tenzij `mobiel_audit_frequency = daily` in de settings staat. Een onbekende
        waarde valt terug op wekelijks in plaats van de puls stil te leggen."""
        f = str(self._settings(getattr(self, "_ctx", None)).get("mobiel_audit_frequency") or "").lower()
        return f if f in ("daily", "weekly") else self.DEFAULT_FREQUENCY

    # ── ophalen ───────────────────────────────────────────────────────────────

    @staticmethod
    def _standaard_haal(params: dict):
        import requests
        r = requests.get(PSI_URL, params=params, timeout=TIMEOUT,
                         headers={"User-Agent": "NoochVillage/0.1"})
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, data

    def validate_payload(self, payload: dict, context) -> list:
        """Een 'url' die geen adres is (een plaatshouder van de planner) hoort bij het PLANNEN al te
        stranden, niet pas bij Google. Zelfde poort als haal_pagina."""
        url = str((payload or {}).get("url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            kort = url if len(url) <= 60 else url[:57] + "…"
            return [f"'url' is geen adres maar tekst ({kort!r})"]
        return []

    def _meet(self, url: str, strategie: str, context) -> dict:
        """Eén PageSpeed-run. Geeft óf een geparste uitkomst (ok=True) óf een error-dict."""
        try:
            url = self._controleer(url)
        except safe_fetch.FetchGeweigerd as e:
            return {"error": f"URL geweigerd: {e}", "url": url, "tijdelijk": False}
        key = self._key(context)
        if not key:
            # Bewust geen 'ontbreekt'/'verplicht' in deze zin: dat is de woordkeus van een
            # PAYLOAD-klacht (test_payload_declaratie), en dit is config, geen payload.
            return {"error": "geen PAGESPEED_API_KEY in .env; zonder key deelt deze skill Google's "
                             "anonieme quotum en dat is op (gemeten 11 sep 2026: 429 Queries per day)",
                    "url": url, "tijdelijk": False}
        params = {"url": url, "strategy": strategie, "key": key}
        # requests herhaalt een lijstwaarde als losse parameters: category=performance&category=seo…
        params["category"] = list(CATEGORIEEN)
        try:
            status, data = self._haal(params)
        except Exception as e:                        # noqa: BLE001 — netwerk, time-out, DNS
            # Een requests-fout herhaalt de volledige aanvraag-URL, inclusief `key=`; die mag niet in
            # een logregel, de draaistaat of op een projectmuur belanden.
            msg = str(e).replace(key, "***") if key else str(e)
            return {"error": f"PageSpeed niet bereikbaar: {type(e).__name__}: {msg[:300]}", "url": url,
                    "tijdelijk": True}
        if not isinstance(data, dict):
            return {"error": f"PageSpeed gaf geen JSON (HTTP {status})", "url": url,
                    "tijdelijk": status in (429, 500, 502, 503, 504)}
        if "error" in data:
            fout = data.get("error") or {}
            msg = str(fout.get("message") or fout)[:300]
            return {"error": f"PageSpeed: {msg}", "url": url,
                    "tijdelijk": status in (429, 502, 503, 504) or "quota" in msg.lower()}
        lh = data.get("lighthouseResult") or {}
        rt = lh.get("runtimeError") or {}
        if rt.get("code") and rt.get("code") != "NO_ERROR":
            return {"error": f"Lighthouse: {rt.get('code')}: {str(rt.get('message') or '')[:200]}",
                    "url": url, "tijdelijk": False}
        if not lh.get("categories"):
            return {"error": "PageSpeed gaf een antwoord zonder Lighthouse-resultaat", "url": url,
                    "tijdelijk": True}
        return self._parse(data, url, strategie)

    # ── parsen ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse(data: dict, url: str, strategie: str) -> dict:
        lh = data.get("lighthouseResult") or {}
        audits = lh.get("audits") or {}
        cats = lh.get("categories") or {}
        scores = {"performance": _score100((cats.get("performance") or {}).get("score")),
                  "accessibility": _score100((cats.get("accessibility") or {}).get("score")),
                  "best_practices": _score100((cats.get("best-practices") or {}).get("score")),
                  "seo": _score100((cats.get("seo") or {}).get("score"))}
        lab = {}
        for veld, audit_id, _eenheid in _LAB:
            a = audits.get(audit_id) or {}
            lab[veld] = {"waarde": _num(a.get("numericValue")), "weergave": a.get("displayValue") or "",
                         "score": _num(a.get("score"))}
        veld = MobielAuditSkill._veld(data, url)
        kansen = []
        for aid, a in audits.items():
            det = a.get("details") or {}
            if det.get("type") != "opportunity":
                continue
            winst = _num(det.get("overallSavingsMs")) or 0.0
            bytes_ = _num(det.get("overallSavingsBytes")) or 0.0
            if winst <= 0 and bytes_ <= 0:
                continue                      # zonder geschatte winst is het geen kans maar een bevinding
            kansen.append({"audit": aid, "titel": str(a.get("title") or "")[:120], "winst_ms": int(winst),
                           "winst_bytes": int(bytes_)})
        kansen.sort(key=lambda k: (-k["winst_ms"], -k["winst_bytes"]))
        bevindingen = MobielAuditSkill._bevindingen(lh)
        lcp_element = MobielAuditSkill._lcp_element(audits)
        mobiel = []
        for aid in _MOBIEL:
            a = audits.get(aid)
            if not a or a.get("scoreDisplayMode") in ("notApplicable", "manual", "informative"):
                continue
            s = _num(a.get("score"))
            mobiel.append({"audit": aid, "titel": str(a.get("title") or "")[:120],
                           "geslaagd": None if s is None else s >= 0.9,
                           "weergave": a.get("displayValue") or ""})
        # Het veld heet `finalDisplayedUrl` (gezien in Stefans echte antwoord van 11 sep); de oudere
        # naam blijft als terugval.
        uit = {"ok": True, "url": lh.get("finalDisplayedUrl") or lh.get("finalDisplayUrl") or lh.get("finalUrl") or url,
               "strategie": strategie, "lighthouse_versie": lh.get("lighthouseVersion") or "",
               "gemeten_op": lh.get("fetchTime") or "", "scores": scores, "lab": lab, "veld": veld,
               "kansen": kansen[:MAX_KANSEN], "mobiel": mobiel, "bevindingen": bevindingen,
               "lcp_element": lcp_element,
               "waarschuwingen": [str(w)[:200] for w in (lh.get("runWarnings") or [])[:3]]}
        uit["text"] = MobielAuditSkill._tekst(uit)
        return uit

    @staticmethod
    def _bevindingen(lh: dict) -> list[dict]:
        """Per categorie de audits die FALEN (score < 0.9), gewogen zoals Lighthouse ze weegt.

        De eerste echte run (nooch.earth, 11 sep) gaf performance 58 en best practices 54, met als
        enige 'kans' 330 ms ongebruikte CSS. Dat verklaart geen LCP van 20 seconden en geen 54: de
        verklaring zit in de audits zonder tijdwinst-schatting (render-blokkerend, lazy geladen
        LCP-afbeelding, console-fouten, cookies van derden). Die horen in het rapport, want zonder
        die lijst is de score een cijfer zonder oorzaak. Metrics zelf staan er niet in (die zijn
        `lab`), en niet-scorende audits (informatief, handmatig, n.v.t.) ook niet."""
        audits = lh.get("audits") or {}
        metrics = {a for _, a, _ in _LAB}
        uit = []
        for cat, naam in (("performance", "performance"), ("accessibility", "accessibility"),
                          ("best-practices", "best_practices"), ("seo", "seo")):
            refs = (lh.get("categories") or {}).get(cat, {}).get("auditRefs") or []
            rijen = []
            for ref in refs:
                aid = ref.get("id")
                a = audits.get(aid) or {}
                if aid in metrics or a.get("scoreDisplayMode") in ("notApplicable", "manual", "informative", "error"):
                    continue
                sc = _num(a.get("score"))
                if sc is None or sc >= 0.9:
                    continue
                rijen.append({"categorie": naam, "audit": aid, "titel": str(a.get("title") or "")[:120],
                              "score": sc, "weergave": str(a.get("displayValue") or "")[:80],
                              "gewicht": _num(ref.get("weight")) or 0.0})
            rijen.sort(key=lambda r: (-r["gewicht"], r["score"]))
            uit.extend(rijen[:MAX_BEVINDINGEN])
        return uit

    @staticmethod
    def _lcp_element(audits: dict) -> dict | None:
        """Wélk element de LCP is, en waar de tijd in ging (TTFB, laadvertraging, laadtijd,
        rendervertraging). Dit is het antwoord op "waarom 20 seconden"; zonder dit is LCP een
        getal. Vorm van Lighthouse 10+: details.items[0] = tabel met de node, items[1] = tabel
        met fases. Fail-soft: een andere vorm geeft None, geen fout."""
        a = audits.get("largest-contentful-paint-element") or {}
        items = (a.get("details") or {}).get("items") or []
        if not items:
            return None
        uit = {}
        try:
            node = ((items[0].get("items") or [{}])[0].get("node") or {})
            uit["element"] = str(node.get("nodeLabel") or node.get("snippet") or "")[:160]
            uit["selector"] = str(node.get("selector") or "")[:160]
            uit["snippet"] = str(node.get("snippet") or "")[:200]
        except (AttributeError, IndexError, TypeError):
            pass
        try:
            fases = (items[1].get("items") or []) if len(items) > 1 else []
            uit["fases_ms"] = {str(f.get("phase") or "?"): int(_num(f.get("timing")) or 0) for f in fases}
        except (AttributeError, TypeError):
            pass
        return uit or None

    @staticmethod
    def _veld(data: dict, url: str) -> dict:
        """De velddata: eerst die van de pagina zelf, anders van het domein (origin). Geen van beide =
        te weinig Chrome-verkeer, en dat is een feit over de site, geen storing."""
        for bron, sleutel in (("url", "loadingExperience"), ("origin", "originLoadingExperience")):
            le = data.get(sleutel) or {}
            metrics = le.get("metrics") or {}
            if not metrics:
                continue
            if le.get("origin_fallback"):
                bron = "origin"                   # Google vulde de pagina-velddata met die van het domein
            uit = {"bron": bron, "oordeel": le.get("overall_category") or ""}
            for veld, psi, deler in _VELD:
                m = metrics.get(psi) or {}
                p = _num(m.get("percentile"))
                uit[veld] = None if p is None else (p / deler if deler != 1 else p)
                if m.get("category"):
                    uit[veld + "_oordeel"] = m["category"]
            return uit
        return {"bron": None, "reden": "geen velddata: te weinig Chrome-verkeer voor deze pagina en dit domein"}

    @staticmethod
    def _tekst(u: dict) -> str:
        s = u["scores"]
        lab = u["lab"]
        regels = [f"{u['strategie']}: performance {_pct(s['performance'])}, accessibility "
                  f"{_pct(s['accessibility'])}, best practices {_pct(s['best_practices'])}, SEO {_pct(s['seo'])}."]
        regels.append("Lab: LCP " + (lab["lcp_ms"]["weergave"] or "?") + " · CLS " +
                      (lab["cls"]["weergave"] or "?") + " · TBT " + (lab["tbt_ms"]["weergave"] or "?") + ".")
        v = u["veld"]
        if v.get("bron"):
            regels.append(f"Veld ({v['bron']}, p75): {v.get('oordeel') or '?'}; LCP {_pct(v.get('veld_lcp_ms'))} ms, "
                          f"INP {_pct(v.get('veld_inp_ms'))} ms, CLS {_pct(v.get('veld_cls'))}.")
        else:
            regels.append("Veld: " + v.get("reden", "geen velddata") + ".")
        le = u.get("lcp_element") or {}
        if le.get("element"):
            fases = le.get("fases_ms") or {}
            zwaarste = max(fases.items(), key=lambda kv: kv[1])[0] if fases else ""
            regels.append(f"LCP-element: {le['element']}" + (f" (meeste tijd: {zwaarste})." if zwaarste else "."))
        if u["kansen"]:
            k = u["kansen"][0]
            regels.append(f"Grootste kans: {k['titel']} ({k['winst_ms']} ms).")
        per_cat = {}
        for b in u.get("bevindingen") or []:
            per_cat[b["categorie"]] = per_cat.get(b["categorie"], 0) + 1
        if per_cat:
            regels.append("Falende audits: " + ", ".join(f"{c} {n}" for c, n in per_cat.items()) + ".")
        gefaald = [m["titel"] for m in u["mobiel"] if m["geslaagd"] is False]
        if gefaald:
            regels.append("Mobiel faalt op: " + "; ".join(gefaald) + ".")
        return " ".join(regels)

    # ── op afroep ─────────────────────────────────────────────────────────────

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        url = str(payload.get("url") or "").strip() or self._url(context)
        strategie = str(payload.get("strategie") or payload.get("strategy") or "mobile").lower()
        if strategie not in STRATEGIEEN:
            return {"error": f"onbekende strategie {strategie!r}; kies uit {', '.join(STRATEGIEEN)}",
                    "tijdelijk": False}
        t0 = time.time()
        uit = self._meet(url, strategie, context)
        uit["duur_s"] = round(time.time() - t0, 1)
        return uit

    # ── als meetbron ──────────────────────────────────────────────────────────

    def available_metrics(self, context=None) -> list[str]:
        return list(_METRICS)

    def is_configured(self, context) -> bool:
        self._ctx = context                 # zodat frequency() de settings kan lezen (zie collector)
        return bool(self._key(context))     # de URL heeft een default; de key niet (zie docstring)

    def daily_values(self, context, datum: str) -> dict:
        """Eén run op de geconfigureerde URL; per veld de waarde of None (fail-closed per veld).
        `datum` is de periode-sleutel van de collector; de meting is altijd van nu — dat is wat een
        QA-check is: hoe staat de site er vandaag voor."""
        self._ctx = context
        out = {m: None for m in _METRICS}
        r = self._meet(self._url(context), "mobile", context)
        if not r.get("ok"):
            log.warning("mobiel_audit daily_values (%s): %s", datum, r.get("error"))
            return out
        out["performance"] = r["scores"]["performance"]
        for veld in ("lcp_ms", "cls", "tbt_ms"):
            out[veld] = r["lab"][veld]["waarde"]
        v = r["veld"]
        if v.get("bron"):
            for veld in ("veld_lcp_ms", "veld_inp_ms", "veld_cls"):
                out[veld] = v.get(veld)
        self._laatste = r
        return out

    def observation_meta(self, context, datum: str, field: str) -> dict:
        r = getattr(self, "_laatste", None) or {}
        return {"endpoint": "pagespeedonline/v5", "url": self._url(context), "strategie": "mobile",
                "lighthouse": r.get("lighthouse_versie", ""), "gemeten_op": r.get("gemeten_op", ""),
                "veld_bron": (r.get("veld") or {}).get("bron")}
