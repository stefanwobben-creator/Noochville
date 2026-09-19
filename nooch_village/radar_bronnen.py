"""radar_bronnen.py — de bronnen-teller van de radar, losgemaakt uit `radar_clusters`.

WAAROM DIT APART BLIJFT STAAN. De radar telde vermeldingen, en dat is het verkeerde getal. Acht
keer mycelium uit één feed is één bron die zichzelf herhaalt; acht keer mycelium uit acht bronnen
is een trend. Wie op vermeldingen stuurt wordt geregeerd door de meest luidruchtige feed.

De rest van `radar_clusters.py` — de embedding-laag, de lexicale terugval, de trend-berekening en
de besluit-store — is op 19 september 2026 verwijderd met de beoordelingslaag (fase 4). Er is geen
wachtrij meer die geclusterd moet worden: feeds landen ongefilterd in de swipefile. Dít stuk
overleeft omdat het maandrapport het weer nodig heeft, en omdat het het enige idee in die hele
keten was dat los van de wachtrij klopt.

Geen I/O, geen model, geen store. Twee functies en een tijdstempel-lezer.
"""
from __future__ import annotations

import datetime


def bron_van(item: dict) -> str:
    """De bron van één signaal, genormaliseerd tot iets telbaars.

    Volgorde: het `source`-veld (de host die de ingest vastlegde: 'fashionunited.com'), anders de
    host uit de link, anders de feed. Leeg → "onbekend", en dat is één bron, geen n bronnen: acht
    signalen zonder herkomst mogen niet als acht onafhankelijke bevestigingen tellen."""
    bron = str(item.get("source") or "").strip().lower()
    if bron:
        return bron
    link = str(item.get("link") or "").strip().lower()
    if link:
        host = link.split("//", 1)[-1].split("/", 1)[0]
        if host:
            return host
    return str(item.get("feed") or "").strip().lower() or "onbekend"


def bronnen_van(leden: list[dict]) -> set[str]:
    """De VERSCHILLENDE bronnen in een groep signalen. Dit is het getal dat een trend aanwijst; het
    aantal signalen is dat niet. Acht vermeldingen uit één feed geven hier 1 terug."""
    return {bron_van(i) for i in leden}


def tijdstip(item: dict) -> float:
    """Het moment waarop dit signaal telt: de publicatiedatum van het artikel als die er is, anders
    het moment van ingest. Een oud artikel dat vandaag binnenkomt is historisch bewijs, geen vers
    nieuws — dat onderscheid maakt `RadarStore.add` al, en een rapport hoort het te respecteren."""
    rauw = str(item.get("published_at") or "").strip()
    if rauw:
        try:
            dt = datetime.datetime.fromisoformat(rauw.replace("Z", "+00:00"))
            return dt.timestamp()
        except ValueError:
            pass
    try:
        return float(item.get("at") or 0.0)
    except (TypeError, ValueError):
        return 0.0
