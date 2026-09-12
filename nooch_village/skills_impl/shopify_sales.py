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
import logging
import urllib.request
import urllib.parse
import urllib.error
from collections import Counter
from datetime import datetime, timedelta, timezone
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

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


#: Pagina's van 100 orders per fetch; daarboven stopt de skill en zegt hij dat (`truncated`).
MAX_PAGES = 20


def fetch_orders_pages(store: str, token: str, since_iso: str | None, *, _post=None,
                       max_pages: int = MAX_PAGES) -> tuple[list[dict], bool]:
    """Haal (genormaliseerde) orders op, met paginatie: (orders, truncated). `since_iso=None` → hele
    historie (geen datumfilter). `truncated` = True als de laatste pagina nog `hasNextPage` had: de
    historie is dan afgekapt op max_pages × 100 orders, en dat hoort in de uitkomst te staan in
    plaats van stil als 'alles' door te gaan (skill-review 12-09-2026). `_post` injecteerbaar."""
    post = _post or (lambda q, v: _post_graphql(store, token, q, v))
    out: list[dict] = []
    cursor = None
    q = f"created_at:>={since_iso}" if since_iso else None
    truncated = False
    for _ in range(max_pages):
        data = post(_ORDERS_QUERY, {"cursor": cursor, "q": q})
        if (data or {}).get("errors"):
            raise RuntimeError(f"Shopify GraphQL-fout: {str(data['errors'])[:300]}")
        conn = ((data or {}).get("data") or {}).get("orders") or {}
        out.extend(_normalize(n) for n in conn.get("nodes", []))
        page = conn.get("pageInfo") or {}
        truncated = bool(page.get("hasNextPage"))
        if not truncated:
            break
        cursor = page.get("endCursor")
    return out, truncated


def fetch_orders(store: str, token: str, since_iso: str | None, *, _post=None, max_pages: int = MAX_PAGES) -> list[dict]:
    """Als `fetch_orders_pages`, alleen de orders (de bestaande aanroepvorm: daily_values, tests)."""
    return fetch_orders_pages(store, token, since_iso, _post=_post, max_pages=max_pages)[0]


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


