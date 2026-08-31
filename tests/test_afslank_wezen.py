"""Een rol slapend leggen laat zijn open projecten achter.

GEMETEN OP PROD, 31 aug 2026: 13 open projecten op een eigenaar zonder vervuller. Acht daarvan zijn
de individuele-actie-baan van de founder en horen daar. De andere VIJF zijn wezen — 3 op `noochie`,
2 op `facilitator` — en alle vijf ontstonden doordat de rol slapend werd gelegd NÁ het aanmaken.

De afslank-poort vraagt wat er aan een rol HANGT (events, ritme, skills). Wat hij niet vraagt is wat
er OP ZIJN BORD LIGT, en daar viel het werk tussendoor.
"""
from __future__ import annotations

from nooch_village import afslank_wezen as aw
from nooch_village import cockpit2


def _st(tmp_path):
    dd = str(tmp_path / "w")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def test_de_founder_baan_is_geen_wees(tmp_path, monkeypatch):
    """`ii:<cirkel>` is geen rol maar de eigen lijst van de founder: eigenaar zonder vervuller, maar
    mét iemand die kijkt. Acht van de dertien prod-gevallen. Ze meesleuren zou werk verplaatsen dat
    precies staat waar het hoort."""
    dd, st = _st(tmp_path)
    st.projects.create("ii:mother_earth__nooch", "Organize Portugal Trip", "human")
    assert aw.wezen(st) == []


def test_een_rol_die_niets_kan_levert_wel_een_wees(tmp_path, monkeypatch):
    dd, st = _st(tmp_path)
    pid = st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    gevonden = aw.wezen(st)
    assert [w["pid"] for w in gevonden] == [pid]


def test_een_afgerond_project_telt_niet_mee(tmp_path, monkeypatch):
    dd, st = _st(tmp_path)
    pid = st.projects.create("slaper", "Al klaar", "human")
    st.projects.complete(pid, "klaar")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    assert aw.wezen(st) == []


def test_dry_run_schrijft_niets(tmp_path, monkeypatch):
    """Wat er gebeurt is zichtbaar vóór het gebeurt."""
    dd, st = _st(tmp_path)
    st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    geraakt = []
    monkeypatch.setattr(cockpit2, "route_werk", lambda *a, **k: geraakt.append(k) or ("x", "y"))
    res = aw.herrouteer(st, apply=False)
    assert res["gevonden"] == 1 and res["toegepast"] is False and geraakt == []


def test_herrouteren_gebruikt_route_werk_en_geen_tweede_regel(tmp_path, monkeypatch):
    """GEEN NIEUW MECHANIEK. Een tweede routeerregel hier zou na één wijziging uit de pas lopen, en
    dan landt werk stil op de verkeerde plek — precies de fout die #364 wegnam."""
    dd, st = _st(tmp_path)
    st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    gezien = {}

    def _nep(st_, **kw):
        gezien.update(kw)
        return "inbox", "bij de Circle Lead"

    monkeypatch.setattr(cockpit2, "route_werk", _nep)
    res = aw.herrouteer(st, apply=True)
    assert res["toegepast"] is True and "Circle Lead" in res["items"][0]["naar"]
    assert gezien["rol"] == "slaper"
    assert "geen vervuller meer" in gezien["herkomst"], "de herkomst zegt niet waarom het verhuisde"


def test_een_fout_op_een_project_stopt_de_sweep_niet(tmp_path, monkeypatch):
    """Fail-soft per project: één onverwerkbaar geval mag de andere vier niet tegenhouden."""
    dd, st = _st(tmp_path)
    for i in range(3):
        st.projects.create("slaper", f"nummer {i}", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    beurt = {"n": 0}

    def _soms_stuk(st_, **kw):
        beurt["n"] += 1
        if beurt["n"] == 2:
            raise RuntimeError("stuk")
        return "project", "ergens"

    monkeypatch.setattr(cockpit2, "route_werk", _soms_stuk)
    res = aw.herrouteer(st, apply=True)
    assert len(res["items"]) == 3
    assert sum(1 for x in res["items"] if x["naar"].startswith("FOUT")) == 1


def test_het_cli_commando_draait_echt(tmp_path, monkeypatch, capsys):
    """DE TAK ZELF DRAAIEN, want de volle suite (4264 tests) ving een `UnboundLocalError` in dit
    commando niet: geen enkele test voerde hem uit. Hij viel pas om op prod, bij de eerste droge
    run — en dat is precies één stap te laat.

    Een compileerbare tak is geen werkende tak. Deze test roept `main()` aan zoals de shell dat doet,
    tegen een wegwerp-datamap, en zou de fout hebben gevangen vóór hij de server haalde."""
    import sys
    import types

    from nooch_village import cli
    dd = str(tmp_path / "cli")
    cockpit2._bootstrap(dd)
    monkeypatch.setattr("nooch_village.config.load_context",
                        lambda _b: types.SimpleNamespace(data_dir=dd))
    monkeypatch.setattr(sys, "argv", ["village", "afslank_wezen"])
    cli.main()
    uit = capsys.readouterr().out
    assert "wees" in uit or "geen wezen" in uit


def test_zonder_apply_staat_er_dry_run_bij(tmp_path, monkeypatch, capsys):
    """Wat er niet gebeurde, moet net zo duidelijk zijn als wat er wél gebeurde — anders leest een
    droge run als een uitgevoerde."""
    import sys
    import types

    from nooch_village import cli
    dd = str(tmp_path / "cli2")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    monkeypatch.setattr("nooch_village.config.load_context",
                        lambda _b: types.SimpleNamespace(data_dir=dd))
    monkeypatch.setattr(sys, "argv", ["village", "afslank_wezen"])
    cli.main()
    uit = capsys.readouterr().out
    assert "DRY-RUN" in uit and "slaper" in uit
