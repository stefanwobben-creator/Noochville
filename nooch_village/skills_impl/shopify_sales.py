"""ShopifySalesSkill — read-only verkoopindicatoren uit de eigen Shopify-winkel.

Geeft de website_watcher de verkoopkant naast Plausible (bezoekers) en GSC (vindbaarheid):
paren verkocht, orders, omzet, gemiddelde orderwaarde, verdeling per land en topproducten over
een venster. Gebruikt de Admin GraphQL API (X-Shopify-Access-Token).

Privacy: UITSLUITEND geaggregeerd. Geen klantnamen/adressen/e-mails — alleen tellingen en
landcodes. Fail-closed zonder store/token. De pure aggregatie (`aggregate_orders`) en het ophalen
(`fetch_orders`, injecteerbare POST) zijn gescheiden, zodat alles testbaar is zonder netwerk.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse
import urllib.error
from collections import Counter
from datetime import datetime, timedelta, timezone
from nooch_village.skills import Skill

_API_VERSION = "2026-01"

# Eén pagina orders met regels, bedrag en land. Geen PII (geen klant-velden).
_ORDERS_QUERY = """
query($cursor: String, $q: String) {
  orders(first: 100, after: $cursor, query: $q, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      createdAt
      currentTotalPriceSet { shopMoney { amount currencyCode } }
      shippingAddress { countryCodeV2 }
      lineItems(first: 100) { nodes { title quantity } }
      customerJourneySummary {
        firstVisit {
          landingPage
          source
          sourceType
          referrerUrl
          utmParameters { source medium campaign term }
        }
      }
    }
  }
}
"""


def _post_graphql(store: str, token: str, query: str, variables: dict) -> dict:
    """Eén GraphQL-POST naar de Admin API. Aparte functie zodat tests 'm kunnen injecteren."""
    url = f"https://{store}/admin/api/{_API_VERSION}/graphql.json"
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "X-Shopify-Access-Token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_access_token(store: str, client_id: str, client_secret: str, *, _post=None) -> str:
    """Wissel Client ID + secret om voor een (kortlevend) Admin-token via de client-credentials-
    flow (Dev Dashboard-apps; werkt als app en winkel in dezelfde organisatie zitten). De oude
    statische 'shpat_'-token bestaat sinds 2026 niet meer voor nieuwe apps. `_post` injecteerbaar."""
    if _post is not None:
        return _post(store, client_id, client_secret)
    url = f"https://{store}/admin/oauth/access_token"
    # Shopify vereist hier application/x-www-form-urlencoded (NIET json), anders HTTP 400.
    body = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret,
                                   "grant_type": "client_credentials"}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("access_token", "")
    except urllib.error.HTTPError as e:
        # Toon de échte reden die Shopify meegeeft (bijv. shop_not_permitted, invalid_client).
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        raise RuntimeError(f"HTTP {e.code} van Shopify: {detail or e.reason}") from None


def _path_of(url: str) -> str:
    """Maak een landingspagina-URL leesbaar: alleen het pad (bijv. /blogs/veganisme/...)."""
    if not url:
        return ""
    try:
        p = urllib.parse.urlparse(url)
        return (p.path or "/") if p.scheme else url
    except Exception:
        return url


def _normalize(node: dict) -> dict:
    """GraphQL-order → vlak dict met verkoop- én attributievelden (eerste bezoek: landingspagina,
    kanaal, UTM-term). Geen PII."""
    money = ((node.get("currentTotalPriceSet") or {}).get("shopMoney") or {})
    addr = node.get("shippingAddress") or {}
    items = [{"title": (n.get("title") or "?"), "quantity": int(n.get("quantity") or 0)}
             for n in ((node.get("lineItems") or {}).get("nodes") or [])]
    try:
        total = float(money.get("amount") or 0)
    except (TypeError, ValueError):
        total = 0.0
    fv = ((node.get("customerJourneySummary") or {}).get("firstVisit") or {})
    utm = fv.get("utmParameters") or {}
    return {"created_at": node.get("createdAt", ""), "country": addr.get("countryCodeV2") or "?",
            "currency": money.get("currencyCode") or "", "total": total, "line_items": items,
            "landing_page": _path_of(fv.get("landingPage") or ""),
            "channel": (fv.get("sourceType") or fv.get("source") or "onbekend"),
            "utm_term": (utm.get("term") or "")}