class ShopifySalesSkill(DataSourceSkill):
    name = "shopify_sales"
    SOURCE = "shopify"
    CATALOG_LABEL = "Shopify (verkoop)"
    cost = "free"
    # `required_env` = wat ALTIJD moet: de winkel. De auth-weg is een of-of (statisch SHOPIFY_TOKEN óf
    # SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET) die een platte lijst niet kan uitdrukken; tot scope 58
    # stonden hier client-id + secret, waardoor de bronnen-view bij een token-configuratie "connected"
    # én "missing SHOPIFY_CLIENT_ID/SECRET" tegelijk toonde. `is_configured` toetst de echte eis;
    # `config_hint` zegt hem in mensentaal aan de planner-poort.
    required_env = ("SHOPIFY_STORE",)
    optional_env = ("SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")
    config_hint = ("SHOPIFY_STORE plus SHOPIFY_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET "
                   "needed in .env")
    description = (
        "Sales figures from the Nooch Shopify store (read-only Admin GraphQL): pairs sold, orders, revenue "
        "and average order value over a window, with breakdowns per country, product, landing page, "
        "channel and UTM term. Aggregated only, no customer data. Returns `rows` (headline figures first) "
        "and a one-line `text`; a stub run says 'stub' in that text. Needs SHOPIFY_STORE and a token."
    )
    input_schema = ("window_days: int (optional, default 0 = all history; 7, 30, …) OR windows: list[int] "
                    "(optional, e.g. [0, 7, 30] = several windows from one fetch; the flat figures are then "
                    "the first window, usually all history). Nothing else.")
    output_schema = ("ok, text, rows[{period, metric, waarde, text} — pairs_sold, orders, revenue, aov, "
                     "orders_7d, pairs_7d, then {period, metric, dimension, name, waarde, text} per country/"
                     "product/landing page/channel/utm term], pairs_sold, orders, revenue, currency, aov, "
                     "by_country, top_products, top_landing_pages, channels, top_keywords, orders_7d, "
                     "pairs_7d, first_order_date, span_days, avg_*_month, window_days, truncated, "
                     "windows{…} (windows-form), stub + live:false (stub) | no_data + reason (0 orders) | error")

    def available_metrics(self, context=None) -> list[str]:
        """De scalaire verkoopindicatoren die aggregate_orders oplevert (voor het koppelscherm)."""
        return ["pairs_sold", "orders", "revenue", "aov"]

    def is_configured(self, context) -> bool:
        """Read-only creds-check: een winkel + een auth-weg (statisch SHOPIFY_TOKEN óf CLIENT_ID+SECRET).
        Leest alleen; raakt SHOPIFY_API_SECRET (webhook-secret) nooit aan."""
        s = context.settings
        store = (s.get("SHOPIFY_STORE") or s.get("shopify_store", "")).strip()
        token = (s.get("SHOPIFY_TOKEN") or s.get("shopify_token", "")).strip()
        cid = (s.get("SHOPIFY_CLIENT_ID") or s.get("shopify_client_id", "")).strip()
        csec = (s.get("SHOPIFY_CLIENT_SECRET") or s.get("shopify_client_secret", "")).strip()
        return bool(store and (token or (cid and csec)))

    def daily_values(self, context, datum: str) -> dict:
        """Dagwaarde per gedeclareerd veld (pairs_sold/orders/revenue/aov) voor de kalenderdag `datum`:
        haal orders sinds `datum`, filter op exact die dag, aggregeer. Fail-closed per veld (None bij
        ontbrekende creds/API-fout, geen stub/mock). Alleen lezen — geen enkele Shopify-secret wordt
        geschreven."""
        fields = ("pairs_sold", "orders", "revenue", "aov")
        out = {m: None for m in fields}
        s = context.settings
        store = (s.get("SHOPIFY_STORE") or s.get("shopify_store", "")).strip()
        if not store:
            return out
        token = (s.get("SHOPIFY_TOKEN") or s.get("shopify_token", "")).strip()
        if not token:
            cid = (s.get("SHOPIFY_CLIENT_ID") or s.get("shopify_client_id", "")).strip()
            csec = (s.get("SHOPIFY_CLIENT_SECRET") or s.get("shopify_client_secret", "")).strip()
            if not (cid and csec):
                return out
            try:
                token = get_access_token(store, cid, csec)
            except Exception as exc:
                log.warning("Shopify token daily_values faalde: %s", exc)
                return out
        if not token:
            return out
        try:
            orders = fetch_orders(store, token, datum)
            day = [o for o in orders if str(o.get("created_at", ""))[:10] == datum]
            agg = aggregate_orders(day, 0)
            for m in fields:
                if agg.get(m) is not None:
                    out[m] = agg[m]
        except Exception as exc:
            log.warning("Shopify daily_values faalde (%s): %s", datum, exc)
        return out

    @staticmethod
    def _truthy(v) -> bool:
        return str(v).strip().lower() in ("1", "true", "yes", "ja", "on")

    def validate_payload(self, payload: dict, context) -> list:
        """Twee poorten bij het PLANNEN. (1) Configuratie: zonder winkel + auth-weg is elke payload
        onuitvoerbaar — vijf keer "⚠️ niet gelukt (fout, poging n)" op de wall was de meting die
        hierachter zit; de reden noemt de sleutelNAMEN. (2) Vorm: `window_days` een getal ≥ 0,
        `windows` een lijst getallen; iets anders (een datum, een productnaam) strandt hier."""
        uit = []
        if context is not None and getattr(context, "settings", None) is not None:
            try:
                if not self.is_configured(context):
                    uit.append(f"Shopify not configured ({self.config_hint})")
            except Exception:                              # noqa: BLE001 — bij twijfel geen oordeel
                pass
        p = payload or {}
        if p.get("window_days") not in (None, ""):
            try:
                if int(p["window_days"]) < 0:
                    uit.append("'window_days' must be 0 (all history) or a positive number of days")
            except (TypeError, ValueError):
                uit.append(f"'window_days' is not a number ({p['window_days']!r})")
        if p.get("windows") not in (None, ""):
            ws = p["windows"]
            if not isinstance(ws, (list, tuple)):
                uit.append("'windows' must be a list of day counts, e.g. [0, 7, 30]")
            else:
                try:
                    if any(int(w) < 0 for w in ws):
                        uit.append("'windows' may only contain 0 (all history) or positive day counts")
                except (TypeError, ValueError):
                    uit.append(f"'windows' is not a list of numbers ({ws!r})")
        return uit

    @staticmethod
    def _label(window_days: int, agg: dict) -> str:
        if window_days <= 0:
            eerste = agg.get("first_order_date")
            return f"all history (since {eerste})" if eerste else "all history"
        return {7: "the last 7 days", 30: "the last 30 days"}.get(window_days, f"the last {window_days} days")

    @staticmethod
    def _n(n, enkel: str, meer: str) -> str:
        """'1 order' / '3 orders' — een note die "1 orders" zegt leest als een machine."""
        return f"{n} {enkel if n == 1 else meer}"

    @staticmethod
    def _geld(bedrag, currency: str) -> str:
        cur = (currency or "").upper()
        return f"€{bedrag:,.2f}" if cur == "EUR" else f"{bedrag:,.2f} {cur}".strip()

    def _rows(self, agg: dict, window_days: int) -> list:
        """De kopcijfers eerst, dan de verdelingen als één lijst. Zonder deze lijst won `by_country`
        (een lijst tuples) van `pairs_sold`, en opende de note met "('NL', 2) • ('DE', 1)" zonder paren
        of omzet (skill-review 12-09-2026)."""
        label = self._label(window_days, agg)
        periode = "all" if window_days <= 0 else f"{window_days}d"
        cur = agg.get("currency") or ""
        rows = [
            {"period": periode, "metric": "pairs_sold", "waarde": agg.get("pairs_sold", 0),
             "text": f"{self._n(agg.get('pairs_sold', 0), 'pair', 'pairs')} sold in {label}"},
            {"period": periode, "metric": "orders", "waarde": agg.get("orders", 0),
             "text": f"{self._n(agg.get('orders', 0), 'order', 'orders')} in {label}"},
            {"period": periode, "metric": "revenue", "waarde": agg.get("revenue", 0.0),
             "text": f"{self._geld(agg.get('revenue', 0.0), cur)} revenue in {label}"},
            {"period": periode, "metric": "aov", "waarde": agg.get("aov", 0.0),
             "text": f"average order value {self._geld(agg.get('aov', 0.0), cur)} in {label}"},
        ]
        if window_days <= 0 or window_days > 7:
            rows.append({"period": "7d", "metric": "orders_7d", "waarde": agg.get("orders_7d", 0),
                         "text": f"{self._n(agg.get('orders_7d', 0), 'order', 'orders')} and "
                                 f"{self._n(agg.get('pairs_7d', 0), 'pair', 'pairs')} in the last 7 days"})
        for sleutel, dim, eenheid, frase in (("by_country", "country", "orders", "from {}"),
                                              ("top_products", "product", "pairs", "of {}"),
                                              ("top_landing_pages", "landing_page", "pairs", "via landing page {}"),
                                              ("channels", "channel", "orders", "via channel {}"),
                                              ("top_keywords", "utm_term", "pairs", "via utm term {}")):
            for naam, n in agg.get(sleutel) or []:
                rows.append({"period": periode, "metric": eenheid, "dimension": dim, "name": str(naam),
                             "waarde": n,
                             "text": f"{self._n(n, eenheid[:-1], eenheid)} {frase.format(naam)} in {label}"})
        return rows

    def _tekst(self, agg: dict, window_days: int, *, stub: bool = False, truncated: bool = False,
               wins: dict | None = None) -> str:
        label = self._label(window_days, agg)
        cur = agg.get("currency") or ""
        kop = (f"{self._n(agg.get('pairs_sold', 0), 'pair', 'pairs')} in "
               f"{self._n(agg.get('orders', 0), 'order', 'orders')}, "
               f"{self._geld(agg.get('revenue', 0.0), cur)} (AOV {self._geld(agg.get('aov', 0.0), cur)}) in {label}")
        if window_days <= 0 and agg.get("avg_pairs_month"):
            kop += f", ≈{agg['avg_pairs_month']} pairs/month"
        delen = [kop + "."]
        extra = []
        for w, a in sorted(((int(k), v) for k, v in (wins or {}).items()), key=lambda kv: kv[0]):
            if w == window_days or not isinstance(a, dict):
                continue
            extra.append(f"{self._label(w, a)}: {self._n(a.get('pairs_sold', 0), 'pair', 'pairs')} in "
                         f"{self._n(a.get('orders', 0), 'order', 'orders')}")
        if extra:
            delen.append("; ".join(extra).capitalize() + ".")
        elif window_days <= 0 or window_days > 7:
            delen.append(f"Last 7 days: {self._n(agg.get('orders_7d', 0), 'order', 'orders')}, "
                         f"{self._n(agg.get('pairs_7d', 0), 'pair', 'pairs')}.")
        top = (agg.get("top_products") or [None])[0]
        if top:
            delen.append(f"Top product: {top[0]} ({top[1]} pairs).")
        if truncated:
            delen.append(f"Truncated: only the first {MAX_PAGES * 100} orders were read (older history missing).")
        if stub:
            delen.insert(0, "STUB — fixture data, not live (Shopify not configured):")
        return " ".join(delen)

    def _stub_result(self) -> dict:
        """Gemarkeerde fixture-uitkomst: NIET live. Alleen via de expliciete stub-modus. Het woord
        'stub' staat in de `text` en in elke rij, zodat fixture-verkoop nooit als echt op de wall komt."""
        agg = aggregate_orders(_STUB_ORDERS, 0)
        rows = self._rows(agg, 0)
        for r in rows:
            r["text"] = "stub: " + r["text"]
        return {"ok": True, "live": False, "stub": True,
                "note": "STUB — Shopify-OAuth staat geparkeerd; dit is fixture-data, niet live.",
                "text": self._tekst(agg, 0, stub=True), "rows": rows, **agg}

    def _uitkomst(self, agg: dict, window_days: int, *, truncated: bool, wins: dict | None = None) -> dict:
        """Eén vorm voor beide routes: ok + text + rows + de platte aggregatie (+ windows)."""
        uit = {"ok": True, "text": self._tekst(agg, window_days, truncated=truncated, wins=wins),
               "rows": self._rows(agg, window_days), **agg, "truncated": truncated}
        if wins is not None:
            uit["windows"] = wins
        if not agg.get("orders"):
            # Nul orders is onderzocht-en-niets, geen succes: tot scope 58 won `generated_at` en
            # toonde de note een Unix-timestamp als antwoord (skill-review 12-09-2026). `ok` blijft
            # True (de bron antwoordde); `no_data` zegt wat het is.
            uit["no_data"] = True
            uit["reason"] = f"Shopify: 0 orders in {self._label(window_days, agg)}"
        return uit

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        s = getattr(context, "settings", None) or {}
        store = (s.get("SHOPIFY_STORE") or s.get("shopify_store", "")).strip()
        token = (s.get("SHOPIFY_TOKEN") or s.get("shopify_token", "")).strip()
        cid = (s.get("SHOPIFY_CLIENT_ID") or s.get("shopify_client_id", "")).strip()
        csec = (s.get("SHOPIFY_CLIENT_SECRET") or s.get("shopify_client_secret", "")).strip()
        # Expliciete stub-modus: payload {"stub": True} of settings shopify_stub. Draait alleen als
        # er GEEN live route is — statisch token óf client-credentials — zo houdt de echte route
        # voorrang en wordt niets dood-gecodeerd. (Tot scope 58 telde alleen het statische token, en
        # won de stub van een echte client-credentials-configuratie.)
        stub_requested = bool(payload.get("stub")) or self._truthy(s.get("shopify_stub", ""))
        has_live_route = bool(token or (cid and csec))
        if stub_requested and not has_live_route:
            return self._stub_result()
        # Bewust geen 'ontbreekt'/'verplicht' in deze zinnen: dat is de woordkeus van een
        # PAYLOAD-klacht (test_payload_declaratie), en dit is config, geen payload. De planner-poort
        # vangt dit al vóór de uitvoering (validate_payload / config_hint); dit is de tweede laag.
        if not store:
            return {"error": "SHOPIFY_STORE not set in .env -> skill fails closed"}
        # Token: statisch (oude apps) óf via Client ID/secret (Dev Dashboard, client-credentials).
        if not token:
            if not (cid and csec):
                return {"error": "SHOPIFY_TOKEN or SHOPIFY_CLIENT_ID+SHOPIFY_CLIENT_SECRET "
                                 "not set in .env -> skill fails closed"}
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
                orders, truncated = fetch_orders_pages(store, token, None, _post=payload.get("_post"))
            except Exception as e:
                return {"error": f"Shopify-call mislukt: {e} -> skill faalt closed"}
            now = datetime.now(timezone.utc)
            wins = {}
            for w in windows:
                w = int(w)
                subset = orders if w <= 0 else [o for o in orders
                                                if _within_days(o.get("created_at", ""), now, w)]
                wins[str(w)] = aggregate_orders(subset, w, now=now)
            base_key = "0" if "0" in wins else next(iter(wins))
            return self._uitkomst(wins[base_key], int(base_key), truncated=truncated, wins=wins)
        window = int(payload.get("window_days") or 0)      # 0 = hele historie (geen datumfilter)
        since = None if window <= 0 else (
            datetime.now(timezone.utc) - timedelta(days=window)).date().isoformat()
        try:
            orders, truncated = fetch_orders_pages(store, token, since, _post=payload.get("_post"))
        except Exception as e:
            return {"error": f"Shopify-call mislukt: {e} -> skill faalt closed"}
        return self._uitkomst(aggregate_orders(orders, window), window, truncated=truncated)
