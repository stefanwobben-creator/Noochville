"""Server-side ophalen van een publieke pagina, met SSRF-guardrail.

Waarom deze module bestaat: de cockpit draait in een datacenter en heeft toegang tot interne
adressen die een browser niet heeft. Een gebruiker die een URL invoert mag die toegang nooit
lenen. Elke server-side fetch van een door de mens aangeleverde URL loopt daarom hier langs.

Gedeeld door de claims-checker (handmatige URL-scan) en de wekelijkse site-scan, zodat de
guardrail op één plek leeft — reference, don't copy.
"""
from __future__ import annotations

import html as html_module
import ipaddress
import re
import socket
import urllib.parse

USER_AGENT = "NoochVillage/1.0 (+https://nooch.earth; claims-checker)"
TIMEOUT_SECONDS = 15
MAX_BYTES = 3_000_000          # ~3 MB: ruim voor een webpagina, klein genoeg om niet te verstikken


class FetchGeweigerd(ValueError):
    """De URL mag niet opgehaald worden (schema, hostnaam of privé-adres)."""


class FetchMislukt(RuntimeError):
    """De URL mocht wel, maar ophalen lukte niet (timeout, DNS, HTTP-fout)."""


def _is_privaat(ip: str) -> bool:
    """Loopback, privé-ranges, link-local, multicast en 'reserved' — alles wat niet publiek is."""
    try:
        adres = ipaddress.ip_address(ip)
    except ValueError:
        return True                                  # onparseerbaar = niet vertrouwen
    return bool(adres.is_private or adres.is_loopback or adres.is_link_local
                or adres.is_multicast or adres.is_reserved or adres.is_unspecified)


def controleer_url(url: str) -> str:
    """Geef de URL terug als hij veilig opgehaald mag worden, anders FetchGeweigerd.

    Weigert alles wat geen http(s) is en elke hostnaam die naar een niet-publiek adres
    resolvet — ook als de host publiek klinkt maar naar 127.0.0.1 wijst."""
    url = (url or "").strip()
    if not url:
        raise FetchGeweigerd("geen URL opgegeven")
    delen = urllib.parse.urlparse(url)
    if delen.scheme not in ("http", "https"):
        raise FetchGeweigerd("alleen http:// en https:// worden opgehaald")
    if not delen.hostname:
        raise FetchGeweigerd("URL zonder hostnaam")
    try:
        infos = socket.getaddrinfo(delen.hostname, delen.port or (443 if delen.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise FetchGeweigerd(f"hostnaam niet gevonden: {delen.hostname}") from e
    for info in infos:
        ip = info[4][0]
        if _is_privaat(ip):
            raise FetchGeweigerd(
                f"interne adressen worden niet gescand ({delen.hostname} → {ip})")
    return url


def haal_tekst(url: str, _fetch=None) -> dict:
    """Haal de pagina op en geef `{url, status, titel, tekst}` terug.

    `_fetch` is injecteerbaar voor tests: een callable(url) -> (status_code, html).
    Zonder injectie wordt `requests` gebruikt — en dan pas, zodat de import geen
    netwerkafhankelijkheid oplegt aan wie alleen de guardrail nodig heeft."""
    veilig = controleer_url(url)
    if _fetch is not None:
        status, html = _fetch(veilig)
    else:
        import requests
        try:
            r = requests.get(veilig, timeout=TIMEOUT_SECONDS,
                             headers={"User-Agent": USER_AGENT}, stream=True)
            html = r.raw.read(MAX_BYTES, decode_content=True).decode(r.encoding or "utf-8",
                                                                    errors="replace")
            status = r.status_code
        except Exception as e:                       # requests-fouten zijn een familie; één vangnet
            raise FetchMislukt(f"ophalen mislukt: {e}") from e
    if status >= 400:
        raise FetchMislukt(f"de pagina gaf HTTP {status}")
    titel, tekst = naar_tekst(html)
    return {"url": veilig, "status": status, "titel": titel, "tekst": tekst}


def haal_ruw(url: str, _fetch=None) -> dict:
    """Haal een bron op zonder hem als HTML te interpreteren: `{url, status, content_type, ruw}`.

    Nodig voor bronnen die geen webpagina zijn (de Belgische PDF-gids). Een PDF door de
    HTML-stripper halen geeft binaire ruis die per byte kan verschillen zonder dat de inhoud
    veranderde; op de rauwe bytes hashen is stabiel én eerlijk.

    `_fetch` is injecteerbaar voor tests: callable(url) -> (status, body, content_type)."""
    veilig = controleer_url(url)
    if _fetch is not None:
        status, body, ctype = _fetch(veilig)
    else:
        import requests
        try:
            r = requests.get(veilig, timeout=TIMEOUT_SECONDS,
                             headers={"User-Agent": USER_AGENT}, stream=True)
            body = r.raw.read(MAX_BYTES, decode_content=True)
            status, ctype = r.status_code, r.headers.get("Content-Type", "")
        except Exception as e:
            raise FetchMislukt(f"ophalen mislukt: {e}") from e
    if status >= 400:
        raise FetchMislukt(f"de bron gaf HTTP {status}")
    return {"url": veilig, "status": status, "content_type": ctype or "", "ruw": body}


_SCRIPT_RE = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_TITEL_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
_WIT_RE = re.compile(r"\n{3,}")



def naar_tekst(html: str) -> tuple[str, str]:
    """Strip HTML naar leesbare tekst: titel + meta-description + body, in die volgorde.

    Bewust dezelfde volgorde als het prototype hanteerde, zodat een claim in de <title>
    net zo goed gevonden wordt als een claim in de body."""
    html = html or ""
    titel_m = _TITEL_RE.search(html)
    titel = " ".join(_ontsnap(_TAG_RE.sub("", titel_m.group(1))).split()) if titel_m else ""
    meta_m = _META_RE.search(html)
    meta = _ontsnap(meta_m.group(1)).strip() if meta_m else ""
    body = _SCRIPT_RE.sub(" ", html)
    body = _TAG_RE.sub("\n", body)
    body = _ontsnap(body)
    body = "\n".join(regel.strip() for regel in body.split("\n") if regel.strip())
    tekst = _WIT_RE.sub("\n\n", "\n".join(x for x in (titel, meta, body) if x)).strip()
    return titel, tekst


def _ontsnap(s: str) -> str:
    """HTML-entiteiten terug naar tekens — via de stdlib, zodat ook &ndash; en &#8217; kloppen."""
    return html_module.unescape(s).replace("\xa0", " ")
