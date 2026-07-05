from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _get_creds(token_path: str):
    """Laadt en vernieuwt OAuth-credentials. Geen interactieve flow: faalt closed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not os.path.exists(token_path):
        return None, f"token niet gevonden: {token_path}"
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    except Exception as e:
        return None, f"token kon niet worden geladen: {e}"

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            except Exception as e:
                return None, f"token-refresh mislukt: {e}"
        else:
            return None, "token verlopen zonder refresh_token; herauthoriseer via get_gsc_data.py"

    return creds, None


def _bucket(position: float, impressions: int) -> str:
    if impressions == 0:
        return "content_gap"
    if position <= 10:
        return "page1"
    if position <= 30:
        return "high_potential"
    return "low_ranking"


def _token_path(context) -> str:
    raw_path = (context.settings.get("GSC_TOKEN_PATH") or
                context.settings.get("gsc_token_path", "")).strip()
    if not raw_path:
        # fallback: token.json naast de data-map (= project-root)
        raw_path = os.path.join(os.path.dirname(context.data_dir), "token.json")
    return os.path.expanduser(raw_path)


class GscPerformanceSkill(DataSourceSkill):
    name = "gsc_performance"
    SOURCE = "gsc"
    cost = "free"
    required_env = ("GSC_TOKEN_PATH", "GSC_SITE")
    # GSC-data heeft ~2-3 dagen vertraging → gisteren is nog leeg. De collector richt zich daarom op
    # today − 1 − lag_days; 'geen datapunt voor gisteren' is bij GSC normaal, geen teken van 'dood'.
    lag_days = 3
    description = (
        "Haalt Search Analytics-data op uit Google Search Console (dimensie 'query', "
        "laatste 28 dagen) en classificeert queries in page1 / high_potential / "
        "content_gap / low_ranking."
    )

    def available_metrics(self) -> list[str]:
        """De ruwe zoekprestatie-velden per query (voor het koppelscherm)."""
        return ["impressions", "clicks", "ctr", "position"]

    def is_configured(self, context) -> bool:
        """GSC_SITE gezet én het OAuth-token-bestand bestaat. Zo is 'ontbrekende creds' (unconfigured)
        te onderscheiden van een kapotte API (dood). Read-only."""
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        return bool(site) and os.path.exists(_token_path(context))

    def daily_values(self, context, datum: str) -> dict:
        """Site-dag-totalen (impressions/clicks/ctr/position) voor de kalenderdag `datum`, via een APARTE
        Search Analytics-query (dimensie=date, één dag). Náást de bestaande zoekwoord-run — die blijft
        ongemoeid. Fail-closed per veld: None bij ontbrekende creds/API-fout/geen data (geen mock).
        Geen data voor `datum` is bij GSC's vertraging normaal (→ dan gewoon None, geen 'dood')."""
        fields = ("impressions", "clicks", "ctr", "position")
        out = {m: None for m in fields}
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        if not site:
            return out
        creds, err = _get_creds(_token_path(context))
        if err:
            log.warning("GSC daily_values auth mislukt: %s", err)
            return out
        try:
            from googleapiclient.discovery import build
        except ImportError:
            return out
        try:
            service = build("webmasters", "v3", credentials=creds)
            response = service.searchanalytics().query(
                siteUrl=site,
                body={"startDate": datum, "endDate": datum, "dimensions": ["date"], "rowLimit": 1},
            ).execute()
        except Exception as exc:
            log.warning("GSC daily_values API-fout (%s): %s", datum, exc)
            return out
        rows = response.get("rows", [])
        if not rows:
            return out                   # nog geen data voor die dag → normaal bij GSC-lag
        r = rows[0]
        out["impressions"] = int(r.get("impressions", 0))
        out["clicks"] = int(r.get("clicks", 0))
        out["ctr"] = round(r.get("ctr", 0.0), 4)
        out["position"] = round(r.get("position", 0.0), 1)
        return out

    def run(self, payload: dict, context) -> dict:
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        if not site:
            return {"error": "GSC_SITE ontbreekt in .env -> skill faalt bewust closed"}

        creds, err = _get_creds(_token_path(context))
        if err:
            return {"error": f"GSC-auth mislukt: {err} -> skill faalt bewust closed"}

        try:
            from googleapiclient.discovery import build
        except ImportError:
            return {"error": "google-api-python-client niet geinstalleerd (pip install google-api-python-client)"}

        today = datetime.now().date()
        start = (today - timedelta(days=28)).isoformat()
        end = today.isoformat()

        try:
            service = build("webmasters", "v3", credentials=creds)
            response = service.searchanalytics().query(
                siteUrl=site,
                body={
                    "startDate": start,
                    "endDate": end,
                    "dimensions": ["query"],
                    "rowLimit": payload.get("row_limit", 500),
                },
            ).execute()
        except Exception as e:
            return {"error": f"GSC API-fout: {e} -> skill faalt bewust closed"}

        # Detecteer de locale van de site op basis van het domein (bijv. .nl → nl, anders en)
        locale = "nl" if site.rstrip("/").endswith(".nl") or ".nl/" in site else "en"

        rows = []
        for row in response.get("rows", []):
            query = row["keys"][0]
            clicks = int(row.get("clicks", 0))
            impressions = int(row.get("impressions", 0))
            position = round(row.get("position", 0.0), 1)
            rows.append({
                "query":       query,
                "locale":      locale,   # taalvak afgeleid van het site-domein
                "clicks":      clicks,
                "impressions": impressions,
                "position":    position,
                "bucket":      _bucket(position, impressions),
            })

        counts = {}
        for r in rows:
            counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1

        return {
            "site":   site,
            "locale": locale,            # top-level locale voor eenvoudige consumers
            "period": f"{start}/{end}",
            "total": len(rows),
            "bucket_counts": counts,
            "rows": rows,
        }
