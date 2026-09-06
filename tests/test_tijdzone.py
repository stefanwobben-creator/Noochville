"""Tijd op het scherm staat in de zone van de LEZER, niet van de server.

Op 6 september 2026 bleek het cockpit twee uur achter te lopen: de server draait UTC, de mensen die
het lezen zitten in CEST. Er stond niets fout — de tijdstempels klopten, ze werden alleen in de
verkeerde zone getoond.

Wat deze tests vastleggen:

1. De weergave gebruikt een instelbare zone, niet de servertijd.
2. Kapotte invoer geeft nooit een crash: een pagina die niet laadt is erger dan een verkeerd uur.
3. Een onbekende zone valt terug op UTC in plaats van te weigeren.
4. De OPSLAG blijft epoch en de periode-sleutels blijven UTC. Dat is geen omissie maar de reden dat
   dit een weergave-probleem was en geen datamigratie: een dagreeks mag niet twee keer 02:30 hebben
   in de nacht dat de klok terugloopt.
"""
from __future__ import annotations

import datetime

from nooch_village.cockpit2_util import _stamp, lokaal

# 2026-09-06 15:23:43 UTC — het moment waarop dit aan het licht kwam.
TS = datetime.datetime(2026, 9, 6, 15, 23, 43, tzinfo=datetime.timezone.utc).timestamp()


def test_amsterdam_is_twee_uur_later_dan_utc():
    assert lokaal(TS, settings={"display_timezone": "Europe/Amsterdam"}) == "2026-09-06 17:23"
    assert lokaal(TS, settings={"display_timezone": "UTC"}) == "2026-09-06 15:23"


def test_default_is_de_thuiszone_en_niet_de_serverzone(monkeypatch):
    monkeypatch.delenv("display_timezone", raising=False)
    assert lokaal(TS, settings={}) == "2026-09-06 17:23"


def test_zone_mag_uit_de_omgeving_komen(monkeypatch):
    monkeypatch.setenv("display_timezone", "Asia/Tokyo")
    assert lokaal(TS, settings={}) == "2026-09-07 00:23"          # +9, dus de volgende dag


def test_onbekende_zone_valt_terug_op_utc_zonder_te_breken():
    assert lokaal(TS, settings={"display_timezone": "Mars/Olympus"}) == "2026-09-06 15:23"


def test_lege_en_kapotte_invoer_geeft_een_streepje():
    for slecht in (None, "", 0, "geen getal", object()):
        assert lokaal(slecht, settings={"display_timezone": "UTC"}) == "—"


def test_eigen_leeg_teken():
    assert lokaal(None, leeg="") == ""


def test_stamp_staat_in_dezelfde_zone():
    """De meest gelezen tijd in het cockpit: onder elke wall-bubbel."""
    assert _stamp(TS, {"display_timezone": "Europe/Amsterdam"}) == "6 Sep 2026, 17:23"
    assert _stamp(TS, {"display_timezone": "UTC"}) == "6 Sep 2026, 15:23"


def test_stamp_zonder_tijd_is_leeg_en_crasht_niet():
    assert _stamp(None) == ""
    assert _stamp("rommel") == ""


def test_periode_sleutels_blijven_utc():
    """De dagreeksen en de idempotentie-poorten van de periodieke skills hangen hierop.

    Zou `period_key` de lezer-zone volgen, dan verschuift de weeknummering met de kijker mee en is
    'deze week al gescand' niet meer één feit. Weergave is per lezer; een periode is dat niet."""
    from nooch_village.checklists import period_key
    middernacht_utc = datetime.datetime(2026, 9, 6, 23, 30, tzinfo=datetime.timezone.utc)
    assert period_key("dag", middernacht_utc) == "2026-09-06"     # niet de 7e, ook al is het dat in CEST
