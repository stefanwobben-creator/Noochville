"""trustpilot_reviews — leest recente Trustpilot-reviews van een merk (concurrent of Nooch zelf).

WAAROM DEZE SKILL BESTAAT. `community_listening` dekt Reddit/Bluesky/YouTube-gesprek; geen enkele
skill leest gestructureerde klantreviews (sterren + tekst). Trustpilot-reviews zijn precies het soort
directe klantsignaal dat een gesprekspeiling mist: iemand die met sterren EN woorden zegt waarom een
levering, product of klantenservice tegenviel of juist beviel — bruikbaar op zowel een concurrent als
op Nooch zelf.

CONFIGURATIE. Nodig: een DataForSEO-account (Basic Auth: `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD`
in `.env`, geen los "token"). Betaald per taak, geen bekende gratis laag voor dit endpoint — actuele
prijs op https://dataforseo.com/pricing (dit document schrijft bewust geen bedrag hard, dat verjaart
sneller dan de code). **Ik heb hier geen account voor aangemaakt**; deze skill is inert
("not configured") tot de sleutels in `.env` staan.

ASYNC IN ÉÉN SYNCHRONE AANROEP, EN DE AFWEGING DIE DAARBIJ HOORT. DataForSEO's Trustpilot-endpoint is
een taak-API: `task_post` (meteen betaald, ongeacht of je het resultaat ooit ophaalt) → pollen op
`task_get/<id>` tot het resultaat er is. Dit dorp kent geen "haal dit later op"-mechanisme voor
skills — één `run()`-aanroep geeft één antwoord. Daarom kiest deze skill standaard `priority: 2`
(hoge prioriteit, "tot 1 minuut" volgens DataForSEO's eigen documentatie i.p.v. tot 45 minuten bij de
normale rij) en een begrensde poll-lus van ~90 seconden — dezelfde orde grootte als de bestaande
ngram-puls ("wacht maximaal 90 seconden", CLAUDE.md). Dat kost meer per taak dan de trage rij, maar
past zonder nieuwe architectuur. Is 90 seconden niet genoeg, dan komt de taak-id terug in de
foutmelding: een VOLGENDE aanroep met `task_id` in de payload doet geen nieuwe (betaalde!) taak maar
pollt gewoon door op dezelfde — zo kost een trage dag geen tweede taak.

Drie uitkomsten:
  content            reviews gelezen: sterren-gemiddelde, aantal, en de reviews zelf (tekst, cijfer,
                     datum), plus een simpel getal-signaal (hoeveel 1-2 sterren vs. 4-5 sterren)
  no_data + reason   taak gelukt, geen enkele review gevonden (merk bestaat niet op Trustpilot, of
                     heeft er nog geen)
  error              creds ontbreken, de taak zelf faalde bij DataForSEO, of de taak was nog niet
                     klaar binnen het wachtbudget (`tijdelijk: True`, met `task_id` om op door te pollen)
"""
from __future__ import annotations

import os
import time

import requests

from nooch_village.skills import Skill

_BASE = "https://api.dataforseo.com/v3/business_data/trustpilot/reviews"
_TIMEOUT = 20
_POLL_BUDGET_S = 90            # zelfde orde als de ngram-puls (CLAUDE.md: "wacht maximaal 90 seconden")
_POLL_EERSTE_WACHT_S = 5
_POLL_MAX_WACHT_S = 15
_MAX_REVIEWS_IN_UITVOER = 20
_MAX_TEKST = 500


def _creds(context) -> tuple[str, str]:
    s = getattr(context, "settings", {}) or {}
    login = str(s.get("DATAFORSEO_LOGIN") or os.environ.get("DATAFORSEO_LOGIN") or "").strip()
    wachtwoord = str(s.get("DATAFORSEO_PASSWORD") or os.environ.get("DATAFORSEO_PASSWORD") or "").strip()
    return login, wachtwoord


def _masker_creds(tekst: str, login: str, wachtwoord: str) -> str:
    from nooch_village.sleutelmasker import masker
    return masker(tekst, extra=tuple(w for w in (login, wachtwoord) if w))


