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


def _normalize(node: dict) -> dict:
    """GraphQL-order → vlak dict {created_at, country, currency, total, line_items[]}."""
    money = ((node.get("currentTotalPriceSet") or {}).get("shopMoney") or {})
    addr = node.get("shippingAddress") or {}
    items = [{"title": (n.get("title") or "?"), "quantity": int(n.get("quantity") or 0)}
             for n in ((node.get("lineItems") or {}).get("nodes") or [])]
    try:
        total = float(money.get("amount") or 0)
    except (TypeError, ValueError):
        total = 0.0
    return {"created_at": node.get("createdAt", ""), "country": addr.get("countryCodeV2") or "?",
            "currency": money.get("currencyCode") or "", "total": total, "line_items": items}


def fetch_orders(store: str, token: str, since_iso: str, *, _post=None, max_pages: int = 10) -> list[dict]:
    """Haal (genormaliseerde) orders op vanaf `since_iso`, met paginatie. `_post` injecteerbaar."""
    post = _post or (lambda q, v: _post_graphql(store, token, q, v))
    out: list[dict] = []
    cursor = None
    for _ in range(max_pages):
        data = post(_ORDERS_QUERY, {"cursor": cursor, "q": f"created_at:>={since_iso}"})
        conn = ((data or {}).get("data") or {}).get("orders") or {}
        out.extend(_normalize(n) for n in conn.get("nodes", []))
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
    return out


def aggregate_orders(orders: list[dict], window_days: int, *, now=None) -> dict:
    """Pure aggregatie van genormaliseerde orders → verkoopindicatoren. Geen netwerk, geen PII."""
    now = now or datetime.now(timezone.utc)
    pairs = sum(li["quantity"] for o in orders for li in o.get("line_items", []))
    revenue = round(sum(o.get("total", 0.0) for o in orders), 2)
    n = len(orders)
    currency = next((o["currency"] for o in orders if o.get("currency")), "")
    by_country = Counter(o.get("country", "?") for o in orders)
    prod = Counter()
    for o in orders:
        for li in o.get("line_items", []):
            prod[li["title"]] += li["quantity"]
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
    }


class ShopifySalesSkill(Skill):
    name = "shopify_sales"
    cost = "free"
    required_env = ("SHOPIFY_STORE", "SHOPIFY_TOKEN")
    description = (
        "Read-only verkoopindicatoren uit Shopify (Admin GraphQL): paren verkocht, orders, omzet, "
        "AOV, per land en topproducten over een venster. Uitsluitend geaggregeerd, geen PII."
    )

    def run(self, payload: dict, context) -> dict:
        s = context.settings
        store = (s.get("SHOPIFY_STORE") or s.get("shopify_store", "")).strip()
        token = (s.get("SHOPIFY_TOKEN") or s.get("shopify_token", "")).strip()
        if not store or not token:
            return {"error": "SHOPIFY_STORE/SHOPIFY_TOKEN ontbreekt in .env -> skill faalt closed"}
        window = int(payload.get("window_days", 28))
        since = (datetime.now(timezone.utc) - timedelta(days=window)).date().isoformat()
        try:
            orders = fetch_orders(store, token, since, _post=payload.get("_post"))
        except Exception as e:
            return {"error": f"Shopify-call mislukt: {e} -> skill faalt closed"}
        return {"ok": True, **aggregate_orders(orders, window)}
