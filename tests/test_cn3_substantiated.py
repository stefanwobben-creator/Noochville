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

def _uitgesteld(pid, tot, *vragen_, body="", feiten=None):
    """Een pagina waarop deze vragen deferred zijn tot `tot`."""
    p = _pagina(pid, body, feiten)
    p.meta[wd.UITSTEL_SLEUTEL] = {k: {"tot": tot, "eigenaar": OWNER} for k in vragen_}
    return p


ALLE_MAT = ("plastic", "biobased", "animal", "chem", "co2", "water", "cert")
ALLE_LEV = ("loc", "cert", "price", "labor", "own")


def test_een_pagina_telt_als_elk_veld_gecheckt_of_geldig_deferred_is():
    """De regel sinds de aanvulling "deferred": elk veld gecheckt of deferred met een datum die nog
    niet voorbij is, geen ongecheckt feit, en bij een materiaal een leverancier."""
    lev = _uitgesteld("Lev", "2026-12-31", *ALLE_LEV)
    goed = _uitgesteld("Goed", "2026-12-31", *ALLE_MAT)
    verlopen = _uitgesteld("Verlopen", "2026-10-01", *ALLE_MAT)          # datum voorbij
    half = _uitgesteld("Half", "2026-12-31", *ALLE_MAT[:-1])             # cert niet deferred
    met_feit = _uitgesteld("Feit", "2026-12-31", *ALLE_MAT,
                           body="## Characteristics\n{{fact:a}}", feiten=[_feit("a")])
    d = _dek(("A", "Goed", goed, "Lev", lev), ("B", "Verlopen", verlopen, "Lev", lev),
             ("C", "Half", half, "Lev", lev), ("D", "Feit", met_feit, "Lev", lev),
             ("E", "Zonder leverancier", _uitgesteld("Z", "2026-12-31", *ALLE_MAT), "", None))
    gestaafd = {r["naam"] for r in d["materialen"] + d["leveranciers"] if wd.gestaafd(r, vandaag="2026-10-10")}
    assert gestaafd == {"Goed", "Lev"}


def test_een_lege_pagina_telt_niet_meer():
    d = _dek(("A", "Leeg", _pagina("L"), "Lev", _pagina("Lev")))
    assert not any(wd.gestaafd(r, vandaag="2026-10-10") for r in d["materialen"] + d["leveranciers"])


def test_deferred_apart_geteld_en_verlopen_valt_terug_op_leeg():
    p = _uitgesteld("P", "2026-12-31", "plastic", "biobased")
    p.meta[wd.UITSTEL_SLEUTEL]["chem"] = {"tot": "2026-10-01", "eigenaar": OWNER}       # verlopen
    d = _dek(("A", "P", p, "", None))
    cel = d["materialen"][0]["cellen"]
    assert (cel["plastic"]["status"], cel["plastic"]["tot"]) == (wd.UITGESTELD, "2026-12-31")
    assert cel["chem"]["status"] == wd.LEEG and cel["chem"]["verlopen"]
    c = wd.cijfers(d, vandaag="2026-10-10")
    assert (c["cellen_deferred"], c["cellen_deferred_verlopen"], c["cellen_checked"], c["cellen_open"]) == \
           (2, 1, 0, 5)


def test_uitstel_vraagt_datum_en_eigenaar():
    assert wd.maak_uitstel("2026-12-31", OWNER)["tot"] == "2026-12-31"
    assert wd.maak_uitstel("", OWNER) is None and wd.maak_uitstel("2026-12-31", "") is None
    assert wd.maak_uitstel("31-12-2026", OWNER) is None


def test_deferred_verbergt_alleen_de_placeholders_van_die_vraag():
    """Sinds 11 oktober: de regel wordt niet uit de tekst gehaald maar bij het tonen afgeleid."""
    body = ("## Open items\n- Animal-derived status: not yet verified\n"
            "- Dye/chemical disclosure: not yet provided\n- Eigen notitie")
    rij = _dek(("A", "P", _uitgesteld("P", "2026-12-31", "chem", body=body), "", None))["materialen"][0]
    assert set(wd.verborgen_placeholders(rij)) == {"Dye/chemical disclosure: not yet provided"}
    assert rij["pagina"].body == body                                     # de tekst is onaangeroerd
    lev = _dek(("A", "M", None, "NFW", _uitgesteld("N", "2026-12-31", "labor")))["leveranciers"][0]
    assert set(wd.verborgen_placeholders(lev)) == {
        "Facility address: not yet provided", "Living wage verification: not yet provided",
        "Compliance policies (modern slavery, child labor, health & safety, anti-discrimination, "
        "union rights): not yet provided"}


