"""lead_beoordeling — zoek de site van een lead op, lees hem, en zeg met een citaat of hij past.

WAAROM DEZE SKILL BESTAAT (12 september 2026). Stefan legde het lijmvrij-verslag naast zijn eigen
Google-ronde en vroeg: "waarom kan AI niet zelf een site via Google opzoeken en bekijken?" Het dorp
kon zoeken (`web_zoek`) en lezen (`haal_pagina`), maar niet wat een mens dáárna doet: een naam die in
een tekst opduikt opnieuw googelen, de eigen site openen, en beslissen of dit iets is. Een lijst
links is geen bevinding; een lead is pas een lead als iemand hem heeft bekeken en beoordeeld. Dit is
die stap, als gereedschap.

WAT HIJ DOET, in de volgorde van een mens:
1. **Opzoeken.** Geen `url`? Dan zoekt hij de naam op (via `web_zoek`, dus met dezelfde motoren en
   dezelfde fail-closed regels) en neemt de eerste treffer die niet van een verzamelsite komt
   (Wikipedia, LinkedIn, marktplaatsen). Welke treffer het werd staat in `gevonden_via`, zodat een
   verkeerde keuze zichtbaar is en geen stille aanname.
2. **Lezen.** De pagina via `safe_fetch` (SSRF-guardrail, backoff), tot `_MAX_TEKST` tekens.
3. **Beoordelen.** Eén modelronde: wat is dit, per criterium uit de opdracht ja/nee/onbekend mét het
   zinnetje van de pagina dat het draagt, een oordeel hoog/midden/laag, en de volgende stap
   (contact, sample, read_more, discard).

DE REGEL DIE HET OORDEEL EERLIJK HOUDT: **geen ja of nee zonder citaat.** Een verdict zonder een
letterlijke zin van de pagina wordt ná het model deterministisch teruggezet naar `unknown`. Het
model mag vinden wat het wil; alleen wat het kan aanwijzen telt. Zelfde gedachte als `grond` in de
wiki: een oordeel is een vergelijking met bewijs, geen stempel.

GEEN CIJFER. Stefan (12 sep): "dat cijfer hoeft niet." Hoog/midden/laag plus een reden en een
volgende stap is wat een mens nodig heeft om te beslissen; een getal zou daar precisie aan
toevoegen die er niet is.

FAIL-CLOSED. Geen site gevonden, pagina niet leesbaar, model geeft onzin: een `error`, geen
`no_data`. Een lead die niet beoordeeld kón worden is iets anders dan een lead die niet past, en de
uitvoerlus laat het item dan open (poging tellen) in plaats van het als antwoord af te vinken.
"""
from __future__ import annotations

import json
import logging
import re

from nooch_village import safe_fetch, web_read
from nooch_village.skills import Skill

log = logging.getLogger("village.skill.lead_beoordeling")

_MAX_TEKST = 6000                 # meer dan web_zoek per pagina (3000): hier gaat het om déze ene site
_MAX_CRITERIA = 8
_MAX_CITAAT = 300
_ZOEK_AANTAL = 5

#: Verzamelsites: een treffer hiervandaan is zelden de eigen site van de lead. De eerste treffer
#: die hier NIET in staat wint; staan ze er allemaal in, dan de eerste met `site_onzeker`.
VERZAMELSITES = (
    "wikipedia.org", "wikidata.org", "linkedin.com", "facebook.com", "instagram.com", "youtube.com",
    "twitter.com", "x.com", "tiktok.com", "pinterest.", "reddit.com", "medium.com", "quora.com",
    "amazon.", "alibaba.com", "aliexpress.com", "ebay.", "etsy.com", "bol.com", "zalando.",
    "europages.", "kompass.com", "crunchbase.com", "bloomberg.com", "reuters.com", "glassdoor.",
    "indeed.", "trustpilot.com", "yelp.", "tripadvisor.", "researchgate.net", "sciencedirect.com",
    "springer.com", "mdpi.com", "semanticscholar.org", "google.", "bing.com", "duckduckgo.com",
)

FIT = ("high", "medium", "low")
VOLGENDE = ("contact", "sample", "read_more", "discard")
VERDICT = ("yes", "no", "unknown")


def _verzamelsite(domein: str) -> bool:
    d = (domein or "").lower()
    return any(v in d for v in VERZAMELSITES)


