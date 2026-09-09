"""web_zoek — zoek op het open web en lees meteen wat je vindt.

WAAROM DEZE SKILL BESTAAT. Op 6 september bleek het dorp niet te kunnen googelen. SerpAPI zat er
drie keer in, maar elke keer vastgeklonken aan één doel: `competitor_discover` zoekt naar merkgidsen,
`linkbuilding` naar linkkandidaten, `claim_evidence` naar één merk plus één claim. Geen van drieën
kan een vrije vraag beantwoorden. `haal_pagina` leest één pagina, maar alleen als je de URL al hebt.
Daartussen zat niets. Een rol die wilde weten wat er over een onderwerp op het web staat, kon dat
alleen via een mens.

WAT HIJ ANDERS DOET DAN "EEN LIJSTJE LINKS". Hij zoekt én leest. Acht links teruggeven verplaatst het
werk alleen maar: de rol moet er dan acht vervolgstappen van maken en de vraag blijft onbeantwoord.
Daarom haalt hij de bovenste paar treffers ook op en geeft hun tekst mee. Eén checklist-item levert
zo een bevinding op in plaats van huiswerk. Wie alleen de lijst wil, zet `lees: 0`.

DE GRENZEN, in dezelfde geest als `haal_pagina`:
- **Alleen lezen.** Geen formulieren, geen login. Het ophalen loopt via `safe_fetch`, met dezelfde
  SSRF-guardrail, backoff en Retry-After als de site-scan.
- **Geen oordeel.** Hij vindt en citeert. Of het klopt bepaalt de lezer, of `claims_check`.
- **Fail-closed op de zoekopdracht.** Geen sleutel of een stukke API is een fout, geen leeg
  resultaat. Anders leest "niets gevonden" hetzelfde als "er is niets".
- **Fail-soft op het lezen.** Een pagina die niet meewerkt (paywall, 403, JS-only) kost zijn eigen
  regel, niet de hele uitkomst; de treffer blijft staan met zijn fragment.
- **`no_data` ≠ storing.** De zoekmachine gaf nul organische treffers is een ANTWOORD. Dat is een
  ander ding dan de zoekmachine niet kunnen bereiken, en het staat hier apart.

TWEE MOTOREN, ÉÉN VORM. SerpAPI (Google) en Brave (eigen index). `settings.web_zoek_bron` kiest:
`auto` (default, probeert op volgorde en valt terug), `serpapi` of `brave`. Welke motor antwoordde
staat in `bron` en op de wall, want twee zoekmachines geven verschillende antwoorden en een uitkomst
zonder afzender is niet te vergelijken met die van vorige week.

KOST GELD. Elke aanroep is een credit plus een paar pagina-fetches, en daarom is dit een
`credits`-skill: de planner ziet dat en kiest hem niet voor iets wat `library_lookup` gratis weet.
"""
from __future__ import annotations

import logging
import os

from nooch_village import safe_fetch, web_read
from nooch_village.skills import Skill

log = logging.getLogger("village.skill.web_zoek")

_DEFAULT_AANTAL = 8
# NEGEN GEVONDEN, DRIE GELEZEN, EN EEN CONCLUSIE ALSOF DE DEKKING COMPLEET WAS. Op 8 september
# strandde het leveranciers-onderzoek precies daarop: van negen treffers werden er drie gelezen, en
# tussen de zes ongelezen zat savon-atlantique.fr — een Franse zeepmaker, in een rapport dat
# concludeerde dat er geen Europese leverancier bestond. De cap was niet fout, de STILTE eromheen
# wel; zie `volledig_gelezen` hieronder. Vijf naar tien, drie naar vijf: een fetch is goedkoop
# vergeleken met een verkeerde conclusie.
_DEFAULT_LEES = 5
_MAX_AANTAL = 20
_MAX_LEES = 10
_TEKST_PER_PAGINA = 3000            # genoeg om de strekking te zien, niet genoeg om de context te vullen
_FRAGMENT = 300

