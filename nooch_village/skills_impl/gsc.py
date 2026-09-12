from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timedelta
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _get_creds(token_path: str):
    """Laadt credentials uit `token_path`. Detecteert automatisch een SERVICE-ACCOUNT-sleutel
    (type=service_account — robuust, verloopt niet, geen consent-scherm) óf een OAuth
    authorized_user-token (oude route, met refresh). Faalt closed: geen interactieve flow."""
    if not os.path.exists(token_path):
        return None, f"credential-bestand niet gevonden: {token_path}"
    try:
        with open(token_path, encoding="utf-8") as fh:
            blob = json.load(fh)
    except Exception as e:
        return None, f"credential-bestand kon niet worden gelezen: {e}"

    # Service-account-sleutel: server-to-server, geen 7-daagse token-verloop, geen browser-flow.
    if isinstance(blob, dict) and blob.get("type") == "service_account":
        try:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(blob, scopes=SCOPES)
            return creds, None
        except Exception as e:
            return None, f"service-account-sleutel kon niet worden geladen: {e}"

    # Anders: OAuth authorized_user-token — laden en zo nodig vernieuwen.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    try:
        creds = Credentials.from_authorized_user_info(blob, SCOPES)
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
            return None, "token verlopen zonder refresh_token; gebruik een service-account-sleutel"
    return creds, None


#: De bucket-grenzen op gemiddelde positie — ÉÉN plek. gsc_report las tot scope 58 zijn eigen koppen
#: ("11–20", "21–50", "50+") die `_bucket` tegenspraken (11–30, >30): twee waarheden, uiteengedreven.
#: (ondergrens, bovengrens); None = open naar boven. `content_gap` is geen positieband maar
#: 'impressions == 0' — NB: een Search-Analytics-rij zonder vertoningen komt in de praktijk niet voor
#: (GSC geeft alleen rijen met ≥1 impressie terug), dus die bucket blijft vrijwel altijd leeg.
BUCKET_GRENZEN = {"page1": (1, 10), "high_potential": (11, 30), "low_ranking": (31, None)}
BUCKET_LABEL = {"page1": "page 1", "high_potential": "high potential", "low_ranking": "low ranking",
                "content_gap": "content gap"}
#: Het vaste venster van `run` (dagen), en hoeveel dagen Google structureel achterloopt (zie lag_days).
VENSTER_DAGEN = 28
LAG_DAGEN = 3


def bucket_bereik(bucket: str) -> str:
    """'position 11–30' / 'position 31+' — voor koppen en de leeswijzer, afgeleid uit BUCKET_GRENZEN."""
    lo, hi = BUCKET_GRENZEN.get(bucket, (None, None))
    if lo is None:
        return "no impressions"
    return f"position {lo}–{hi}" if hi is not None else f"position {lo}+"