def fetch_orders(store: str, token: str, since_iso: str | None, *, _post=None, max_pages: int = 20) -> list[dict]:
    """Haal (genormaliseerde) orders op, met paginatie. `since_iso=None` → hele historie (geen
    datumfilter). `_post` injecteerbaar voor tests."""
    post = _post or (lambda q, v: _post_graphql(store, token, q, v))
    out: list[dict] = []
    cursor = None
    q = f"created_at:>={since_iso}" if since_iso else None
    for _ in range(max_pages):
        data = post(_ORDERS_QUERY, {"cursor": cursor, "q": q})
        if (data or {}).get("errors"):
            raise RuntimeError(f"Shopify GraphQL-fout: {str(data['errors'])[:300]}")
        conn = ((data or {}).get("data") or {}).get("orders") or {}
        out.extend(_normalize(n) for n in conn.get("nodes", []))
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
    return out


def _parse_dt(created_at: str, now: datetime):
    """Parse Shopify-ISO naar datetime (UTC). None bij onleesbaar."""
    try:
        dt = datetime.fromisoformat((created_at or "").replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _within_days(created_at: str, now: datetime, days: int) -> bool:
    """True als de order-datum binnen `days` van nu valt. Fail-safe → True (tel mee bij twijfel)."""
    dt = _parse_dt(created_at, now)
    return True if dt is None else (now - dt).total_seconds() <= days * 86400


def aggregate_orders(orders: list[dict], window_days: int, *, now=None) -> dict:
    """Pure aggregatie van genormaliseerde orders → verkoopindicatoren. Geen netwerk, geen PII.
    Bevat ook een 7-daags subvenster (orders_7d/pairs_7d), zodat het dashboard de conversie eerlijk
    tegen de 7-daagse bezoekerscijfers (Plausible) kan zetten."""
    now = now or datetime.now(timezone.utc)
    pairs = sum(li["quantity"] for o in orders for li in o.get("line_items", []))
    revenue = round(sum(o.get("total", 0.0) for o in orders), 2)
    n = len(orders)
    currency = next((o["currency"] for o in orders if o.get("currency")), "")
    by_country = Counter(o.get("country", "?") for o in orders)
    prod = Counter()
    landing = Counter()      # landingspagina (eerste bezoek) → paren
    channels = Counter()     # kanaal van eerste bezoek → orders
    keywords = Counter()     # UTM-term (campagnes) → paren
    for o in orders:
        units = sum(li["quantity"] for li in o.get("line_items", []))
        for li in o.get("line_items", []):
            prod[li["title"]] += li["quantity"]
        if o.get("landing_page"):
            landing[o["landing_page"]] += units
        channels[o.get("channel") or "onbekend"] += 1
        if o.get("utm_term"):
            keywords[o["utm_term"]] += units
    recent = [o for o in orders if _within_days(o.get("created_at", ""), now, 7)]
    pairs_7d = sum(li["quantity"] for o in recent for li in o.get("line_items", []))
    # Gemiddelden per maand over de werkelijke periode (eerste order → nu) — vooral nuttig bij
    # 'hele historie': zo zie je een rustig gemiddelde i.p.v. alleen een venster.
    dates = [d for o in orders if (d := _parse_dt(o.get("created_at", ""), now))]
    first = min(dates) if dates else None
    span_days = max(1, (now - first).days) if first else 0
    fmonth = (span_days / 30) if span_days else 0
    per_month = lambda x: round(x / fmonth, 1) if fmonth else 0.0
    return {
        "generated_at": now.timestamp(),
        "window_days": window_days,
        "pairs_sold": pairs,
        "orders": n,
        "revenue": revenue,
        "currency": currency,
        "aov": round(revenue / n, 2) if n else 0.0,
        "by_country": by_country.most_common(8),
        "top_products": prod.most_common(8),
        "orders_7d": len(recent),
        "pairs_7d": pairs_7d,
        "first_order_date": first.date().isoformat() if first else None,
        "span_days": span_days,
        "avg_pairs_month": per_month(pairs),
        "avg_orders_month": per_month(n),
        "avg_revenue_month": per_month(revenue),
        "top_landing_pages": landing.most_common(8),
        "channels": channels.most_common(8),
        "top_keywords": keywords.most_common(8),
    }


# Fixture-data voor de STUB-modus. Shopify-OAuth staat geparkeerd; tot er een live token is kan de
# skill — UITSLUITEND op expliciet verzoek — op deze vaste fixture draaien zodat pairs_sold een
# testwaarde geeft en de pijplijn niet op de OAuth blijft hangen. Dit is GEEN mock die de echte
# call dood-codeert (CLAUDE.md regel 5): de live route houdt altijd voorrang en blijft bereikbaar;
# de stub draait alleen als hij expliciet wordt aangevraagd én er geen live token aanwezig is.
_STUB_ORDERS = [
    {"created_at": "2026-06-20T10:00:00Z", "country": "NL", "currency": "EUR",
     "total": 180.0, "line_items": [{"title": "Sneaker Groen", "quantity": 2}]},
    {"created_at": "2026-06-18T10:00:00Z", "country": "DE", "currency": "EUR",
     "total": 90.0, "line_items": [{"title": "Sneaker Zwart", "quantity": 1}]},
    {"created_at": "2026-05-30T10:00:00Z", "country": "NL", "currency": "EUR",
     "total": 270.0, "line_items": [{"title": "Sneaker Groen", "quantity": 3}]},
]   # pairs_sold = 2 + 1 + 3 = 6


class ShopifySalesSkill(Skill):
    name = "shopify_sales"
    cost = "free"
    required_env = ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")
    description = (
        "Read-only verkoopindicatoren uit Shopify (Admin GraphQL): paren verkocht, orders, omzet, "
        "AOV, per land en topproducten over een venster. Uitsluitend geaggregeerd, geen PII."
    )

    def available_metrics(self) -> list[str]:
        """De scalaire verkoopindicatoren die aggregate_orders oplevert (voor het koppelscherm)."""
        return ["pairs_sold", "orders", "revenue", "aov"]

    @staticmethod
    def _truthy(v) -> bool:
        return str(v).strip().lower() in ("1", "true", "yes", "ja", "on")

    def _stub_result(self) -> dict:
        """Gemarkeerde fixture-uitkomst: NIET live. Alleen via de expliciete stub-modus."""
        agg = aggregate_orders(_STUB_ORDERS, 0)
        return {"ok": True, "live": False, "stub": True,
                "note": "STUB — Shopify-OAuth staat geparkeerd; dit is fixture-data, niet live.",
                **agg}

    def run(self, payload: dict, context) -> dict:
        s = context.settings
        # Expliciete stub-modus: payload {"stub": True} of settings shopify_stub. Draait alleen als
        # er GEEN live token is — zo houdt de echte route voorrang en wordt niets dood-gecodeerd.
        stub_requested = bool(payload.get("stub")) or self._truthy(s.get("shopify_stub", ""))
        has_static_token = bool((s.get("SHOPIFY_TOKEN") or s.get("shopify_token", "")).strip())
        if stub_requested and not has_static_token:
            return self._stub_result()
        store = (s.get("SHOPIFY_STORE") or s.get("shopify_store", "")).strip()
        if not store:
            return {"error": "SHOPIFY_STORE ontbreekt in .env -> skill faalt closed"}
        # Token: statisch (oude apps) óf via Client ID/secret (Dev Dashboard, client-credentials).
        token = (s.get("SHOPIFY_TOKEN") or s.get("shopify_token", "")).strip()
        if not token:
            cid = (s.get("SHOPIFY_CLIENT_ID") or s.get("shopify_client_id", "")).strip()
            csec = (s.get("SHOPIFY_CLIENT_SECRET") or s.get("shopify_client_secret", "")).strip()
            if not (cid and csec):
                return {"error": "SHOPIFY_TOKEN of SHOPIFY_CLIENT_ID+SHOPIFY_CLIENT_SECRET "
                                 "ontbreekt in .env -> skill faalt closed"}
            try:
                token = get_access_token(store, cid, csec, _post=payload.get("_token_post"))
            except Exception as e:
                return {"error": f"Shopify-token ophalen mislukt: {e} -> skill faalt closed"}
            if not token:
                return {"error": "Shopify gaf geen access_token terug -> skill faalt closed"}
        # Eén of meer vensters. `windows=[0,7,30]` → in één fetch (hele historie) meerdere
        # aggregaties, zodat het dashboard een 7d/maand/alles-toggle kan tonen zonder extra calls.
        windows = payload.get("windows")
        if windows:
            try:
                orders = fetch_orders(store, token, None, _post=payload.get("_post"))
            except Exception as e:
                return {"error": f"Shopify-call mislukt: {e} -> skill faalt closed"}
            now = datetime.now(timezone.utc)
            wins = {}
            for w in windows:
                w = int(w)
                subset = orders if w <= 0 else [o for o in orders
                                                if _within_days(o.get("created_at", ""), now, w)]
                wins[str(w)] = aggregate_orders(subset, w, now=now)
            base = wins.get("0") or next(iter(wins.values()))
            return {"ok": True, "windows": wins, **base}
        window = int(payload.get("window_days", 0))      # 0 = hele historie (geen datumfilter)
        since = None if window <= 0 else (
            datetime.now(timezone.utc) - timedelta(days=window)).date().isoformat()
        try:
            orders = fetch_orders(store, token, since, _post=payload.get("_post"))
        except Exception as e:
            return {"error": f"Shopify-call mislukt: {e} -> skill faalt closed"}
        return {"ok": True, **aggregate_orders(orders, window)}
