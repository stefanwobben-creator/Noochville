"""pappers_financials — omzethistorie van een Franse concurrent uit het officiële handelsregister.

WAAROM DEZE SKILL BESTAAT. `concurrentiedossier.md` (12 sept) demonstreerde handmatig wat deze skill
automatiseert: Veja's jaarrekeningen bij de Franse Balanscentrale (via pappers.fr) laten een
omzetdaling van 28% zien sinds de piek van 2023 — een concreet, gegrond feit dat geen enkele
bestaande skill kon vinden (`competitor_news` is nieuws/RSS, `claim_evidence` verifieert een
GEDANE claim, geen van beide graaft in jaarrekeningen). Frankrijk publiceert dit verplicht en
openbaar voor de meeste vennootschapsvormen (SAS, SARL, ...); pappers.fr ontsluit het als API.

CONFIGURATIE. Nodig: een gratis pappers.fr-account (professioneel e-mailadres geeft 100 gratis
credits bij aanmelden) en `PAPPERS_API_KEY` in `.env`. Kost: 0,1 credit per zoekresultaat + 1 credit
voor het bedrijfsdossier + 2 credits voor de financiële cijfers (tekst/JSON) = ruwweg 3 credits per
opzoeking. Nooch's reële behoefte (Veja + Moea, maandelijks) is dus ~6 credits/maand — ruim binnen de
gratis laag. **Ik heb hier geen account voor aangemaakt** (dat mag ik niet namens Stefan doen); deze
skill is inert ("not configured") tot de sleutel in `.env` staat.

EERLIJKHEID OVER WAT GEVERIFIEERD IS. De authenticatie (`api_token` als query-parameter) en het
zoeken-op-naam-vóór-details-ophalen-patroon zijn bevestigd via pappers.fr's eigen site en meerdere
onafhankelijke bronnen. Het EXACTE veldnamen-schema van de financiële cijfers in de JSON-respons kon
ik niet met zekerheid vaststellen zonder een werkende sleutel (de volledige API-referentie zit achter
een JS-laag die deze sandbox niet kan renderen). Daarom leest `_haal_omzetreeks` DEFENSIEF: hij
probeert een paar aannemelijke veldnamen en faalt LUID met de ruwe top-level sleutels erbij als geen
ervan matcht — nooit stil een lege of verzonnen reeks. Klopt het schema niet meer (Pappers wijzigt
zijn API), dan is de eerste run zichtbaar `error`, niet een stille misinterpretatie.

Drie uitkomsten, zelfde conventie als de rest van het dorp:
  content            een bedrijf gevonden, financiële cijfers gelezen, trend berekend
  no_data + reason   bedrijf niet gevonden in het Franse register, of gevonden maar (nog) geen
                     gedeponeerde jaarrekening (normaal voor een hele jonge of hele kleine onderneming)
  error              de API zelf faalde, de sleutel ontbreekt, of de respons-vorm klopt niet meer
"""
from __future__ import annotations

import os
import random
import time

import requests

from nooch_village.skills import Skill

log_naam = "village.skill.pappers_financials"

_ZOEK_URL = "https://api.pappers.fr/v2/recherche"
_ENTREPRISE_URL = "https://api.pappers.fr/v2/entreprise"
_TIMEOUT = 20
_MAX_POGINGEN = 4          # zelfde orde als openalex/semantic_scholar
_MAX_JAREN = 8


def _key(context) -> str:
    s = getattr(context, "settings", {}) or {}
    return str(s.get("PAPPERS_API_KEY") or os.environ.get("PAPPERS_API_KEY") or "").strip()


