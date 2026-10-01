"""BOM stuk 1: het rekenscherm `/bom` en de kop-bewuste stuklijst eronder (1 oktober 2026)."""
from __future__ import annotations

from nooch_village import bom_reken, cockpit2, wiki
from nooch_village.compositie import bom_rijen, ontleed_bom
from nooch_village.data_bom import NOOCH_SCHOEN_BOM
from nooch_village.views.bom import render_bom

OWNER = "mother_earth__nooch__creator_of_shoes"
KOP = "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\tSupplier\n"


def _bom(*rijen: str) -> str:
    return KOP + "".join(r + "\n" for r in rijen)


# ── de stuklijst: op kopnaam gelezen ────────────────────────────────────────

def test_een_ingevuld_gewicht_wordt_geen_materiaal():
    """De oude lezing nam de laatste twee niet-lege cellen als Part/Material. Met een gewicht en een
    leverancier erachter was het materiaal dan '12' geworden."""
    tekst = _bom("Done\t\tOutsole\tPliant\t\t48\tLTA S.R.L.",
                 "\t\tVamp\tHyphaLite\t< Or hemp fabric\t22\t")
    assert [(c.naam, c.realisatie) for c in ontleed_bom(tekst)] == [("Outsole", "Pliant"),
                                                                    ("Vamp", "HyphaLite")]
    assert ontleed_bom(tekst)[1].alternatieven == ("hemp fabric",)
    assert [(r["gram"], r["supplier"]) for r in bom_rijen(tekst)] == [(48.0, "LTA S.R.L."),
                                                                      (22.0, "")]


def test_de_echte_stuklijst_leest_zoals_voorheen():
    """De kolommen zijn erbij gekomen; wat de belofte-graaf en het wiki-zaad zien niet veranderd."""
    zonder = "\n".join("\t".join(r.split("\t")[:5]) for r in NOOCH_SCHOEN_BOM.splitlines())
    oud = [(c.naam, c.realisatie, c.alternatieven, c.opmerking) for c in ontleed_bom(zonder)]
    nieuw = [(c.naam, c.realisatie, c.alternatieven, c.opmerking) for c in ontleed_bom(NOOCH_SCHOEN_BOM)]
    assert nieuw == oud and len(nieuw) == 23


def test_een_onleesbaar_gewicht_is_open_en_geen_nul():
    tekst = _bom("\t\tA\tX\t\t12,5\t", "\t\tB\tX\t\tveel\t", "\t\tC\tX\t\t-3\t", "\t\tD\tX\t\t\t")
    assert [r["gram"] for r in bom_rijen(tekst)] == [12.5, None, None, None]


def test_de_echte_stuklijst_heeft_nog_geen_verzonnen_cijfers():
    """Het prototype had illustratieve gewichten; die horen hier niet als echt te staan."""
    assert all(r["gram"] is None and r["supplier"] == "" for r in bom_rijen(NOOCH_SCHOEN_BOM))


# ── de rekenlaag ────────────────────────────────────────────────────────────

def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _pagina(st, titel, *waarden):
    a = st.att.add(OWNER, "note", title=titel)
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit(f"{g} volgens de bron", soort="bron",
                                                        url="https://x", waarde=wiki.maak_waarde(g, n))
                                         for g, n in waarden]})
    return a


def test_de_totalen_vermenigvuldigen_en_tellen_wat_meetelt(tmp_path):
    _dd, st = _dorp(tmp_path)
    _pagina(st, "Helios 200", ("co2e_per_kg", "2"), ("water_per_kg", "100"))
    _pagina(st, "LTA S.R.L.", ("prijs_per_kg", "50"))
    tekst = _bom("\t\tHeel counter\tHelios 200\t\t10\tLTA S.R.L.",
                 "\t\tLaces\tCotton laces\t\t5\t")
    uit = bom_reken.bereken(tekst, wiki.paginas(cockpit2._Stores(_dd).att))
    t = uit["totalen"]
    assert t["gram"] == {"som": 15.0, "n": 2, "m": 2}
    assert t["co2e"]["n"] == 1 and abs(t["co2e"]["som"] - 0.02) < 1e-9     # 10 g × 2 kg/kg
    assert t["water"]["n"] == 1 and abs(t["water"]["som"] - 1.0) < 1e-9    # 10 g × 100 L/kg
    assert t["prijs"]["n"] == 1 and abs(t["prijs"]["som"] - 0.5) < 1e-9    # 10 g × €50/kg
    open_laces = uit["rijen"][1]["open"]
    assert any("no material page" in o for o in open_laces) and "no supplier" in open_laces
    assert uit["rijen"][0]["open"] == []


def test_twee_waarden_voor_dezelfde_grootheid_tellen_niet_mee(tmp_path):
    """Welke van de twee het is, is een besluit van de eigenaar — niet van deze code."""
    _dd, st = _dorp(tmp_path)
    _pagina(st, "Helios 200", ("co2e_per_kg", "2"), ("co2e_per_kg", "3"))
    uit = bom_reken.bereken(_bom("\t\tA\tHelios 200\t\t10\t"), wiki.paginas(cockpit2._Stores(_dd).att))
    assert uit["totalen"]["co2e"]["n"] == 0
    assert any("more than one value" in o for o in uit["rijen"][0]["open"])


def test_zonder_gewicht_telt_een_factor_niet_mee(tmp_path):
    _dd, st = _dorp(tmp_path)
    _pagina(st, "Helios 200", ("co2e_per_kg", "2"))
    uit = bom_reken.bereken(_bom("\t\tA\tHelios 200\t\t\t"), wiki.paginas(cockpit2._Stores(_dd).att))
    assert uit["totalen"]["co2e"]["n"] == 0 and "weight not filled in" in uit["rijen"][0]["open"]


# ── het scherm ──────────────────────────────────────────────────────────────

def test_het_scherm_zegt_eerlijk_op_hoeveel_het_rust(tmp_path):
    _dd, st = _dorp(tmp_path)
    html = render_bom(st)
    assert html.count("based on 0 of 23 components") == 4
    assert "Still open" in html and "weight not filled in" in html
    assert "class='mtab'" in html and "class='tile'" in html
    assert "style=" not in html.split("<body")[1].split("<script")[0].replace("<style", "")


def test_een_materiaal_met_pagina_linkt_ernaartoe(tmp_path):
    _dd, st = _dorp(tmp_path)
    a = st.att.add(OWNER, "note", title="Pliant")
    assert f"href='{wiki.pagina_url(a.id)}'>Pliant</a>" in render_bom(cockpit2._Stores(_dd))


def test_de_route_en_de_toolkaart(tmp_path):
    from nooch_village.views.tools import render_tools
    _dd, st = _dorp(tmp_path)
    assert "href='/bom'" in render_tools(st) or 'href="/bom"' in render_tools(st)