# ── De motoren ───────────────────────────────────────────────────────────────
# Twee zoekmachines, één vorm. `web_read` normaliseert allebei naar
# [{title, link, snippet}], zodat hieronder niets weet wélke er draaide.
#
# Waarom twee. Er is geen gratis officiële deur naar Google meer: Google's eigen Custom Search JSON
# API is dicht voor nieuwe klanten en bestaande klanten moeten er vóór 1 januari 2027 vanaf, en de
# Bing-API is opgeheven. Wat overblijft is betalen. SerpAPI hebben we al (drie skills gebruiken hem);
# Brave heeft een EIGEN index en is per zoekopdracht goedkoper. Welke van de twee de beste antwoorden
# geeft weten we niet, en dat is precies waarom ze allebei aan staan: dat is te meten zodra ze draaien.
_MOTOREN: dict[str, dict] = {
    "serpapi": {"sleutels": ("SERPAPI_API_KEY", "serpapi_api_key"), "env": "SERPAPI_API_KEY",
                "wat": "Google via SerpAPI"},
    "brave": {"sleutels": ("BRAVE_API_KEY", "brave_api_key"), "env": "BRAVE_API_KEY",
              "wat": "Brave's eigen index"},
}
# `auto` (de default) probeert in deze volgorde. SerpAPI eerst omdat we die sleutel al hebben en zijn
# resultaten al kennen uit drie andere skills; Brave is de nieuwe en moet zich eerst bewijzen.
_VOLGORDE = ("serpapi", "brave")


def _int(waarde, default: int, *, minimum: int = 0, maximum: int = 100) -> int:
    try:
        if waarde in (None, ""):
            return default
        return max(minimum, min(int(waarde), maximum))
    except (TypeError, ValueError):
        return default


def _sleutel(context, motor: str) -> str:
    """De sleutel van één motor. Twee schrijfwijzen omdat de settings ze allebei kennen:
    `competitor_discover` leest hoofdletters, `trend_reindex` kleine. Ze hier allebei accepteren is
    twee regels en scheelt een skill die zichtbaar faalt op een verkeerd geschreven sleutelnaam."""
    s = getattr(context, "settings", {}) or {}
    for naam in _MOTOREN[motor]["sleutels"]:
        if str(s.get(naam) or "").strip():
            return str(s[naam]).strip()
    return (os.getenv(_MOTOREN[motor]["env"]) or "").strip()


def _te_proberen(context) -> list[str]:
    """Welke motoren, in welke volgorde. `settings.web_zoek_bron` = auto | serpapi | brave.

    Zelfde patroon als `trend_reindex.source` (pytrends | serpapi | auto), zodat er niet twee manieren
    zijn om hetzelfde te zeggen. Een onbekende waarde valt terug op `auto` in plaats van te weigeren:
    een typfout in de settings mag het onderzoek niet stilleggen."""
    keuze = str((getattr(context, "settings", {}) or {}).get("web_zoek_bron") or "auto").strip().lower()
    if keuze not in _MOTOREN:
        if keuze != "auto":
            log.info("web_zoek: onbekende web_zoek_bron %r — terug naar auto", keuze)
        return list(_VOLGORDE)
    return [keuze]                   # expliciet gekozen: geen terugval, je krijgt wat je vroeg


