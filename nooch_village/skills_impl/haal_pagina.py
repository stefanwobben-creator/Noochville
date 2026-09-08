"""haal_pagina — een publieke pagina ophalen en de zin rond een term teruggeven.

Waarom deze skill bestaat: op 5 september stonden **22 projecten** stil op precies één handeling,
"haal de FAQ-pagina op en geef de zin waarin 'natural' staat". Compliance vroeg het aan Website
Watcher, die aan Library, die terug aan Website Watcher; vijf keer "fetch live Nooch FAQ page",
vijf keer "confirm exact location", van 16 augustus tot 1 september. De escalatie-router deed zijn
werk (eigenaarschap vóór gereedschap), maar geen enkele rol droeg een skill die een URL ophaalt.
De capaciteit lag er wél: `safe_fetch` met SSRF-guardrail, backoff en Retry-After, gebruikt door
`claims_site_scan` en `regulation_watch`. Er was alleen geen skill die hem als gereedschap aanbood.

Grenzen, in dezelfde geest als de rest:
- **Alleen lezen.** Geen formulieren, geen login, geen POST. `safe_fetch.controleer_url` weigert
  privé-adressen en niet-http(s)-schema's.
- **Fail-closed.** Een netwerkfout is een fout, geen lege uitkomst; `tijdelijk` zegt of opnieuw
  proberen zin heeft. Nooit verzonnen tekst.
- **`no_data` ≠ nul.** Pagina opgehaald maar de term staat er niet is iets anders dan de pagina
  niet kunnen ophalen. Het eerste is een antwoord, het tweede is een storing.
- **Geen oordeel.** Deze skill vindt en citeert; of een claim mag, bepaalt `claims_check` onder de
  domeinhouder.
"""
from __future__ import annotations

import re

from nooch_village import safe_fetch
from nooch_village.skills import Skill

_DEFAULT_CONTEXT_REGELS = 2
_DEFAULT_MAX_TREFFERS = 10
_DEFAULT_MAX_TEKENS = 4000
_MAX_REGEL = 600                    # één regel in de uitvoer; langer is geen citaat meer


def _int(waarde, default: int, *, minimum: int = 0, maximum: int = 10_000) -> int:
    try:
        if waarde in (None, ""):
            return default
        return max(minimum, min(int(waarde), maximum))
    except (TypeError, ValueError):
        return default


def _kort(s: str, n: int = _MAX_REGEL) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def zoek_treffers(tekst: str, term: str, *, context_regels: int, max_treffers: int) -> list[dict]:
    """Regels waarin `term` voorkomt, elk met de regels ervoor en erna.

    Op regels, niet op zinnen: `safe_fetch.naar_tekst` levert de pagina al als regels, en een kop
    is daarin een eigen regel. De context bevat dus meestal het kopje waar de treffer onder staat,
    zonder dat deze skill hoeft te raden wat een sectie is. Raden zou valse precisie zijn.
    """
    regels = [r for r in (tekst or "").split("\n") if r.strip()]
    naald = (term or "").casefold()
    treffers = []
    for i, regel in enumerate(regels):
        if naald and naald in regel.casefold():
            treffers.append({
                "regel": _kort(regel),
                "regelnummer": i + 1,
                "voor": [_kort(r, 200) for r in regels[max(0, i - context_regels):i]],
                "na": [_kort(r, 200) for r in regels[i + 1:i + 1 + context_regels]],
            })
            if len(treffers) >= max_treffers:
                break
    return treffers