def test_open_vragen_deferred_achteraan_op_research_by():
    p = _uitgesteld("P", "2026-12-31", "plastic")
    p.meta[wd.UITSTEL_SLEUTEL]["biobased"] = {"tot": "2026-11-01", "eigenaar": OWNER}
    vragen_ = wd.open_vragen(_dek(("A", "P", p, "", None)))
    deferred = [v for v in vragen_ if v["status"] == wd.UITGESTELD]
    assert [v["k"] for v in deferred] == ["biobased", "plastic"]          # vroegste datum eerst
    assert vragen_[-1]["status"] == wd.UITGESTELD


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
    assert (t["niveau"], t["target"]) == ("critical", 100.0)
    assert t["eigenaar_rol"] == "mother_earth__nooch__factory_sourcing_manager"
    assert t["lijn"] == {"van": "2026-10-10", "tot": "2026-12-31", "start": 0.0, "oranje": 0.8}
    st = cockpit2._Stores(dd)
    assert {x["actie"] for x in critical_numbers.zaai(st.metrics, cfg, apply=True)} == {"ongewijzigd"}
    assert len(cockpit2._Stores(dd).metrics.tiles_of(C)) == sum(1 for n in cfg["nummers"]
                                                                   if n.get("tegel") is not False)
    cn3 = next(n for n in cfg["nummers"] if n["sleutel"] == "cn3_substantiated")
    cn3["target"] = 90
    r = {x["sleutel"]: x["actie"] for x in critical_numbers.zaai(st.metrics, cfg)}
    assert r["cn3_substantiated"] == "update" and r["cn3_open_questions"] == "ongewijzigd"


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
    assert "target 100 by 2026-12-31" in h                             # de lijn, welke dag het ook is


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


# ── de lijn naar het doel (stap 1, 10 oktober 2026) ─────────────────────────

def test_de_lijn_loopt_van_start_naar_doel_en_kleurt_80_procent():
    from nooch_village.metrics import GROEN, ORANJE, ROOD, lijn_status, lijn_waarde, maak_lijn
    lijn = maak_lijn("2026-10-01", "2026-12-31", start=0, oranje=0.8)
    assert lijn_waarde(lijn, 100, "2026-09-30") is None                # vóór de start: niets
    assert lijn_waarde(lijn, 100, "2026-10-01") == 0
    assert abs(lijn_waarde(lijn, 100, "2026-11-15") - 49.45) < 0.1   # halverwege ~ de helft
    assert lijn_waarde(lijn, 100, "2027-02-01") == 100                 # na de deadline: het doel
    assert lijn_status(50, 100, lijn, "2026-11-15") == GROEN
    assert lijn_status(40, 100, lijn, "2026-11-15") == ORANJE          # ≥ 80% van ~49
    assert lijn_status(30, 100, lijn, "2026-11-15") == ROOD
    assert lijn_status(0, 100, lijn, "2026-09-01") == ""


def test_een_ongeldige_lijn_wordt_geweigerd():
    from nooch_village.metrics import maak_lijn
    assert maak_lijn("2026-12-31", "2026-10-01") is None
    assert maak_lijn("2026-10-01", "2026-12-31", oranje=1.5) is None
    assert maak_lijn("geen datum", "2026-12-31") is None


# ── deferred via de knoppen ─────────────────────────────────────────────────

def _dorp_met_pagina(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # MET DOMEIN: dan mag alleen de houder (of de Circle Lead) de pagina — en dus het uitstel —
    # wijzigen. Op prod hebben de pagina's (nog) geen domein; dan mag elke herkende gebruiker het,
    # precies zoals bij het bewerken van de pagina zelf.
    a = st.att.add(OWNER, "note", title="Pliant", domain="Materials",
                   body="## Dyes & chemicals\nx\n## Open items\n- Dye/chemical disclosure: not yet provided")
    st.bom_materialen.zet("Outsole", "Pliant")
    st.people.add("Buiten", "buiten@t.nl")
    return dd, a.id


def test_defer_en_undo_via_de_actie(tmp_path):
    dd, aid = _dorp_met_pagina(tmp_path)
    form = {"aid": [aid], "soort": ["materiaal"], "k": ["chem"], "tot": ["2026-12-31"], "next": ["/"]}
    import pytest
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "vraag_uitstel", form, username="buiten@t.nl")
    assert "✓" in cockpit2.dispatch(dd, "vraag_uitstel", form, username="guest")[1]
    a = cockpit2._Stores(dd).att.get(aid)
    assert a.meta[wd.UITSTEL_SLEUTEL]["chem"]["tot"] == "2026-12-31"
    assert a.meta[wd.UITSTEL_SLEUTEL]["chem"]["eigenaar"] == OWNER       # de pagina-eigenaar
    assert "not yet provided" in a.body                                 # de tekst blijft (11 okt)
    assert "✗" in cockpit2.dispatch(dd, "vraag_uitstel", dict(form, tot=[""]), username="guest")[1]
    cockpit2.dispatch(dd, "vraag_uitstel_weg", {"aid": [aid], "k": ["chem"], "next": ["/"]}, username="guest")
    assert wd.UITSTEL_SLEUTEL not in cockpit2._Stores(dd).att.get(aid).meta


def test_defer_staat_op_open_questions_en_op_de_wikipagina(tmp_path):
    from nooch_village.views.wiki import render_pagina
    dd, aid = _dorp_met_pagina(tmp_path)
    st = cockpit2._Stores(dd)
    h = render_open_vragen(st, csrf_token="t", username="guest")
    assert "value='vraag_uitstel'" in h and "Research by" in h and ">Deferred" in h
    assert "value='vraag_uitstel'" not in render_open_vragen(st)       # zonder sessie geen knop
    p = render_pagina(st, aid, csrf_token="t", username="guest")
    blok = p[p.index("<h2>Questions and facts</h2>"):]
    assert "Dyes &amp; chemicals" in blok and "value='vraag_uitstel'" in blok
    assert "counts as substantiated: <strong>no</strong>" in blok