class WebZoekSkill(Skill):
    name = "web_zoek"
    cost = "credits"               # een zoek-credit (SerpAPI of Brave) + pagina-fetches
    side_effect_free = True        # leest alleen; schrijft niets, publiceert niets
    description = (
        "Searches the open web for a term and returns the real results: title, URL, domain and the "
        "search snippet. Also fetches the top few pages and returns their readable text, so one call "
        "answers a question instead of producing a list of links to open later. Read-only, no "
        "judgement about what it finds."
    )
    input_schema = ("term: str (verplicht — de zoekterm, in de taal waarin je verwacht dat er "
                    "over geschreven wordt); "
                    "aantal: int (optioneel, default 8, max 20 — hoeveel treffers); "
                    "lees: int (optioneel, default 5, max 10 — hoeveel van de bovenste treffers "
                    "ook opgehaald worden; 0 = alleen de lijst. Zoek je naar het BESTAAN van iets "
                    "(leveranciers, spelers, bronnen), zet dit dan hoog: een ongelezen treffer "
                    "telt niet als gecontroleerd); "
                    "land: str (optioneel, bv. 'nl' — landvoorkeur van de zoekmachine); "
                    "taal: str (optioneel, bv. 'en' — taalvoorkeur van de zoekmachine)")
    required_payload = ("term",)
    output_schema = ("ok, term, bron (serpapi|brave), aantal_treffers, "
                     "treffers[{titel, url, domein, fragment, tekst, gelezen, reden}], "
                     "gelezen (int), volledig_gelezen (bool — False betekent dat er treffers "
                     "ONGELEZEN bleven; trek dan geen conclusie over de hele lijst), "
                     "text (voor de wall), teruggevallen_van[] (als de eerste motor "
                     "faalde), no_data + reason (nul treffers) | error")

    def __init__(self, zoek=None, haal=None):
        # Injecteerbaar zodat een test dit kan bewijzen zonder netwerk en zonder credits, net als
        # `_haal` in haal_pagina. `zoek=None` betekent: kies de motor op basis van de settings.
        self._zoek = zoek
        self._haal = haal or safe_fetch.haal_tekst_geduldig

    def validate_payload(self, payload: dict, context) -> list:
        """Is dit een zoekopdracht, of een filter-constructie die geen enkele motor aankan?

        HET GEVAL, 8 september 2026. Het plan schreef als term:
        `kaliumzeep fabrikant Europages Kompass site:europages.nl OR site:kompass.com` — vrije
        tekst plus twee site-filters plus een OR. Dat kwam LEEG terug, en juist die stap moest de
        registers met telefoonnummers opleveren. Hij stond daarna afgevinkt op het bord.

        De oorzaak is een goede instructie, verkeerd uitgevoerd: "gebruik Kompass en Europages"
        werd vertaald naar `site:`-operatoren, terwijl je een register bevraagt door zijn naam
        gewoon in de term te zetten (of door het register zelf te openen). Eén `site:` is een
        precisie-instrument; twee met een OR is geen zoekopdracht meer.

        De reden staat er bij het PLANNEN op, dus de mens ziet wat er mis is voordat er een credit
        aan opgaat."""
        from nooch_village.zoektermen import gestapeld
        reden = gestapeld(str((payload or {}).get("term") or ""))
        return [reden] if reden else []

    # ── de skill ────────────────────────────────────────────────────────────
    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        term = (payload.get("term") or payload.get("vraag") or "").strip()
        if not term:
            return {"error": "ontbrekende parameter: 'term' is verplicht"}

        kandidaten = [(m, _sleutel(context, m)) for m in _te_proberen(context)]
        met_sleutel = [(m, k) for m, k in kandidaten if k]
        if not met_sleutel:
            # Fail-closed: zonder sleutel geen stille lege lijst. Zie de moduletekst.
            gevraagd = ", ".join(_MOTOREN[m]["sleutels"][0] for m, _ in kandidaten)
            return {"error": f"geen zoeksleutel ({gevraagd}) — zoeken kan niet, en een lege uitkomst "
                             f"zou hier gelezen worden als 'er staat niets over op het web'"}

        aantal = _int(payload.get("aantal"), _DEFAULT_AANTAL, minimum=1, maximum=_MAX_AANTAL)
        lees = _int(payload.get("lees"), _DEFAULT_LEES, minimum=0, maximum=_MAX_LEES)
        rauw, bron, fouten = self._zoeken(term, met_sleutel, aantal, payload)
        if bron is None:
            return {"error": "zoeken mislukt: " + "; ".join(fouten), "term": term}

        treffers = []
        for r in (rauw or [])[:aantal]:
            url = (r.get("link") or "").strip()
            if not url:
                continue
            treffers.append({"titel": (r.get("title") or "").strip(),
                             "url": url,
                             "domein": web_read.domain_of(url),
                             "fragment": (r.get("snippet") or "").strip()[:_FRAGMENT],
                             "tekst": "", "gelezen": False, "reden": ""})
        if not treffers:
            # De zoekmachine wérkte en gaf niets terug. Dat is een antwoord, geen storing — precies
            # het onderscheid dat haal_pagina ook maakt.
            return {"ok": True, "term": term, "bron": bron, "aantal_treffers": 0, "treffers": [],
                    "gelezen": 0, "no_data": True,
                    "reason": f"geen organische treffers voor '{term}' via {bron}",
                    "text": f"No results on the open web for “{term}” ({bron})."}

        for t in treffers[:lees]:
            t["tekst"], t["reden"] = self._lees(t["url"])
            t["gelezen"] = bool(t["tekst"])

        gelezen = sum(1 for t in treffers if t["gelezen"])
        # DEKKING IS EEN FEIT, GEEN VOETNOOT. Dezelfde regel als `claims_site_scan.volledig`: wie
        # een conclusie trekt uit een deelverzameling moet kunnen zien DAT het een deelverzameling
        # was. Het stond al in de data (`gelezen` per treffer), maar niet in de tekst die de
        # rapport-schrijver leest, en dus kwam het niet in de conclusie terecht.
        volledig = gelezen == len(treffers)
        uit = {"ok": True, "term": term, "bron": bron, "aantal_treffers": len(treffers),
               "treffers": treffers, "gelezen": gelezen, "volledig_gelezen": volledig,
               "text": _als_tekst(term, treffers, bron, gelezen=gelezen)}
        if fouten:
            # Er is teruggevallen. Dat mag, maar niet stil: twee motoren geven verschillende
            # antwoorden, en wie de uitkomst leest moet kunnen zien dat de andere aan de beurt was.
            uit["teruggevallen_van"] = fouten
        return uit

    def _zoeken(self, term: str, motoren: list, aantal: int, payload: dict):
        """(resultaten, bron, fouten). Probeert de motoren op volgorde.

        Terugvallen gebeurt ALLEEN op `auto`, en dat volgt vanzelf: bij een expliciete keuze staat er
        één motor in de lijst. Dat is met opzet. Vraag je om Brave, dan wil je Brave weten, niet
        stiekem Google. Vraag je niets, dan wil je een antwoord.

        Elke mislukte poging blijft in `fouten` staan, ook als een latere motor slaagt. Een uitkomst
        die er goed uitziet terwijl de eerste motor zonder credits zat is precies het soort stilte
        waar je een maand later achterkomt."""
        fouten = []
        for motor, key in motoren:
            try:
                rauw = self._roep(motor)(term, key, num=aantal,
                                         gl=str(payload.get("land") or "").strip()[:5],
                                         hl=str(payload.get("taal") or "").strip()[:5])
                return rauw, motor, fouten
            except Exception as exc:                      # noqa: BLE001 — nooit de puls breken
                log.warning("web_zoek: %s faalde (%s): %s", motor, term[:60], exc)
                fouten.append(f"{motor}: {type(exc).__name__}: {exc}")
        return [], None, fouten

    def _roep(self, motor: str):
        """De functie die deze motor aanroept. Een geïnjecteerde `zoek` wint altijd — zo bewijst een
        test het gedrag zonder netwerk en zonder credits, precies zoals `_haal` in haal_pagina."""
        if self._zoek is not None:
            return self._zoek
        return web_read.brave_search if motor == "brave" else web_read.serpapi_search

    def _lees(self, url: str) -> tuple[str, str]:
        """(tekst, reden). Fail-soft: een pagina die niet meewerkt kost zijn eigen regel, niet de
        hele zoekopdracht. De reden staat er wél bij, want 'geen tekst' zonder uitleg leest als
        'de pagina was leeg' en dat is bijna nooit wat er aan de hand is."""
        try:
            gehaald = self._haal(url)
        except safe_fetch.FetchGeweigerd as e:
            return "", f"geweigerd: {e}"
        except safe_fetch.FetchMislukt as e:
            return "", f"niet opgehaald: {e}"
        except Exception as e:                            # noqa: BLE001
            return "", f"onverwachte fout: {type(e).__name__}: {e}"
        tekst = (gehaald.get("tekst") or "").strip()
        if not tekst:
            return "", "pagina bevatte geen leesbare tekst (waarschijnlijk JavaScript-only)"
        return tekst[:_TEKST_PER_PAGINA], ""


