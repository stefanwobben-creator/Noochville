"""BelofteStore + het /belofte-scherm: de graaf persisteren en van kaal naar rijp tonen."""
import os

from nooch_village import cockpit2
from nooch_village.belofte_store import BelofteStore, seed_schoen_graaf
from nooch_village.belofte_graaf import Constituent, Oordeel, Sterkte
from nooch_village.data_bom import SCHOEN_BELOFTE_ID


def _store(tmp_path):
    return BelofteStore(str(tmp_path / "belofte_grafen.json"))


def test_seed_idempotent_en_bewaart_grondingen(tmp_path):
    s = _store(tmp_path)
    assert seed_schoen_graaf(s) is True
    entry = s.get(SCHOEN_BELOFTE_ID)
    assert entry and len(entry["constituenten"]) == 23      # 23 onderdelen, kop weg
    # kaal: alles onbekend → onbewezen, bottleneck = alle 23
    w = s.weeg(SCHOEN_BELOFTE_ID)
    assert w.sterkte == Sterkte.ONBEWEZEN and len(w.bottleneck) == 23
    # grond één onderdeel als 'houdt niet' → graaf breekt daar
    s.grond(SCHOEN_BELOFTE_ID, "Glue / cement", Oordeel.HOUDT_NIET, grounds="latex uit rubber")
    w2 = s.weeg(SCHOEN_BELOFTE_ID)
    assert w2.sterkte == Sterkte.GEBROKEN and "Glue / cement" in w2.gebroken_op
    # her-seed gooit die grounding NIET weg
    assert seed_schoen_graaf(s) is False
    hergrond = next(r for r in s.get(SCHOEN_BELOFTE_ID)["constituenten"]
                    if r["naam"] == "Glue / cement")
    assert hergrond["oordeel"] == "houdt_niet" and hergrond["grounds"] == "latex uit rubber"


def test_grond_onbekend_belofte_faalt_zacht(tmp_path):
    s = _store(tmp_path)
    assert s.grond("bestaat-niet", "x", Oordeel.HOUDT) is None
    assert s.weeg("bestaat-niet") is None


def test_grond_ongeldig_oordeel_valt_terug(tmp_path):
    s = _store(tmp_path)
    s.zet_graaf("b1", "test", [Constituent("x")])
    row = s.grond("b1", "x", "misschien")            # geen geldig Oordeel
    assert row["oordeel"] == Oordeel.ONBEKEND.value


def test_scherm_toont_sterkte_en_bottleneck(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)                           # seed loopt mee
    html = cockpit2.render_belofte(dd)
    assert "Beloftes" in html and "onbewezen" in html
    detail = cockpit2.render_belofte(dd, SCHOEN_BELOFTE_ID)
    assert "Glue / cement" in detail and "Outsole" in detail
    assert "hemp fabric" in detail                    # alternatief zichtbaar
    assert "bottleneck" in detail.lower()


def test_scherm_onbekende_belofte(tmp_path):
    dd = str(tmp_path / "poc2")
    cockpit2._bootstrap(dd)
    assert "Onbekende belofte" in cockpit2.render_belofte(dd, "zomaar-iets")