class HaalPaginaSkill(Skill):
    name = "haal_pagina"
    cost = "rate_limited"          # publieke pagina, beleefde backoff via safe_fetch
    side_effect_free = True        # leest alleen; schrijft niets, publiceert niets
    description = ("Haalt een publieke webpagina op en geeft de leesbare tekst terug, of, met een "
                   "term erbij, elke regel waarin die term voorkomt met de regels eromheen als "
                   "context. Alleen lezen, fail-closed, geen oordeel over de inhoud.")
    input_schema = ("url: str (verplicht — http(s), publiek adres); "
                    "term: str (optioneel — geef alleen de regels rond deze term); "
                    "context_regels: int (optioneel, default 2); "
                    "max_treffers: int (optioneel, default 10); "
                    "max_tekens: int (optioneel, default 4000 — alleen zonder term)")
    required_payload = ("url",)
    output_schema = ("ok, url, status, titel, term, aantal_treffers, "
                     "treffers[{regel, regelnummer, voor[], na[]}], tekst (alleen zonder term), "
                     "afgekapt, no_data + reason (term niet gevonden), error + tijdelijk (bij storing)")

    def __init__(self, haal=None):
        # Injecteerbaar zodat een test de skill kan bewijzen zonder netwerk, net als `_fetch`
        # in safe_fetch zelf.
        self._haal = haal or safe_fetch.haal_tekst_geduldig

    def validate_payload(self, payload: dict, context) -> list:
        """Is dit een URL, of een belofte dat er ooit een URL komt?

        HET GEVAL, 8 september 2026. De planner schreef letterlijk
        `{"url": "PLACEHOLDER — to be filled with each candidate URL found in prior steps"}` en zette
        er de reden bij dat hij hem nog niet kon weten: die stap gebruikt de uitkomst van een
        eerdere stap, en het planformaat kent die afhankelijkheid niet. Dus verzon hij een
        plaatshouder en hoopte dat iemand hem zou invullen.

        Beide bestaande poorten lieten dat door. `_missing_required` kijkt alleen of het VELD er is,
        en dat is een niet-lege string. `_payload_issues` roept déze methode aan, maar die bestond
        hier niet en de basisklasse geeft `[]` terug. Er stond dus iemand bij de deur die nooit iets
        tegenhield. Gevolg: het item werd uitvoerbaar bevonden, faalde in 0,00 seconden, bleef open,
        en het project bleef "the role is working" tonen.

        Fail-fast bij het PLANNEN is hier het hele punt: dan staat de reden op de kaart en weet de
        mens dat die stap op hem wacht, in plaats van dat er elke dag iets stilletjes omvalt."""
        rauw = (payload or {}).get("url")
        url = str(rauw or "").strip()
        if not url:
            return []                                    # afwezigheid dekt `required_payload` al
        if not url.lower().startswith(("http://", "https://")):
            kort = url if len(url) <= 60 else url[:57] + "…"
            return [f"'url' is geen adres maar tekst ({kort!r}) — een stap die de URL pas uit een "
                    f"eerdere stap kan halen, hoort een mens-taak te zijn of te wachten"]
        return []

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        url = (payload.get("url") or "").strip()
        if not url:
            return {"error": "ontbrekende parameter: 'url' is verplicht"}
        term = (payload.get("term") or "").strip()

        try:
            gehaald = self._haal(url)
        except safe_fetch.FetchGeweigerd as e:
            return {"error": f"URL geweigerd: {e}", "url": url, "tijdelijk": False}
        except safe_fetch.FetchMislukt as e:
            return {"error": f"ophalen mislukt: {e}", "url": url,
                    "tijdelijk": bool(safe_fetch.is_tijdelijk(e)),
                    "status": getattr(e, "status", None)}
        except Exception as e:                       # onverwacht: nooit als lege uitkomst doorgeven
            return {"error": f"onverwachte fout bij ophalen: {type(e).__name__}: {e}",
                    "url": url, "tijdelijk": False}

        tekst = gehaald.get("tekst") or ""
        basis = {"ok": True, "url": gehaald.get("url") or url, "status": gehaald.get("status"),
                 "titel": gehaald.get("titel") or ""}

        if not term:
            maxt = _int(payload.get("max_tekens"), _DEFAULT_MAX_TEKENS, minimum=200, maximum=100_000)
            return {**basis, "tekst": tekst[:maxt], "afgekapt": len(tekst) > maxt,
                    "tekens_totaal": len(tekst)}

        treffers = zoek_treffers(
            tekst, term,
            context_regels=_int(payload.get("context_regels"), _DEFAULT_CONTEXT_REGELS, maximum=10),
            max_treffers=_int(payload.get("max_treffers"), _DEFAULT_MAX_TREFFERS, minimum=1, maximum=100),
        )
        uit = {**basis, "term": term, "aantal_treffers": len(treffers), "treffers": treffers}
        if not treffers:
            # De pagina is opgehaald; de term staat er niet. Dat is een ANTWOORD, geen storing.
            uit["no_data"] = True
            uit["reason"] = f"term '{term}' komt niet voor op deze pagina ({len(tekst)} tekens gelezen)"
        return uit
