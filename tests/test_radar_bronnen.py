"""De bronnen-teller die de radar-opruiming overleefde (fase 4, 19 september 2026).

`radar_clusters.py` is weg met de beoordelingslaag: geen embeddings, geen wachtrij, geen
trend-berekening. Dit ene idee is apart gezet omdat het maandrapport het weer nodig heeft, en
omdat het het enige deel van die keten was dat ook zonder wachtrij klopt: **tel bronnen, geen
vermeldingen.** Acht keer mycelium uit één feed is één bron die zichzelf herhaalt.

Het stuk had tot nu toe alleen dekking via de clustering eromheen. Nu het los staat, staat de
eis er ook los.
"""
from __future__ import annotations

import time

from nooch_village.radar_bronnen import bron_van, bronnen_van, tijdstip

DAG = 86400


# ── bron_van: de volgorde van de herkomst-velden ─────────────────────────────
def test_het_source_veld_wint():
    assert bron_van({"source": "FashionUnited.com", "link": "https://ander.nl/x",
                     "feed": "Industry Watch"}) == "fashionunited.com"


def test_zonder_source_telt_de_host_uit_de_link():
    assert bron_van({"link": "https://www.vogue.com/artikel/1"}) == "www.vogue.com"


def test_zonder_source_en_link_telt_de_feed():
    assert bron_van({"feed": "Material Innovation"}) == "material innovation"


def test_niets_bekend_is_een_bron_en_niet_geen_bron():
    """Acht signalen zonder herkomst mogen niet als acht onafhankelijke bevestigingen tellen —
    dat is precies de fout die de teller moest voorkomen."""
    leeg = [{}, {"source": ""}, {"link": ""}]
    assert bron_van({}) == "onbekend"
    assert bronnen_van(leeg) == {"onbekend"}


# ── bronnen_van: het getal dat een trend aanwijst ────────────────────────────
def test_acht_vermeldingen_uit_een_feed_zijn_een_bron():
    leden = [{"source": "fashionunited.com"} for _ in range(8)]
    assert bronnen_van(leden) == {"fashionunited.com"}


def test_acht_bronnen_zijn_acht_bronnen():
    leden = [{"source": f"bron{i}.com"} for i in range(8)]
    assert len(bronnen_van(leden)) == 8


def test_hoofdletters_maken_geen_tweede_bron():
    assert len(bronnen_van([{"source": "Vogue.com"}, {"source": "vogue.com"}])) == 1


# ── tijdstip: publicatie boven ingest ────────────────────────────────────────
def test_published_at_wint_van_het_ingest_moment():
    """Een oud artikel dat vandaag binnenkomt is historisch bewijs, geen vers nieuws."""
    nu = time.time()
    oud = {"published_at": "2024-01-15T09:00:00Z", "at": nu}
    assert tijdstip(oud) < nu - 365 * DAG


def test_zonder_publicatiedatum_telt_het_ingest_moment():
    assert tijdstip({"at": 1700000000.0}) == 1700000000.0


def test_een_onleesbare_datum_valt_terug_en_crasht_niet():
    assert tijdstip({"published_at": "gisteren", "at": 42}) == 42.0
    assert tijdstip({"published_at": "gisteren"}) == 0.0
    assert tijdstip({}) == 0.0