def _get(url: str, params: dict) -> dict:
    """Eén GET-call met exponentiële backoff bij 429/5xx, zelfde geest als openalex/semantic_scholar.
    Nooit de URL in de foutmelding (die draagt `api_token`): `sleutelmasker.http_fout` geeft alleen
    status + reden + begin van de body. Geïsoleerd zodat tests dit kunnen vervangen zonder netwerk."""
    from nooch_village.sleutelmasker import http_fout
    laatste_fout = None
    for poging in range(_MAX_POGINGEN):
        try:
            r = requests.get(url, params=params, timeout=_TIMEOUT)
        except requests.RequestException as e:
            laatste_fout = RuntimeError(f"Pappers-API netwerkfout: {type(e).__name__}")
            if poging < _MAX_POGINGEN - 1:
                time.sleep(2 ** poging + random.uniform(0, 1))
                continue
            raise laatste_fout from None
        if r.status_code >= 400:
            if r.status_code in (429, 500, 502, 503, 504) and poging < _MAX_POGINGEN - 1:
                time.sleep(2 ** poging + random.uniform(0, 1))
                continue
            raise RuntimeError(http_fout(r, "Pappers"))
        return r.json()
    raise laatste_fout or RuntimeError("Pappers-API: geen antwoord na herhaalde pogingen")


def _haal_omzetreeks(entreprise: dict) -> tuple[list[dict], list[str]]:
    """(jaren, ontbreekt) — defensief: probeert een paar aannemelijke sleutels voor de financiële
    reeks en per jaar voor omzet/jaartal, in plaats van er blindelings één te veronderstellen.
    `ontbreekt` is niet-leeg zodra het schema niet herkend werd — dat is de zichtbare fout-hook."""
    ruwe_reeks = None
    for sleutel in ("finances", "comptes", "bilans", "comptes_annuels"):
        if isinstance(entreprise.get(sleutel), list):
            ruwe_reeks = entreprise[sleutel]
            break
    if ruwe_reeks is None:
        return [], [f"geen herkenbare financiële reeks in de respons (top-level sleutels: "
                    f"{', '.join(sorted(entreprise.keys())[:15])})"]

    jaren: list[dict] = []
    for item in ruwe_reeks:
        if not isinstance(item, dict):
            continue
        jaar = None
        for jsleutel in ("annee", "date_cloture_exercice", "annee_cloture", "exercice"):
            if item.get(jsleutel):
                jaar = str(item[jsleutel])[:4]
                break
        omzet = None
        for osleutel in ("chiffre_affaires", "ca", "chiffres_affaires"):
            waarde = item.get(osleutel)
            if isinstance(waarde, (int, float)):
                omzet = float(waarde)
                break
        if jaar and omzet is not None:
            jaren.append({"jaar": jaar, "omzet": omzet})
    if not jaren and ruwe_reeks:
        return [], [f"financiële reeks gevonden ({len(ruwe_reeks)} item(s)) maar geen jaar+omzet "
                    f"veld herkend — voorbeeld-sleutels: {', '.join(sorted(ruwe_reeks[0].keys())[:15]) if isinstance(ruwe_reeks[0], dict) else '?'}"]
    jaren.sort(key=lambda r: r["jaar"])
    return jaren[-_MAX_JAREN:], []


def _trend(jaren: list[dict]) -> dict:
    """Piek-tot-nu en jaar-op-jaar, procentueel. Simpel en navolgbaar (geen voorspelling, geen model)
    — dezelfde soort feit als de Veja-vondst in concurrentiedossier.md: 'omzet daalt X% sinds de piek'."""
    if len(jaren) < 2:
        return {}
    laatste = jaren[-1]["omzet"]
    piek = max(j["omzet"] for j in jaren)
    piek_jaar = next(j["jaar"] for j in jaren if j["omzet"] == piek)
    vorige = jaren[-2]["omzet"]
    uit = {}
    if piek:
        uit["sinds_piek_pct"] = round((laatste - piek) / piek * 100, 1)
        uit["piek_jaar"] = piek_jaar
    if vorige:
        uit["jaar_op_jaar_pct"] = round((laatste - vorige) / vorige * 100, 1)
    return uit


