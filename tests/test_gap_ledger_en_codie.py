"""De capaciteit-gat-oogst en de Codie-backlog: van vastgelopen werk naar een probleemstelling."""
from __future__ import annotations

from nooch_village import gap_ledger
from nooch_village.views.codie import render_codie


def _gat(dd, **kw):
    basis = {"role": "harry", "item_text": "haal patentdata op", "project_id": "p1",
             "reason": gap_ledger.MISSING_CAPABILITY, "capability": "patent search API"}
    return gap_ledger.record(dd, **{**basis, **kw})


def test_record_en_teruglezen(tmp_path):
    dd = str(tmp_path)
    rij = _gat(dd, hop_trail=["website_dev"])
    assert rij and rij["reason"] == gap_ledger.MISSING_CAPABILITY
    terug = gap_ledger.alle(dd)
    assert len(terug) == 1 and terug[0]["capability"] == "patent search API"
    assert terug[0]["hop_trail"] == ["website_dev"] and terug[0]["ts"] > 0


def test_onbekende_reden_wordt_geweigerd(tmp_path):
    """Fail-closed op het enige veld dat de backlog stuurt: een gat met een verzonnen reden zou
    stilletjes wél of níét in de dev-backlog belanden."""
    assert _gat(str(tmp_path), reason="omdat het kan") is None
    assert gap_ledger.alle(str(tmp_path)) == []


def test_kapotte_regel_maakt_de_ledger_niet_onleesbaar(tmp_path):
    dd = str(tmp_path)
    _gat(dd)
    with open(gap_ledger.pad(dd), "a", encoding="utf-8") as f:
        f.write("dit is geen json\n")
    _gat(dd, project_id="p2")
    assert len(gap_ledger.alle(dd)) == 2


def test_frequentie_telt_projecten_niet_records(tmp_path):
    """Tien keer vastlopen op hetzelfde project is één geblokkeerd project, geen tienvoudige
    urgentie — anders bepaalt de puls-frequentie de prioriteit in plaats van de impact."""
    dd = str(tmp_path)
    for _ in range(6):
        _gat(dd, capability="veel records", project_id="p1")
    for i in range(3):
        _gat(dd, capability="veel projecten", project_id=f"q{i}")

    top = gap_ledger.clusters(dd)
    assert top[0]["capability"] == "veel projecten" and top[0]["n_projecten"] == 3
    assert top[1]["capability"] == "veel records" and top[1]["n_projecten"] == 1


def test_clusteren_is_hoofdletterongevoelig_en_over_rollen_heen(tmp_path):
    dd = str(tmp_path)
    _gat(dd, capability="Patent Search API", project_id="p1", role="harry")
    _gat(dd, capability="patent search api", project_id="p2", role="compliance")

    cl = gap_ledger.clusters(dd)
    assert len(cl) == 1 and cl[0]["n_projecten"] == 2
    assert [r for r, _n in cl[0]["rollen"]] == ["compliance", "harry"]


def test_zonder_label_klontert_er_niets_verkeerd_samen(tmp_path):
    """Liever een cluster van één dan twee ongerelateerde gaten op één hoop."""
    dd = str(tmp_path)
    _gat(dd, capability="", item_text="iets heel specifieks", project_id="p1")
    _gat(dd, capability="", item_text="iets heel anders", project_id="p2")
    assert len(gap_ledger.clusters(dd)) == 2


def test_alleen_missing_capability_voedt_de_backlog(tmp_path):
    dd = str(tmp_path)
    _gat(dd, capability="patent search API")
    _gat(dd, reason=gap_ledger.HUMAN_EXTERNAL, capability="", item_text="plak de sticker",
         project_id="p9")

    assert [c["capability"] for c in gap_ledger.clusters(dd)] == ["patent search API"]
    mens = gap_ledger.clusters(dd, reason=gap_ledger.HUMAN_EXTERNAL)
    assert len(mens) == 1


def test_probleemstelling_is_geen_code_spec(tmp_path):
    dd = str(tmp_path)
    _gat(dd, project_id="p1")
    _gat(dd, project_id="p2")
    tekst = gap_ledger.probleemstelling(gap_ledger.clusters(dd)[0])
    assert "blokkeerde 2 projecten" in tekst and "harry" in tekst
    assert "Wat een oplossing zou moeten opleveren" in tekst
    for verboden in ("import ", "def ", "class ", "endpoint", "SDK"):
        assert verboden not in tekst


# ── de weergave ────────────────────────────────────────────────────────────────

def test_view_rangschikt_en_toont_de_keten(tmp_path):
    dd = str(tmp_path)
    _gat(dd, capability="klein gat", project_id="p1")
    for i in range(3):
        _gat(dd, capability="groot gat", project_id=f"q{i}", hop_trail=["website_dev"])

    html = render_codie(dd)

    assert html.index("groot gat") < html.index("klein gat")     # frequentie bepaalt de volgorde
    assert "Blokkeerde 3 projecten" in html
    assert "Ging eerst langs" in html and "website_dev" in html  # de hop-keten is terug te lezen
    assert "probleemstellingen, geen specs" in html


def test_view_is_read_only(tmp_path):
    """De mens-poort zit op het pad van gat naar code, niet op dit scherm: geen knoppen, geen forms."""
    dd = str(tmp_path)
    _gat(dd)
    html = render_codie(dd)
    assert "<form" not in html.split("</head>")[1].replace(
        "<form class='c2-search' action='/search' method='get' role='search' autocomplete='off'>", "")
    assert "action='/action'" not in html


def test_view_zonder_gaten_legt_uit_wat_dat_betekent(tmp_path):
    html = render_codie(str(tmp_path))
    assert "Nog geen capaciteitsgaten" in html
    assert "dorpspuls" in html                                    # stilte kan ook 'kapot' betekenen


def test_view_zonder_inline_styles(tmp_path):
    _gat(str(tmp_path))
    assert "style=" not in render_codie(str(tmp_path))