def _als_tekst(term: str, treffers: list, bron: str = "", gelezen: int | None = None) -> str:
    """De vorm die op de projectwall landt: wat er gezocht is, waar, wat er staat, en van welk domein.

    De motor staat er expliciet bij. Twee zoekmachines geven verschillende antwoorden, en zonder die
    regel is een uitkomst van vandaag niet te vergelijken met een van vorige week.

    Bewust de fragmenten en niet de volledige paginateksten: de wall is om te lezen, de tekst is om
    mee te werken. Wie de hele pagina wil, heeft hem in `treffers[i]["tekst"]`."""
    waar = f" via {bron}" if bron else ""
    if gelezen is None:
        gelezen = sum(1 for t in treffers if t.get("gelezen"))
    kop = f"Searched the open web for “{term}”{waar} — {len(treffers)} results"
    if gelezen < len(treffers):
        # DE ZIN DIE ONTBRAK. Zonder deze regel leest een rapport-schrijver "9 results" en trekt hij
        # een conclusie over negen, terwijl hij er drie kent. Met deze regel staat de onvolledigheid
        # in dezelfde adem als het aantal, en kan hij niet meer per ongeluk over het hoofd worden
        # gezien. Zelfde reparatie als `volledig=False` bij de claims-scan.
        kop += (f", of which {gelezen} were read in full. COVERAGE IS INCOMPLETE: "
                f"{len(treffers) - gelezen} result(s) were listed but NOT read, so nothing can be "
                f"concluded about them. Absence in this list is not evidence of absence")
    regels = [kop + "."]
    for t in treffers:
        kop = f"• {t['titel'] or t['url']} ({t['domein']})"
        staart = t["fragment"] or ("read in full" if t["gelezen"] else t["reden"])
        regels.append(f"{kop}\n  {staart}" if staart else kop)
    return "\n".join(regels)