class TrustpilotReviewsSkill(Skill):
    name = "trustpilot_reviews"
    cost = "credits"                # betaald per taak; zie docstring — geen hard bedrag hier
    side_effect_free = True
    required_env = ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    description = ("Reads recent Trustpilot reviews for a brand (competitor or Nooch itself): "
                    "average rating, review count, and the reviews themselves (text, stars, date), "
                    "plus a plain count of how many are 1-2 stars vs 4-5 stars. Paid per task at "
                    "DataForSEO, async under the hood but answers within one call (bounded wait, "
                    "~90s). If it times out, retry with the returned 'task_id' in the payload instead "
                    "of starting a new (separately billed) task.")
    input_schema = ("domain: str (required — the brand's Trustpilot domain, e.g. "
                     "'www.example-brand.com', NOT the trustpilot.com URL) OR task_id: str (resume "
                     "polling an earlier task instead of starting a new one — use this after a "
                     "'tijdelijk' timeout); depth: int (optional, default 20, max 200 — reviews cost "
                     "per 20); sort_by: str (optional, 'recency' default here or 'relevance'); "
                     "priority: int (optional, default 2=fast/~1min/costs more; 1=slow/~45min/cheaper)")
    required_payload = (("domain", "task_id"),)
    output_schema = ("ok, domain, task_id, gemiddelde_score, aantal_reviews, "
                      "negatief_1_2_sterren, positief_4_5_sterren, reviews[{tekst, sterren, datum, "
                      "auteur, geverifieerd}], text | no_data + reason | "
                      "error (+ task_id + tijdelijk when the task just needs more time)")

    def validate_payload(self, payload: dict, context) -> list:
        """`task_id` verwijst naar iets BUITEN deze payload (een eerder gestarte, al betaalde
        DataForSEO-taak) — zelfde soort verwijzend veld als `haal_pagina`'s `url`, en met dezelfde
        reden een eigen poort: een verzonnen id (de planner die een niet-bestaande waarde bedenkt in
        plaats van een echte terug te geven uit een vorige 'tijdelijk'-foutmelding) moet HIER
        sneuvelen, niet pas live tegen een 404 bij DataForSEO."""
        task_id = str((payload or {}).get("task_id") or "").strip()
        if not task_id:
            return []                    # afwezigheid dekt required_payload al ('domain' kan volstaan)
        if " " in task_id or len(task_id) > 100 or len(task_id) < 8:
            kort = task_id if len(task_id) <= 60 else task_id[:57] + "…"
            return [f"'task_id' ({kort!r}) lijkt geen echte DataForSEO-taak-id — die komt alleen "
                    f"terug in een eerdere 'tijdelijk'-foutmelding van deze skill; gebruik hem dan "
                    f"letterlijk, verzin er geen"]
        return []

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        login, wachtwoord = _creds(context)
        if not login or not wachtwoord:
            raise RuntimeError("DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD ontbreekt in .env — skill "
                               "faalt bewust closed")

        task_id = str(payload.get("task_id") or "").strip()
        domain = str(payload.get("domain") or "").strip()
        if not task_id and not domain:
            return {"error": "geef 'domain' (nieuwe taak) of 'task_id' (doorpollen) mee"}

        auth = (login, wachtwoord)
        if not task_id:
            try:
                task_id = self._post_taak(domain, payload, auth)
            except RuntimeError as e:
                return {"error": _masker_creds(str(e), login, wachtwoord), "domain": domain}
            if not task_id:
                return {"error": f"DataForSEO gaf geen task_id terug voor '{domain}' — respons-vorm "
                                  f"kan gewijzigd zijn, check https://docs.dataforseo.com", "domain": domain}

        try:
            result = self._poll(task_id, auth)
        except RuntimeError as e:
            return {"error": _masker_creds(str(e), login, wachtwoord), "task_id": task_id,
                    "domain": domain}
        if result is None:
            return {"error": f"Trustpilot-taak nog niet klaar na {_POLL_BUDGET_S}s wachten — "
                              f"probeer het opnieuw met \"task_id\": \"{task_id}\" in de payload; "
                              f"dat start GEEN nieuwe (betaalde) taak, alleen doorpollen",
                    "task_id": task_id, "domain": domain, "tijdelijk": True}

        items = (result or {}).get("items") or []
        basis = {"ok": True, "domain": domain or result.get("domain") or "", "task_id": task_id}
        if not items:
            return {**basis, "no_data": True,
                    "reason": f"Trustpilot task completed but returned zero reviews for "
                              f"'{basis['domain']}' — the brand may not be listed there yet"}

        reviews = [self._review(it) for it in items[:_MAX_REVIEWS_IN_UITVOER]]
        negatief = sum(1 for r in reviews if (r.get("sterren") or 0) <= 2)
        positief = sum(1 for r in reviews if (r.get("sterren") or 0) >= 4)
        gemiddeld = (result.get("rating") or {}).get("value")
        uit = {**basis, "gemiddelde_score": gemiddeld, "aantal_reviews": len(items),
               "negatief_1_2_sterren": negatief, "positief_4_5_sterren": positief,
               "reviews": reviews}
        uit["text"] = (f"{basis['domain']}: {len(items)} review(s) read"
                        + (f", average {gemiddeld}/5" if gemiddeld is not None else "")
                        + f" ({negatief} at 1-2 stars, {positief} at 4-5 stars, of the "
                          f"{len(reviews)} shown)")
        return uit

    @staticmethod
    def _review(item: dict) -> dict:
        item = item if isinstance(item, dict) else {}
        tekst = str(item.get("review_text") or "").strip()
        return {
            "tekst": tekst[:_MAX_TEKST] + ("…" if len(tekst) > _MAX_TEKST else ""),
            "sterren": (item.get("rating") or {}).get("value"),
            "datum": item.get("timestamp"),
            "auteur": (item.get("user_profile") or {}).get("name"),
            "geverifieerd": item.get("verified"),
        }

    def _post_taak(self, domain: str, payload: dict, auth: tuple[str, str]) -> str:
        depth = payload.get("depth")
        try:
            depth = max(1, min(int(depth), 200)) if depth not in (None, "") else 20
        except (TypeError, ValueError):
            depth = 20
        sort_by = str(payload.get("sort_by") or "recency").strip()
        if sort_by not in ("recency", "relevance"):
            sort_by = "recency"
        try:
            prioriteit = int(payload.get("priority"))
        except (TypeError, ValueError):
            prioriteit = 2
        if prioriteit not in (1, 2):
            prioriteit = 2

        body = [{"domain": domain, "depth": depth, "sort_by": sort_by, "priority": prioriteit}]
        r = requests.post(f"{_BASE}/task_post", json=body, auth=auth, timeout=_TIMEOUT)
        if r.status_code >= 400:
            from nooch_village.sleutelmasker import http_fout
            raise RuntimeError(http_fout(r, "DataForSEO"))
        data = r.json()
        taken = data.get("tasks") or []
        if not taken or not isinstance(taken[0], dict):
            return ""
        eerste = taken[0]
        if int(eerste.get("status_code") or 0) not in (20000, 20100) and eerste.get("status_code"):
            raise RuntimeError(f"DataForSEO wees de taak af: {eerste.get('status_message')}")
        return str(eerste.get("id") or "")

    def _poll(self, task_id: str, auth: tuple[str, str]) -> dict | None:
        """Pollt `task_get/<id>` tot `result` gevuld is of het wachtbudget op is. `None` = nog niet
        klaar (geen fout — de taak loopt door bij DataForSEO, alleen deze aanroep wacht niet langer).
        Oplopend interval (5s → 15s) i.p.v. vast, zodat een snel-klare taak niet onnodig lang wacht
        en een trage taak niet te vaak (en dus niet onnodig veel) pollt."""
        verstreken = 0.0
        wacht = _POLL_EERSTE_WACHT_S
        while True:
            r = requests.get(f"{_BASE}/task_get/{task_id}", auth=auth, timeout=_TIMEOUT)
            if r.status_code >= 400:
                from nooch_village.sleutelmasker import http_fout
                raise RuntimeError(http_fout(r, "DataForSEO"))
            data = r.json()
            taken = data.get("tasks") or []
            if taken and isinstance(taken[0], dict):
                resultaten = taken[0].get("result")
                if resultaten:
                    return resultaten[0] if isinstance(resultaten, list) else resultaten
            if verstreken >= _POLL_BUDGET_S:
                return None
            time.sleep(wacht)
            verstreken += wacht
            wacht = min(wacht + 5, _POLL_MAX_WACHT_S)