class PappersFinancialsSkill(Skill):
    name = "pappers_financials"
    cost = "credits"                # ~3 credits per opzoeking (zoeken + dossier + cijfers)
    side_effect_free = True
    required_env = ("PAPPERS_API_KEY",)
    description = ("Looks up a FRENCH competitor's filed annual accounts (the official, public "
                    "French company register via pappers.fr) and reports its revenue history and "
                    "trend — peak-to-now and year-over-year, in percent. France requires most company "
                    "forms (SAS, SARL, ...) to file this publicly. Only useful for French-registered "
                    "companies; a non-French brand will come back as 'not found'.")
    input_schema = ("bedrijf: str (company name to search) OR siren: str (the 9-digit French company "
                     "id, skips the search step if you already have it) — one of the two is required; "
                     "jaren: int (optional, default all available up to 8, most recent last)")
    required_payload = (("bedrijf", "siren"),)
    output_schema = ("ok, bedrijf, siren, kandidaten[{naam, siren}] (other name matches, if any), "
                      "jaren[{jaar, omzet}], trend{sinds_piek_pct, piek_jaar, jaar_op_jaar_pct}, "
                      "text | no_data + reason (not found, or no filed accounts yet) | error")

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        key = _key(context)
        if not key:
            raise RuntimeError("PAPPERS_API_KEY ontbreekt in .env — skill faalt bewust closed")

        bedrijf = str(payload.get("bedrijf") or "").strip()
        siren = str(payload.get("siren") or "").strip()
        kandidaten: list[dict] = []

        if not siren:
            if not bedrijf:
                return {"error": "geef 'bedrijf' (naam) of 'siren' mee"}
            try:
                zoek = _get(_ZOEK_URL, {"api_token": key, "q": bedrijf, "par_page": 5})
            except RuntimeError as e:
                return {"error": str(e)}
            resultaten = zoek.get("resultats") or zoek.get("resultats_siren") or []
            if not resultaten:
                return {"no_data": True, "bedrijf": bedrijf,
                        "reason": f"no French company found under the name '{bedrijf}' in the "
                                  f"Pappers register — it may not be French-registered"}
            eerste = resultaten[0] if isinstance(resultaten[0], dict) else {}
            siren = str(eerste.get("siren") or "").strip()
            if not siren:
                return {"error": f"search for '{bedrijf}' returned a result without a 'siren' field "
                                  f"— response shape may have changed"}
            kandidaten = [{"naam": r.get("nom_entreprise") or r.get("denomination") or "?",
                           "siren": r.get("siren")} for r in resultaten[1:5] if isinstance(r, dict)]

        try:
            entreprise = _get(_ENTREPRISE_URL, {"api_token": key, "siren": siren,
                                                "extrait_financier": "true"})
        except RuntimeError as e:
            return {"error": str(e), "siren": siren}

        naam = entreprise.get("nom_entreprise") or entreprise.get("denomination") or bedrijf or siren
        jaren, ontbreekt = _haal_omzetreeks(entreprise)
        basis = {"ok": True, "bedrijf": naam, "siren": siren}
        if kandidaten:
            basis["kandidaten"] = kandidaten

        if ontbreekt:
            return {**basis, "error": "Pappers response for this company did not match the expected "
                                       "shape: " + "; ".join(ontbreekt) +
                                       " — check https://www.pappers.fr/api/documentation, the API "
                                       "may have changed since this skill was written"}
        if not jaren:
            return {**basis, "no_data": True,
                    "reason": f"{naam} is registered but has no filed annual accounts yet (normal "
                              f"for a very young or very small company)"}

        trend = _trend(jaren)
        uit = {**basis, "jaren": jaren, "trend": trend}
        uit["text"] = self._als_tekst(naam, jaren, trend)
        return uit

    @staticmethod
    def _als_tekst(naam: str, jaren: list[dict], trend: dict) -> str:
        laatste = jaren[-1]
        kop = f"{naam}: revenue {laatste['omzet']:,.0f} in {laatste['jaar']}".replace(",", ".")
        if trend.get("sinds_piek_pct") is not None:
            richting = "down" if trend["sinds_piek_pct"] < 0 else "up"
            kop += (f", {richting} {abs(trend['sinds_piek_pct'])}% since its {trend['piek_jaar']} peak")
        if trend.get("jaar_op_jaar_pct") is not None:
            kop += f" ({trend['jaar_op_jaar_pct']:+.1f}% year-over-year)"
        return kop + f". {len(jaren)} year(s) of filed accounts read."
