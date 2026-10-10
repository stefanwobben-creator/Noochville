"""Na `cn_zaad` heeft geen Critical/Smart Number-tegel een interne sleutel als titel, en elke tegel
een definitie (gevonden bij de uitrol van 11 oktober: de CN1-tegel heette "cn1_batch4")."""
from __future__ import annotations

from nooch_village import cockpit2, critical_numbers, zicht
from nooch_village.views.metrics import _grondslag, _tile_meta

from tests.test_finance_pr1 import _dorp

TE_CONTROLEREN = ("cn1_batch4", "cn2_runway", "cn3_substantiated", "cn3_deferred")


def test_geen_interne_sleutel_als_titel_en_elke_tegel_een_definitie(tmp_path):
    dd = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    cfg = critical_numbers.laad()
    critical_numbers.zaai(st.metrics, cfg, apply=True)
    kijker = zicht.voor(cockpit2._Stores(dd), "stefan@nooch.earth")
    rec = kijker.records.get(cfg["kring"])
    tegels = {t["cn"]: t for t in kijker.metrics.tiles_of(cfg["kring"]) if t.get("cn")}
    titels = {n["sleutel"]: n["titel"] for n in cfg["nummers"]}
    for cn in TE_CONTROLEREN:
        t = tegels[cn]
        titel = _tile_meta(kijker, rec, t)
        assert t["measure"] not in titel.split(":")[-1] and cn not in titel, (cn, titel)
        assert titels[cn] in titel or cn.startswith("cn2_"), (cn, titel)
        assert _grondslag(kijker, t["source"], t["measure"])["definitie"], cn
    assert "Batch 4 sold" in _tile_meta(kijker, rec, tegels["cn1_batch4"])


def test_dry_run_meldt_hetzelfde_als_de_echte_run(tmp_path):
    dd = _dorp(tmp_path)
    cfg = critical_numbers.laad()
    droog = critical_numbers.zaai(cockpit2._Stores(dd).metrics, cfg, apply=False)
    echt = critical_numbers.zaai(cockpit2._Stores(dd).metrics, cfg, apply=True)
    assert droog == echt
    assert {"sleutel": "cn3_deferred", "titel": "Deferred questions", "actie": "add"} in droog


def test_een_bronwissel_neemt_de_dimensie_mee(tmp_path):
    """De cash-tegel van #702 (een KPI met dimensie "none") wordt `runway/cash` met dimensie
    "totaal" — anders eindigt de titel op "· none"."""
    dd = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    cfg = critical_numbers.laad()
    kring = cfg["kring"]
    t = st.metrics.add_tile(kring, "kpi:oud", "value", "none", "getal", extra={"cn": "cn2_cash"})
    critical_numbers.zaai(st.metrics, cfg, apply=True)
    t = next(x for x in cockpit2._Stores(dd).metrics.tiles_of(kring) if x.get("cn") == "cn2_cash")
    assert (t["source"], t["measure"], t["dim"]) == ("runway", "cash", "totaal")
    kijker = zicht.voor(cockpit2._Stores(dd), "stefan@nooch.earth")
    assert not _tile_meta(kijker, kijker.records.get(kring), t).endswith("none")
