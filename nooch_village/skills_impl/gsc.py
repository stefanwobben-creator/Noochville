from __future__ import annotations
import os
from datetime import datetime, timedelta
from nooch_village.skills import Skill

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


class GscPerformanceSkill(Skill):
    name = "gsc_performance"
    description = (
        "Haalt Search Analytics-data op uit Google Search Console (dimensie 'query', "
        "laatste 28 dagen) en classificeert queries in page1 / high_potential / "
        "content_gap / low_ranking."
    )

    def run(self, payload: dict, context) -> dict:
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        if not site:
            return {"error": "GSC_SITE ontbreekt in .env -> skill faalt bewust closed"}

        raw_path = (context.settings.get("GSC_TOKEN_PATH") or
                    context.settings.get("gsc_token_path", "")).strip()
        if not raw_path:
            # fallback: token.json naast de data-map (= project-root)
            raw_path = os.path.join(os.path.dirname(context.data_dir), "token.json")
        token_path = os.path.expanduser(raw_path)

        creds, err = _get_creds(token_path)
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
