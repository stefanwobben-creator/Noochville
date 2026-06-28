"""Guard: 'reference, don't copy' — indicator-waarden mogen niet als literal in cockpit2 staan,
maar komen uit de catalogus-definitie (`waarde`). En back-cast-bewijs: verander de definitie en
de afgeleide indicator verandert mee (geen kopie)."""
from __future__ import annotations

import re

from nooch_village import cockpit2


def test_co2_constanten_niet_gehardcode():
    src = open(cockpit2.__file__, encoding="utf-8").read()
    # de oude hardcoded PCF/conventioneel mogen niet meer als constante in de code staan
    assert "_CO2_NOOCH_PCF" not in src and "_CO2_CONVENTIONEEL" not in src
    assert not re.search(r"=\s*4\.75\b", src), "PCF 4.75 hoort in de catalogus, niet in code"
    assert not re.search(r"=\s*13\.6\b", src), "conventioneel 13.6 hoort in de catalogus, niet in code"


def test_co2_vermeden_leest_uit_catalogus(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    base = cockpit2._co2_avoided(st)
    assert base is not None and base > 0
    # reference, don't copy: pas de PCF in de catalogus aan → de afgeleide indicator verandert mee
    pcf = st.defs.by_name("CO2 per paar")
    st.defs.amend(pcf["id"], "clarify", waarde=2.0)   # lagere PCF → meer vermeden
    st2 = cockpit2._Stores(dd)
    higher = cockpit2._co2_avoided(st2)
    assert higher > base, "indicator volgt de catalogus-waarde, geen kopie in code"
    # zonder catalogus-waarde geen verzonnen getal
    st2.defs.amend(pcf["id"], "clarify", waarde="")    # waarde weghalen
    assert cockpit2._co2_avoided(cockpit2._Stores(dd)) is None