def kies_site(treffers: list[dict]) -> tuple[str, bool]:
    """(url, onzeker) uit een lijst zoektreffers: de eerste die geen verzamelsite is. Leeg als er
    niets is. `onzeker` = alleen verzamelsites gevonden; dan tóch de eerste, maar gemarkeerd."""
    for t in treffers or []:
        url = str(t.get("url") or t.get("link") or "").strip()
        if url and not _verzamelsite(t.get("domein") or web_read.domain_of(url)):
            return url, False
    for t in treffers or []:
        url = str(t.get("url") or t.get("link") or "").strip()
        if url:
            return url, True
    return "", False


def _json_uit(rauw):
    tekst = str(rauw or "").strip()
    if not tekst:
        return None
    tekst = re.sub(r"^```(?:json)?|```$", "", tekst, flags=re.M).strip()
    try:
        return json.loads(tekst)
    except Exception:                                    # noqa: BLE001
        m = re.search(r"\{.*\}", tekst, re.S)
        try:
            return json.loads(m.group()) if m else None
        except Exception:                                # noqa: BLE001
            return None


def _kort(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _prompt(naam: str, url: str, vraag: str, opdracht: str, criteria: list[str], tekst: str) -> str:
    crit = ("Assess these criteria, in this order: " + "; ".join(criteria) + ".\n") if criteria else (
        "Derive the criteria from the ASSIGNMENT if it names any; otherwise use the single "
        "criterion 'relevant to the question'.\n")
    return (
        "You assess ONE lead for a research question, using ONLY the page text below.\n\n"
        f"QUESTION: {_kort(vraag, 300) or '(not given)'}\n"
        f"ASSIGNMENT: {_kort(opdracht, 600) or '(none)'}\n"
        f"LEAD: {_kort(naam, 120) or '(unnamed)'} — {url}\n\n"
        f"PAGE TEXT (truncated):\n{tekst[:_MAX_TEKST]}\n\n"
        + crit +
        "HARD RULES: a 'yes' or 'no' needs a verbatim sentence from the page as its quote; without "
        "one, answer 'unknown'. Do not invent names, numbers or claims. If the page does not address "
        "the question, say so in what_is_this and set fit to low. Write in English; quotes stay in "
        "the language of the page.\n\n"
        "Answer ONLY with JSON, exactly this shape:\n"
        '{"what_is_this": "<one line: who or what this is, country if stated, and the kind: company, '
        'supplier, manufacturer, brand, institute, paper, blog, register or other>", '
        '"criteria": [{"criterion": "<name>", "verdict": "yes|no|unknown", "quote": "<verbatim or empty>"}], '
        '"fit": "high|medium|low", "why": "<one sentence>", '
        '"next_step": "contact|sample|read_more|discard", '
        '"quote": "<the single most telling sentence from the page, verbatim>"}'
    )


class LeadBeoordelingSkill(Skill):
    name = "lead_beoordeling"
    cost = "credits"               # een zoek-credit als de url ontbreekt, plus een pagina-fetch
    side_effect_free = True        # leest en oordeelt; schrijft niets
    description = (
        "Looks up the website of one lead (a company, product, institute or brand) by name or URL, "
        "reads it and assesses it against the question and the assignment's criteria: what it is, "
        "yes/no/unknown per criterion with a verbatim quote, a fit (high/medium/low), why, and the "
        "next step (contact, sample, read_more, discard). No yes or no without a quote."
    )
    input_schema = ("naam: str (the lead as it appeared in a finding, e.g. 'Kiilto Biomelt'); "
                    "url: str (optional — the lead's own page if already known; leave EMPTY to search "
                    "by name, never a placeholder); "
                    "vraag: str (optional — the project goal); "
                    "opdracht: str (optional — the human's assignment with the criteria); "
                    "criteria: list[str] (optional — the criteria to assess, e.g. "
                    "['plastic-free', 'vegan', 'proven in footwear', 'available in the EU'])")
    required_payload = (("naam", "url"),)
    output_schema = ("ok, naam, url, gevonden_via (url|zoek:<bron>), site_onzeker (bool), "
                     "wat_is_dit, oordeel (high|medium|low), waarom, volgende_stap, citaat, "
                     "beoordeling[{criterium, oordeel, citaat}], text (voor de wall) | error")

    def __init__(self, zoek=None, haal=None, reason_fn=None):
        # Alle drie injecteerbaar, zodat een test de keten bewijst zonder netwerk, zonder credits
        # en zonder model — dezelfde afspraak als `web_zoek` (zoek, haal) en `deliverable_kop`
        # (reason_fn). `zoek` is de web_zoek-skill of iets met dezelfde `run`.
        self._zoek = zoek
        self._haal = haal or safe_fetch.haal_tekst_geduldig
        self._reason = reason_fn

    def validate_payload(self, payload: dict, context) -> list:
        """Een url die geen adres is (de PLACEHOLDER van 8 september) wordt bij het PLANNEN al
        geweigerd; zonder url zoekt de skill zelf, dus de planner hoeft niets te verzinnen."""
        url = str((payload or {}).get("url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            kort = url if len(url) <= 60 else url[:57] + "…"
            return [f"'url' is geen adres maar tekst ({kort!r}) — laat 'url' leeg, dan zoekt de "
                    f"skill de site zelf op de naam"]
        return []

    # ── de skill ────────────────────────────────────────────────────────────
    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        naam = str(payload.get("naam") or "").strip()
        url = str(payload.get("url") or "").strip()
        if not naam and not url:
            return {"error": "ontbrekende parameter: 'naam' of 'url' is verplicht"}
        vraag = str(payload.get("vraag") or "").strip()
        opdracht = str(payload.get("opdracht") or "").strip()
        criteria = [str(c).strip() for c in (payload.get("criteria") or []) if str(c).strip()][:_MAX_CRITERIA]

        gevonden_via, onzeker = "url", False
        if not url:
            url, bron, onzeker, fout = self._zoek_site(naam, context)
            if not url:
                return {"error": f"geen site gevonden voor '{naam}': {fout}", "naam": naam}
            gevonden_via = f"zoek:{bron}"

        tekst, fout = self._lees(url)
        if not tekst:
            return {"error": f"site niet leesbaar ({url}): {fout}", "naam": naam, "url": url,
                    "gevonden_via": gevonden_via}

        data = self._beoordeel(naam or web_read.domain_of(url), url, vraag, opdracht, criteria, tekst,
                               ladder=(str(payload.get("ladder") or "").strip() or None))
        if data is None:
            return {"error": "geen oordeel: het model gaf geen bruikbaar antwoord", "naam": naam,
                    "url": url, "gevonden_via": gevonden_via}

        rijen, teruggezet = _rijen(data, criteria)
        oordeel = str(data.get("fit") or "").strip().lower()
        oordeel = oordeel if oordeel in FIT else "low"
        volgende = str(data.get("next_step") or "").strip().lower()
        volgende = volgende if volgende in VOLGENDE else ("read_more" if oordeel != "low" else "discard")
        citaat = _kort(data.get("quote"), _MAX_CITAAT)
        wat = _kort(data.get("what_is_this"), 240)
        waarom = _kort(data.get("why"), 240)
        uit = {"ok": True, "naam": naam or web_read.domain_of(url), "url": url,
               "gevonden_via": gevonden_via, "site_onzeker": onzeker,
               "wat_is_dit": wat, "oordeel": oordeel, "waarom": waarom, "volgende_stap": volgende,
               "citaat": citaat, "beoordeling": rijen}
        if teruggezet:
            uit["zonder_citaat_teruggezet"] = teruggezet
        uit["text"] = _als_tekst(uit)
        return uit

    def _zoek_site(self, naam: str, context) -> tuple[str, str, bool, str]:
        """(url, bron, onzeker, fout). Zoekt de naam via web_zoek (zelfde motoren, zelfde
        fail-closed regels: geen sleutel is een fout, geen leeg antwoord)."""
        zoek = self._zoek
        if zoek is None:
            from nooch_village.skills_impl.web_zoek import WebZoekSkill
            zoek = WebZoekSkill()
        try:
            uit = zoek.run({"term": naam, "aantal": _ZOEK_AANTAL, "lees": 0}, context)
        except Exception as exc:                          # noqa: BLE001 — nooit de puls breken
            return "", "", False, f"zoeken mislukt: {type(exc).__name__}: {exc}"
        if not isinstance(uit, dict) or uit.get("error"):
            return "", "", False, str((uit or {}).get("error") or "zoeken gaf niets terug")
        url, onzeker = kies_site(uit.get("treffers") or [])
        if not url:
            return "", str(uit.get("bron") or ""), False, "nul treffers op de naam"
        return url, str(uit.get("bron") or "?"), onzeker, ""

    def _lees(self, url: str) -> tuple[str, str]:
        try:
            gehaald = self._haal(url)
        except safe_fetch.FetchGeweigerd as e:
            return "", f"geweigerd: {e}"
        except safe_fetch.FetchMislukt as e:
            return "", f"niet opgehaald: {e}"
        except Exception as e:                            # noqa: BLE001
            return "", f"onverwachte fout: {type(e).__name__}: {e}"
        tekst = (gehaald.get("tekst") or "").strip() if isinstance(gehaald, dict) else ""
        if not tekst:
            return "", "pagina bevatte geen leesbare tekst (waarschijnlijk JavaScript-only)"
        titel = (gehaald.get("titel") or "").strip() if isinstance(gehaald, dict) else ""
        return (f"{titel}\n{tekst}" if titel else tekst)[:_MAX_TEKST], ""

    def _beoordeel(self, naam, url, vraag, opdracht, criteria, tekst, *, ladder=None):
        """Eén modelronde. `ladder` komt uit de payload (dezelfde afspraak als `tegenspraak`); leeg
        = de dorpsladder. Geen model of onzin terug → None, en de caller maakt er een fout van."""
        reason_fn = self._reason
        if reason_fn is None:
            from nooch_village.llm import reason as reason_fn        # noqa: PLC0415 — lazy, testbaar
        prompt = _prompt(naam, url, vraag, opdracht, criteria, tekst)
        try:
            rauw = reason_fn(prompt, json_mode=True, max_tokens=900, call_site="skill_lead_beoordeling",
                             ladder=ladder)
        except Exception as exc:                          # noqa: BLE001
            log.warning("lead_beoordeling: model faalde voor %s: %s", naam, exc)
            return None
        data = _json_uit(rauw)
        return data if isinstance(data, dict) else None


def _rijen(data: dict, criteria: list[str]) -> tuple[list[dict], int]:
    """De beoordeling als records: eerst 'what is this', dan per criterium, dan het oordeel. Een
    ja/nee zonder citaat wordt hier 'unknown' — dit is de vangrail, niet de prompt."""
    rijen = [{"criterium": "what is this", "oordeel": _kort(data.get("what_is_this"), 240), "citaat": ""}]
    teruggezet = 0
    gezien = set()
    for c in (data.get("criteria") or [])[:_MAX_CRITERIA]:
        if not isinstance(c, dict):
            continue
        naam = _kort(c.get("criterion"), 80)
        if not naam or naam.lower() in gezien:
            continue
        gezien.add(naam.lower())
        verdict = str(c.get("verdict") or "").strip().lower()
        verdict = verdict if verdict in VERDICT else "unknown"
        citaat = _kort(c.get("quote"), _MAX_CITAAT)
        if verdict in ("yes", "no") and not citaat:
            verdict = "unknown"
            teruggezet += 1
        rijen.append({"criterium": naam, "oordeel": verdict, "citaat": citaat})
    # criteria die de opdracht noemde maar het model oversloeg: expliciet onbekend, niet stil weg
    for c in criteria:
        if c.lower() not in gezien:
            rijen.append({"criterium": c, "oordeel": "unknown", "citaat": ""})
    fit = str(data.get("fit") or "").strip().lower()
    fit = fit if fit in FIT else "low"
    volgende = str(data.get("next_step") or "").strip().lower()
    volgende = volgende if volgende in VOLGENDE else ("read_more" if fit != "low" else "discard")
    rijen.append({"criterium": "fit", "oordeel": f"{fit} — {_kort(data.get('why'), 200)}".rstrip(" —"),
                  "citaat": _kort(data.get("quote"), _MAX_CITAAT), "volgende_stap": volgende})
    return rijen, teruggezet


def _als_tekst(uit: dict) -> str:
    """De vorm voor de wall: één regel oordeel, dan de criteria met hun citaat."""
    kop = (f"Assessed {uit['naam']} ({uit['url']}, found via {uit['gevonden_via']}"
           f"{', site uncertain' if uit.get('site_onzeker') else ''}): "
           f"{uit['oordeel']} fit — {uit['waarom'] or uit['wat_is_dit']}. Next: {uit['volgende_stap']}.")
    regels = [kop]
    for r in uit.get("beoordeling") or []:
        regel = f"• {r['criterium']}: {r['oordeel']}"
        if r.get("citaat"):
            regel += f" — “{r['citaat']}”"
        regels.append(regel)
    if uit.get("zonder_citaat_teruggezet"):
        regels.append(f"({uit['zonder_citaat_teruggezet']} verdict(s) had no quote and were set to unknown)")
    return "\n".join(regels)
