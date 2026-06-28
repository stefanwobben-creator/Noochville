"""Guard: 'reference, don't copy' — indicator-waarden mogen niet als literal in cockpit2 staan.
Een canonieke waarde (PCF, conventioneel, benchmark) leeft in de catalogus-definitie (`waarde`),
nooit als magisch getal in de view-code."""
from __future__ import annotations

import re

from nooch_village import cockpit2


def test_co2_constanten_niet_gehardcode():
    src = open(cockpit2.__file__, encoding="utf-8").read()
    # de oude hardcoded PCF/conventioneel mogen niet (meer) als constante in de code staan
    assert "_CO2_NOOCH_PCF" not in src and "_CO2_CONVENTIONEEL" not in src
    assert not re.search(r"=\s*4\.75\b", src), "PCF 4.75 hoort in de catalogus, niet in code"
    assert not re.search(r"=\s*13\.6\b", src), "conventioneel 13.6 hoort in de catalogus, niet in code"


def test_canonieke_waarde_leeft_in_catalogus(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    # de PCF leeft als definitie-`waarde` in de catalogus (één bron), niet in de code
    cur = st.defs.current(st.defs.by_name("CO2 per paar")["id"])
    assert cur["waarde"] == 4.75
