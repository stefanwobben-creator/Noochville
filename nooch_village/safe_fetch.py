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
import logging
import re
import socket
import time
import urllib.parse

log = logging.getLogger("village.fetch")

USER_AGENT = "NoochVillage/1.0 (+https://nooch.earth; claims-checker)"
TIMEOUT_SECONDS = 15
MAX_BYTES = 3_000_000          # ~3 MB: ruim voor een webpagina, klein genoeg om niet te verstikken

# Statuscodes die betekenen "kom later terug", niet "dit bestaat niet". De host praat met ons, hij
# heeft nu even geen zin. Onderscheiden loont: een 429 mag een scan nooit als 'gedaan' afsluiten,
# een 404 mag een scan nooit voor altijd vastzetten.
TIJDELIJKE_STATUS = (408, 425, 429, 500, 502, 503, 504)


class FetchGeweigerd(ValueError):
    """De URL mag niet opgehaald worden (schema, hostnaam of privé-adres)."""


class FetchMislukt(RuntimeError):
    """De URL mocht wel, maar ophalen lukte niet (timeout, DNS, HTTP-fout).

    `status` draagt de HTTP-code als er één was, en None bij een netwerk-/timeout-fout. De caller
    heeft die nodig om tijdelijk (opnieuw proberen) van permanent (de pagina is weg) te scheiden;
    zonder dat onderscheid is elke fout ofwel een eeuwige retry ofwel een stille blinde vlek.

    `retry_after` is wat de hóst zegt te willen wachten (seconden). Shopify vraagt bij een 429 om
    60 seconden; wie zelf 2 seconden verzint, krijgt gewoon opnieuw een 429 en concludeert onterecht
    dat de pagina onbereikbaar is. De bron weet dit beter dan wij."""

    def __init__(self, bericht: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(bericht)
        self.status = status
        self.retry_after = retry_after


def _retry_after(headers) -> float | None:
    """De Retry-After-header als seconden, of None. Alleen de delta-seconds-vorm (wat Shopify en de
    meeste CDN's sturen); een HTTP-datum negeren we liever dan verkeerd te parsen."""
    try:
        ruw = (headers or {}).get("Retry-After")
    except Exception:                                # noqa: BLE001 — een rare header mag niets breken
        return None
    if ruw is None:
        return None
    try:
        wacht = float(str(ruw).strip())
    except ValueError:
        return None
    return wacht if wacht >= 0 else None


def is_tijdelijk(fout: Exception) -> bool:
    """Mag deze fout opnieuw geprobeerd worden?

    Ja bij een netwerk-/timeoutfout (geen status) en bij de TIJDELIJKE_STATUS-codes. Nee bij elke
    andere HTTP-fout (404/410/403: de pagina bestaat niet of mag niet) en bij FetchGeweigerd — dat
    is een configuratieprobleem dat door retryen niet overgaat."""
    if isinstance(fout, FetchGeweigerd):
        return False
    status = getattr(fout, "status", None)
    return status is None or status in TIJDELIJKE_STATUS


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
    wacht = None
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
            wacht = _retry_after(r.headers)
        except Exception as e:                       # requests-fouten zijn een familie; één vangnet
            raise FetchMislukt(f"ophalen mislukt: {e}") from e
    if status >= 400:
        raise FetchMislukt(f"de pagina gaf HTTP {status}", status=status, retry_after=wacht)
    titel, tekst = naar_tekst(html)
    return {"url": veilig, "status": status, "titel": titel, "tekst": tekst}


MAX_PAUZE = 90.0               # bovengrens per wachtbeurt: honoreer de host, maar hang niet eeuwig


class Wachtbudget:
    """Hoeveel seconden mag een reeks fetches in totaal wachten?

    Zonder budget kan een host met `Retry-After: 60` een scan van vijf pagina's tien minuten laten
    hangen. Zonder retry mist die scan 60% van de site. Het budget is de derde weg: wacht zolang het
    zin heeft, en laat de rest als TIJDELIJKE fout terugvallen — die pagina's worden bij de volgende
    puls opnieuw geprobeerd, want een tijdelijke fout sluit de week niet af."""

    def __init__(self, seconden: float):
        self.over = max(0.0, float(seconden))

    def neem(self, seconden: float) -> bool:
        """Reserveer wachttijd. False = het budget is op; de caller stopt met retryen."""
        if seconden > self.over:
            return False
        self.over -= seconden
        return True


def haal_tekst_geduldig(url: str, *, pogingen: int = 3, pauze: float = 2.0,
                        budget: "Wachtbudget | None" = None, _fetch=None, _sleep=None) -> dict:
    """`haal_tekst`, maar met backoff op een TIJDELIJKE fout. Permanente fouten vliegen direct door.

    Waarom dit bestaat: een pagina-set achter elkaar ophalen levert bij Shopify (en de meeste CDN's)
    een 429 op de tweede of derde pagina. Zonder retry wordt zo'n pagina stil overgeslagen en meldt
    de scan dat de site schoon is. Dat is de duurste fout die deze module kan maken.

    De wachttijd komt van de HÓST als die het zegt (`Retry-After`), anders van een verdubbelende
    backoff (2s, 4s). Zelf 2 seconden verzinnen terwijl de host 60 vraagt levert gewoon een tweede
    429 en de onterechte conclusie dat de pagina onbereikbaar is. `budget` begrenst de totale
    wachttijd over een hele pagina-set; `_sleep` is injecteerbaar zodat een test de backoff kan
    bewijzen zonder te wachten."""
    slaap = _sleep if _sleep is not None else time.sleep
    for poging in range(1, max(1, pogingen) + 1):
        try:
            return haal_tekst(url, _fetch=_fetch)
        except (FetchGeweigerd, FetchMislukt) as e:
            if not is_tijdelijk(e) or poging >= max(1, pogingen):
                raise
            gevraagd = getattr(e, "retry_after", None)
            wacht = min(float(gevraagd) if gevraagd else pauze * (2 ** (poging - 1)), MAX_PAUZE)
            if budget is not None and not budget.neem(wacht):
                log.info("fetch %s: %s — wachtbudget op (%.0fs nodig), volgende keer opnieuw",
                         url, e, wacht)
                raise
            log.info("fetch %s: %s — poging %d/%d, %.1fs wachten%s", url, e, poging, pogingen,
                     wacht, " (door de host gevraagd)" if gevraagd else "")
            slaap(wacht)
    raise AssertionError("onbereikbaar")             # pragma: no cover — de lus raakt dit niet


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
        raise FetchMislukt(f"de bron gaf HTTP {status}", status=status)
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
