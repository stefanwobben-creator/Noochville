"""CN3 "Substantiated pages" (10 oktober 2026): de cijfers, het zaaien als tegel, en de open vragen."""
from __future__ import annotations

import json
import types
from types import SimpleNamespace

from nooch_village import cockpit2, critical_numbers, wiki_dekking as wd
from nooch_village.views.open_vragen import render_open_vragen

C = "mother_earth__nooch"
OWNER = "mother_earth__nooch__creator_of_shoes"
GEZIEN = {"door": "Stefan", "op": "2026-10-06"}


def _pagina(pid, body="", feiten=None):
    return SimpleNamespace(id=pid, title=pid, body=body, meta={"feiten": feiten or []},
                           kind="note", status="active", anchor=OWNER)


def _feit(fid, gezien=None):
    f = {"id": fid, "tekst": "x", "grond": {"soort": "bron", "url": "https://x", "citaat": "", "ref": ""}}
    if gezien:
        f["gezien"] = gezien
    return f


def _dek(*rijen):
    return wd.dekking({"rijen": [{"part": p, "materiaal": m, "mat": mp, "supplier": s, "lev": lp}
                                 for p, m, mp, s, lp in rijen]}, vandaag="2026-10-10")


# ── de cijfers ──────────────────────────────────────────────────────────────

def test_een_pagina_telt_als_alles_erop_gecheckt_is_ook_zonder_feiten():
    leeg = _pagina("L")
    goed = _pagina("G", "## Biobased\n{{fact:a}}", [_feit("a", GEZIEN)])
    half = _pagina("H", "## Biobased\n{{fact:a}}", [_feit("a")])
    d = _dek(("A", "Leeg", leeg, "", None), ("B", "Goed", goed, "", None),
             ("C", "Half", half, "", None), ("D", "Geen", None, "", None))
    c = wd.cijfers(d, vandaag="2026-10-10")
    assert (c["gestaafd"], c["paginas_totaal"], c["gestaafd_pct"]) == (2, 4, 50.0)
    assert c["paginas_bestaan"] == 3


def test_laag_1_en_2_koppeling_en_placeholders():
    p = _pagina("P", "## Labor & compliance\n- Living wage verification: not yet provided")
    d = _dek(("A", "Pliant", p, "NFW", _pagina("N")), ("B", "Cotton", None, "", None))
    c = wd.cijfers(d)
    assert (c["materialen"], c["met_leverancier"]) == (2, 1)
    assert c["paginas_zonder_placeholder"] == 1                       # NFW wel, Pliant niet


def test_open_vragen_conflict_eerst_en_lege_rij_zonder_pagina():
    d = _dek(("A", "Cotton", None, "", None))
    vragen = wd.open_vragen(d)
    assert len(vragen) == 7 and {v["status"] for v in vragen} == {wd.LEEG}
    assert wd.cijfers(d)["cellen_open"] == 7


def test_het_dorp_telt_een_materiaal_in_twee_modellen_een_keer():
    rij = {"part": "Vamp", "materiaal": "HyphaLite", "mat": None, "supplier": "", "lev": None}
    d = wd.voor_het_dorp([{"rijen": [rij]}, {"rijen": [dict(rij)]}])
    assert len(d["materialen"]) == 1


# ── zaaien als tegel ────────────────────────────────────────────────────────

def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_het_seed_bestand_heeft_cn3_als_critical_met_doel_100():
    cfg = critical_numbers.laad()
    cn3 = next(n for n in cfg["nummers"] if n["sleutel"] == "cn3_substantiated")
    assert (cfg["kring"], cn3["niveau"], cn3["target"]) == (C, "critical", 100)
    smart = next(n for n in cfg["nummers"] if n["sleutel"] == "cn3_open_questions")
    assert smart["niveau"] == "smart" and smart["target"] is None


def test_zaaien_is_dry_run_dan_idempotent(tmp_path):
    dd = _dd(tmp_path)
    cfg = critical_numbers.laad()
    st = cockpit2._Stores(dd)
    r = critical_numbers.zaai(st.metrics, cfg)
    assert {x["actie"] for x in r} == {"add"} and cockpit2._Stores(dd).metrics.tiles_of(C) == []
    critical_numbers.zaai(st.metrics, cfg, apply=True)
    tiles = {t["cn"]: t for t in cockpit2._Stores(dd).metrics.tiles_of(C)}
    t = tiles["cn3_substantiated"]
    assert (t["niveau"], t["target"], t["eigenaar_domein"]) == ("critical", 100.0, "Materials")
    st = cockpit2._Stores(dd)
    assert {x["actie"] for x in critical_numbers.zaai(st.metrics, cfg, apply=True)} == {"ongewijzigd"}
    assert len(cockpit2._Stores(dd).metrics.tiles_of(C)) == 2
    cfg["nummers"][0]["target"] = 90
    assert critical_numbers.zaai(st.metrics, cfg)[0]["actie"] == "update"


def test_een_nummer_dat_nog_niet_mag_wordt_overgeslagen(tmp_path):
    cfg = {"kring": C, "nummers": [{"sleutel": "cn1", "titel": "Batch 4 sold", "zaai": False,
                                     "reden": "start date of Batch 4 not set"}]}
    r = critical_numbers.zaai(cockpit2._Stores(_dd(tmp_path)).metrics, cfg, apply=True)
    assert r[0]["actie"].startswith("overgeslagen: start date")


def test_de_tegel_toont_de_live_waarde_en_de_eigenaar(tmp_path):
    from nooch_village.views.metrics2 import render_metrics2_tab
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)
    st = cockpit2._Stores(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t")
    assert "<span class='badge'>Critical</span>" in h
    assert "Owner: " in h and "no role holds" not in h
    assert "Off target</span> target 100" in h                         # niets gestaafd in een leeg dorp


# ── de dagbron ──────────────────────────────────────────────────────────────

def test_de_bron_geeft_alle_velden_en_staat_standaard_aan(tmp_path):
    from nooch_village.collector import migrate_data_sources
    from nooch_village.skills_impl.dekking import VELDEN, DekkingSource
    dd = _dd(tmp_path)
    v = DekkingSource().daily_values(types.SimpleNamespace(data_dir=dd), "2026-10-10")
    assert set(v) == set(VELDEN) and v["materialen"] == 14 and v["cellen_open"] > 0
    migrate_data_sources(dd)
    assert cockpit2._Stores(dd).sources.active("dekking")


# ── het scherm ──────────────────────────────────────────────────────────────

def test_open_questions_toont_rijen_en_filtert(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    h = render_open_vragen(st)
    assert "Open questions" in h and "nu-status--open" in h and "(no page yet)" in h
    assert "class='cl-filter on' href='/open-questions'" in h
    leeg = render_open_vragen(st, status="conflict")
    assert "Nothing here." in leeg
    vreemd = render_open_vragen(st, status="<b>x</b>")              # onbekend = alles, nooit echoën
    assert "<b>x</b>" not in vreemd and "class='cl-filter on' href='/open-questions'" in vreemd
