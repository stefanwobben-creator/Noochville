"""Een verbroken verbinding is geen fout van ons — en mag dus geen grafsteen achterlaten.

De browser breekt af (de gebruiker navigeert weg, of een fetch-timeout zoals `AI_TIMEOUT_MS` in de
wizard verloopt) en pas dáárna komt ons antwoord aan bij een socket die al dicht is. Tot 29 aug 2026
gaf dat een BrokenPipeError met volledige traceback, die de `except Exception` van de route opving en
omzette in een HTTP 500 — een 500 die niemand meer kón ontvangen.

Op prod stonden zo vier `/wizard/plan`-"fouten" in het log die in werkelijkheid vier VOLTOOIDE
checklists waren. Dat is de dure kant: het log wees naar het endpoint terwijl het probleem de
traagheid ervóór was, en het werk zelf was af.
"""
from __future__ import annotations

import logging
from http.server import HTTPServer

from nooch_village import cockpit2


def _handler(tmp_path):
    """Een handler-instantie zonder socket: we testen alleen `_schrijf`, niet de HTTP-laag."""
    cls = cockpit2.make_handler(str(tmp_path), "t")
    h = object.__new__(cls)
    h.path = "/wizard/plan"
    return h


class _DichteSocket:
    """Een wfile die zich gedraagt als een client die al weg is."""

    def __init__(self, fout=BrokenPipeError):
        self.fout, self.pogingen = fout, 0

    def write(self, b):
        self.pogingen += 1
        raise self.fout(32, "Broken pipe")


def test_een_gesloten_verbinding_gooit_niet_door(tmp_path):
    h = _handler(tmp_path)
    h.wfile = _DichteSocket()
    assert h._schrijf(b'{"items":[]}') is False          # geen exceptie: de route loopt netjes uit
    assert h.wfile.pogingen == 1                         # en probeert het niet nóg eens


def test_ook_een_reset_door_de_client_telt(tmp_path):
    """ConnectionReset is dezelfde gebeurtenis vanaf de andere kant; niet een apart geval."""
    h = _handler(tmp_path)
    h.wfile = _DichteSocket(ConnectionResetError)
    assert h._schrijf(b"x") is False


def test_een_echte_schrijffout_wordt_wel_doorgegeven(tmp_path):
    """FAIL-CLOSED op de rest. Alleen 'de client is weg' is onschuldig; een kapotte schijf of een
    encoding-fout is een echte storing en moet zichtbaar blijven."""
    h = _handler(tmp_path)

    class _Stuk:
        def write(self, b):
            raise OSError(5, "Input/output error")
    h.wfile = _Stuk()
    try:
        h._schrijf(b"x")
    except OSError:
        return
    raise AssertionError("een echte I/O-fout werd stilgezwegen")


def test_een_geslaagde_schrijfactie_meldt_dat(tmp_path):
    h = _handler(tmp_path)

    class _Ok:
        def __init__(self): self.gezien = b""
        def write(self, b): self.gezien += b
    h.wfile = _Ok()
    assert h._schrijf(b"hallo") is True
    assert h.wfile.gezien == b"hallo"


def test_het_vertrek_wordt_wel_gelogd(tmp_path, caplog):
    """Stil wegslikken is de andere fout. Een vertrokken client is een signaal over TRAAGHEID —
    het is de enige plek waar je ziet dat het antwoord te laat kwam."""
    h = _handler(tmp_path)
    h.wfile = _DichteSocket()
    with caplog.at_level(logging.INFO, logger="cockpit2"):
        h._schrijf(b"x")
    assert any("/wizard/plan" in r.getMessage() for r in caplog.records), caplog.text


def test_elk_antwoordpad_gaat_door_de_helper():
    """EEN MECHANIEK PER DING (docs/CONVENTIES.md). Een tweede `wfile.write` buiten de helper is
    precies hoe deze grafsteen terugkomt: op één route dan wel, op de volgende niet."""
    import inspect
    bron = inspect.getsource(cockpit2.make_handler)
    losse = [r.strip() for r in bron.splitlines()
             if "self.wfile.write" in r and "return True" not in r]
    assert len(losse) == 1, ("elk antwoord hoort via `self._schrijf(...)` te gaan; gevonden losse "
                             f"schrijfacties: {losse}")