def _bucket(position: float, impressions: int) -> str:
    if impressions == 0:
        return "content_gap"
    if position <= BUCKET_GRENZEN["page1"][1]:
        return "page1"
    if position <= BUCKET_GRENZEN["high_potential"][1]:
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
    CATALOG_LABEL = "Google Search Console"
    cost = "free"
    required_env = ("GSC_TOKEN_PATH", "GSC_SITE")
    # GSC-data heeft ~2-3 dagen vertraging → gisteren is nog leeg. De collector richt zich daarom op
    # today − 1 − lag_days; 'geen datapunt voor gisteren' is bij GSC normaal, geen teken van 'dood'.
    lag_days = LAG_DAGEN
    # GSC bewaart ~16 maanden historie. Een backfill vóór die horizon levert enkel None → de backfill
    # klemt de startdatum hierop af zodat je geen honderden lege dagen bevraagt.
    backfill_history_days = 480
    DIMENSION = "query"          # scope 2: reeksen per Library-keyword via de native query-dimensie
    description = (
        "Search queries nooch.earth was found on in Google over the last 28 days, from Google Search "
        "Console: per query clicks, impressions, average position and a bucket (page 1 / high potential / "
        "low ranking / content gap), plus a bucket count and a one-line `text`. Fixed window; the last "
        "~3 days are still empty at Google. Needs GSC_SITE and a credential file (GSC_TOKEN_PATH)."
    )
    input_schema = ("row_limit: int (optional, default 500, max 25000). Fixed window: the last 28 days ending "
                    "today; the last ~3 days are still empty at Google, so a query with few impressions may "
                    "be missing. No query filter.")
    output_schema = ("site, locale, period ('start/end'), total, bucket_counts{page1, high_potential, "
                     "low_ranking, content_gap}, rows[{query, locale, clicks, impressions, position, bucket}], "
                     "text | no_data + reason (0 rows) | error")
    #: `rowLimit` mag bij Google maximaal 25.000 zijn.
    MAX_ROW_LIMIT = 25000

    def available_metrics(self, context=None) -> list[str]:
        """De ruwe zoekprestatie-velden per query (voor het koppelscherm)."""
        return ["impressions", "clicks", "ctr", "position"]

    def is_configured(self, context) -> bool:
        """GSC_SITE gezet én het OAuth-token-bestand bestaat. Zo is 'ontbrekende creds' (unconfigured)
        te onderscheiden van een kapotte API (dood). Read-only."""
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        return bool(site) and os.path.exists(_token_path(context))

    def daily_values(self, context, datum: str, *, _query=None) -> dict:
        """Site-dag-totalen (impressions/clicks/ctr/position) voor de kalenderdag `datum`, via een APARTE
        Search Analytics-query (dimensie=date, één dag). Náást de bestaande zoekwoord-run — die blijft
        ongemoeid. Fail-closed per veld: None bij ontbrekende creds/API-fout/geen data (geen mock).
        Geen data voor `datum` is bij GSC's vertraging normaal (→ dan gewoon None, geen 'dood').
        `_query(body)` is injecteerbaar zodat de backfill-contract-test kan bewijzen dat `datum` écht als
        startDate/endDate meegaat (zonder netwerk)."""
        fields = ("impressions", "clicks", "ctr", "position")
        out = {m: None for m in fields}
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        if not site:
            return out
        body = {"startDate": datum, "endDate": datum, "dimensions": ["date"], "rowLimit": 1}
        if _query is None:
            creds, err = _get_creds(_token_path(context))
            if err:
                log.warning("GSC daily_values auth mislukt: %s", err)
                return out
            try:
                from googleapiclient.discovery import build
            except ImportError:
                return out

            def _query(b):
                return build("webmasters", "v3", credentials=creds).searchanalytics().query(
                    siteUrl=site, body=b).execute()
        try:
            response = _query(body)
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

    def daily_dimension_values(self, context, datum: str, keywords, *, _query=None) -> dict:
        """Per Library-keyword de zoekprestaties voor `datum` via ÉÉN call met dimensie=query (native GSC).
        `keywords` = de gecureerde selectie (collector: approved+doelwit, gecapt). Match exact (case-
        insensitive) op de GSC-query. Geeft {(veld, keyword): waarde}; een keyword dat die dag niet in de
        respons zit (bijv. <10 impressies, GSC-anonimisering) → géén entry → gat. Fail-closed → lege dict.
        `_query(body)` injecteerbaar zodat de contract-test datum + dimensions:['query'] kan bewijzen."""
        want = {k.lower(): k for k in (keywords or [])}
        out = {}
        site = (context.settings.get("GSC_SITE") or context.settings.get("gsc_site", "")).strip()
        if not want or not site:
            return out
        body = {"startDate": datum, "endDate": datum, "dimensions": ["query"], "rowLimit": 25000}
        if _query is None:
            creds, err = _get_creds(_token_path(context))
            if err:
                log.warning("GSC daily_dimension_values auth mislukt: %s", err)
                return out
            try:
                from googleapiclient.discovery import build
            except ImportError:
                return out

            def _query(b):
                return build("webmasters", "v3", credentials=creds).searchanalytics().query(
                    siteUrl=site, body=b).execute()
        try:
            response = _query(body)
        except Exception as exc:
            log.warning("GSC daily_dimension_values API-fout (%s): %s", datum, exc)
            return out
        for row in response.get("rows", []):
            kw = want.get((row.get("keys") or [""])[0].lower())
            if kw is None:
                continue                        # GSC-query hoort niet bij een gecureerd keyword
            out[("impressions", kw)] = int(row.get("impressions", 0))
            out[("clicks", kw)] = int(row.get("clicks", 0))
            out[("ctr", kw)] = round(row.get("ctr", 0.0), 4)
            out[("position", kw)] = round(row.get("position", 0.0), 1)
        return out

    def validate_payload(self, payload: dict, context) -> list:
        """Alleen `row_limit` is stuurbaar; een niet-getal of een limiet buiten Google's bereik strandt
        bij het plannen. Alles anders (een query-filter, een venster) wordt niet stil genegeerd maar
        gemeld, zodat de planner weet dat deze skill dat niet kan."""
        p = payload or {}
        uit = []
        if p.get("row_limit") not in (None, ""):
            try:
                n = int(p["row_limit"])
                if not 1 <= n <= self.MAX_ROW_LIMIT:
                    uit.append(f"'row_limit' must be between 1 and {self.MAX_ROW_LIMIT}, not {n}")
            except (TypeError, ValueError):
                uit.append(f"'row_limit' is not a number ({p['row_limit']!r})")
        onbekend = sorted(k for k in p if not str(k).startswith("_") and k != "row_limit")
        if onbekend:
            uit.append("gsc_performance has a fixed window (last 28 days) and no filters; "
                       f"unsupported field(s): {', '.join(onbekend)}")
        return uit

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        settings = getattr(context, "settings", None) or {}
        site = (settings.get("GSC_SITE") or settings.get("gsc_site", "")).strip()
        if not site:
            # Bewust geen 'ontbreekt'/'verplicht' in deze zin: dat is de woordkeus van een
            # PAYLOAD-klacht (test_payload_declaratie), en dit is config, geen payload.
            return {"error": "GSC_SITE not set in .env -> skill fails closed"}

        today = datetime.now().date()
        start = (today - timedelta(days=VENSTER_DAGEN)).isoformat()
        end = today.isoformat()
        try:
            row_limit = max(1, min(int(payload.get("row_limit") or 500), self.MAX_ROW_LIMIT))
        except (TypeError, ValueError):
            row_limit = 500
        body = {"startDate": start, "endDate": end, "dimensions": ["query"], "rowLimit": row_limit}

        # `_query(body)` is alleen voor tests injecteerbaar (zoals bij daily_values): zo is de
        # bucket-verdeling, de locale en het 0-rijen-pad te bewijzen zonder Google. De planner kan hier
        # nooit iets in zetten (een callable past niet in een JSON-payload).
        _query = payload.get("_query")
        if _query is None:
            creds, err = _get_creds(_token_path(context))
            if err:
                return {"error": f"GSC-auth mislukt: {err} -> skill faalt bewust closed"}
            try:
                from googleapiclient.discovery import build
            except ImportError:
                return {"error": "google-api-python-client niet geinstalleerd (pip install google-api-python-client)"}

            def _query(b):
                return build("webmasters", "v3", credentials=creds).searchanalytics().query(
                    siteUrl=site, body=b).execute()
        try:
            response = _query(body)
        except Exception as e:
            return {"error": f"GSC API-fout: {e} -> skill faalt bewust closed"}

        # Detecteer de locale van de site op basis van het domein (bijv. .nl → nl, anders en)
        locale = "nl" if site.rstrip("/").endswith(".nl") or ".nl/" in site else "en"
        period = f"{start}/{end}"

        rows = []
        for row in (response or {}).get("rows", []) or []:
            query = (row.get("keys") or [""])[0]
            clicks = int(row.get("clicks", 0))
            impressions = int(row.get("impressions", 0))
            position = round(row.get("position", 0.0), 1)
            bucket = _bucket(position, impressions)
            rows.append({
                "query":       query,
                "locale":      locale,   # taalvak afgeleid van het site-domein
                "clicks":      clicks,
                "impressions": impressions,
                "position":    position,
                "bucket":      bucket,
                # de strekking per record, zodat het verslag niet alleen de query noemt
                "text":        (f"avg. position {position}, {impressions} impressions, {clicks} clicks "
                                f"({BUCKET_LABEL[bucket]})"),
            })

        counts = {}
        for r in rows:
            counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1

        # `rows` vóór `bucket_counts`: bij gelijke omvang wint de uitvoerlaag op sleutelvolgorde, en de
        # rijen (met query en strekking) zeggen meer dan de telling (die staat al in de `text`).
        uit = {
            "site":   site,
            "locale": locale,            # top-level locale voor eenvoudige consumers
            "period": period,
            "total": len(rows),
            "rows": rows,
            "bucket_counts": counts,
        }
        if not rows:
            # Nul rijen is ONDERZOCHT, NIETS GEVONDEN — geen succes. Tot scope 58 won `site` als enige
            # tekst en werd het item afgevinkt als "gelukt: sc-domain:nooch.earth" (skill-review
            # 12-09-2026). De lege sleutels blijven staan zodat TrendsWorker gewoon doorloopt.
            uit["no_data"] = True
            uit["reason"] = (f"GSC returned 0 rows for the last {VENSTER_DAGEN} days ({period}); "
                             f"data lags ~{LAG_DAGEN} days")
            return uit
        uit["text"] = self._tekst(rows, counts, period)
        return uit

    @staticmethod
    def _tekst(rows: list, counts: dict, period: str) -> str:
        """De leeswijzer: totaal, de bucket-verdeling met de positiebanden, klikken en vertoningen."""
        delen = []
        for b in ("page1", "high_potential", "low_ranking", "content_gap"):
            n = counts.get(b, 0)
            if n:
                delen.append(f"{n} {BUCKET_LABEL[b]} ({bucket_bereik(b)})")
        clicks = sum(r["clicks"] for r in rows)
        imps = sum(r["impressions"] for r in rows)
        return (f"{len(rows)} queries in {period.replace('/', ' to ')}: " + ", ".join(delen) +
                f"; {clicks} clicks on {imps} impressions. GSC data lags ~{LAG_DAGEN} days, so the last "
                "days of the window are still empty.")
