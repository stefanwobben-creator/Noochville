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


def test_een_slapende_rol_kan_niets_hoeveel_code_er_ook_is(tmp_path):
    """GEVONDEN DOOR DE DROGE RUN OP PROD, niet door een test. De sweep meldde "geen wezen" terwijl
    er vijf lagen: `noochie` en `facilitator` staan allebei in CLASS_MAP, dus "kan uitvoeren" zei ja
    — terwijl ze slapen en er geen thread draait.

    KUNNEN IS NIET DRAAIEN. Zelfde onderscheid als bij de dagbel: de code stond er, er tikte alleen
    niets meer. En het raakt méér dan de opruiming: zonder deze regel krijgt een slapende AI-rol nog
    steeds projecten toegewezen, op een bord waar niemand kijkt."""
    dd, st = _st(tmp_path)
    rol = next(r.id for r in st.records.all() if getattr(r, "definition", None))
    st.assign.assign(rol, "persona", "een-ai")               # een AI-vervuller: kan uitvoeren
    rec = st.records.get(rol)
    assert cockpit2._kan_uitvoeren(st, rol) is True          # wakker: doet mee
    rec.slaapt = True
    st.records.put(rec)
    st2 = cockpit2._Stores(dd)
    assert cockpit2._kan_uitvoeren(st2, rol) is False, "een slapende rol telt nog als uitvoerder"


def test_werk_voor_een_slapende_rol_gaat_niet_naar_zijn_bord(tmp_path, monkeypatch):
    """Het gevolg van hierboven, in de router: geen nieuw project op een slapend bord."""
    dd, st = _st(tmp_path)
    rol = next(r.id for r in st.records.all() if getattr(r, "definition", None))
    st.assign.assign(rol, "persona", "een-ai")
    rec = st.records.get(rol)
    rec.slaapt = True
    st.records.put(rec)
    st2 = cockpit2._Stores(dd)
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_circle_lead_van", lambda _s, r: "een_lead")
    _soort, ref = cockpit2.route_werk(st2, tekst="iets", rol=rol)
    assert "heeft geen vervuller" in ref


def test_de_levencheck_leest_geen_bestand(tmp_path):
    """DE OMGEKEERDE VAL. Mijn eerste versie las `role_status.json` — een bestand dat de DAEMON
    schrijft. Ontbreekt het (test, verse installatie, webserver vóór de eerste dorpsstart), dan werd
    "leeg" gelezen als "niemand leeft", en dan gaat ál het AI-werk naar de Circle Lead.

    Onbekend leven is geen dood, net zoals `no_data` geen nul is. De check grondt op de records zelf
    en berekent live; deze test bevriest dat hij geen cache aanraakt."""
    import inspect
    bron = inspect.getsource(cockpit2._kan_uitvoeren)
    kaal = "\n".join(r for r in bron.splitlines() if not r.strip().startswith("#"))
    assert "role_status" not in kaal, "de levencheck leest weer een bestand"
    assert "read_json" not in kaal and "open(" not in kaal


def test_de_droge_run_noemt_de_bestemming(tmp_path, monkeypatch):
    """"(dry-run)" als bestemming is geen droge run maar een lege belofte: je ziet dát er iets
    gebeurt, niet wát — en dan is aftekenen een handtekening zonder inhoud."""
    dd, st = _st(tmp_path)
    st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    res = aw.herrouteer(st, apply=False)
    naar = res["items"][0]["naar"]
    assert "(dry-run)" not in naar and naar.strip(), naar


def test_voorspellen_en_uitvoeren_zijn_dezelfde_regel():
    """Twee keer dezelfde beslissing uitschrijven loopt na één wijziging uit de pas, en dan belooft
    het scherm iets anders dan er gebeurt. `route_werk` neemt zijn besluit UIT `bestemming`."""
    import inspect
    bron = inspect.getsource(cockpit2.route_werk)
    assert "best = bestemming(" in bron
    assert "mens_vervullers(" not in bron, "route_werk beslist weer zelf"
    assert "_circle_lead_van(" not in bron


def test_herrouteren_is_een_verhuizing_geen_kopie(tmp_path, monkeypatch):
    """GEVONDEN VÓÓR --APPLY, en het had de sweep erger gemaakt dan de kwaal. Zonder het origineel
    te sluiten blijft het wees-project staan én verschijnt er een nieuw item: twee plekken voor één
    stuk werk. En bij de volgende run opnieuw — een opruiming die niet idempotent is maakt bij elke
    beurt meer rommel dan hij weghaalt."""
    dd, st = _st(tmp_path)
    pid = st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    monkeypatch.setattr(cockpit2, "route_werk", lambda *a, **k: ("inbox", "bij de Circle Lead"))
    aw.herrouteer(st, apply=True)
    p = st.projects.get(pid)
    assert p.get("archived") is True, "het origineel bleef op het dode bord staan"
    spoor = " ".join(str(e.get("text") or "") for e in (p.get("log") or []))
    assert "verhuisd" in spoor and "Circle Lead" in spoor, "het spoor terug ontbreekt"


def test_twee_keer_sweepen_levert_niet_twee_kopieen(tmp_path, monkeypatch):
    """Idempotent: de tweede run vindt niets meer, want de eerste sloot het origineel."""
    dd, st = _st(tmp_path)
    st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    monkeypatch.setattr(cockpit2, "route_werk", lambda *a, **k: ("inbox", "bij de Circle Lead"))
    assert aw.herrouteer(st, apply=True)["gevonden"] == 1
    assert aw.herrouteer(st, apply=True)["gevonden"] == 0


def test_de_droge_run_toont_ook_wat_er_met_het_origineel_gebeurt(tmp_path, monkeypatch):
    """BEIDE KANTEN VAN DE VERHUIZING. Alleen de bestemming tonen laat precies de helft weg die het
    verschil maakt tussen verplaatsen en kopiëren — en juist dáár ging het bijna mis. "Zeg wát er
    gebeurt, niet dát er iets gebeurt" geldt ook voor wat er ACHTERBLIJFT."""
    dd, st = _st(tmp_path)
    st.projects.create("slaper", "Iets dat bleef liggen", "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    item = aw.herrouteer(st, apply=False)["items"][0]
    assert "archiveren" in item["origineel"], item
    assert item["naar"] in item["origineel"], "het spoor noemt de bestemming niet"


def test_de_sweep_kapt_de_titel_niet_af(tmp_path, monkeypatch):
    """MIJN EIGEN CAP VAN GISTEREN, gevonden op een echt geveegd item. Hier stond `[:80]`, en die
    afkapping ging als TEKST de nieuwe inbox-melding in — "…compleet overzicht beschikbaa". Geen
    enkele weergave-fix kan dat nog repareren: het verlies zat al in de data.

    Zelfde les als de 160-cap: een veld dat 'titel' heet maar de enige kopie is, is geen titel maar
    een amputatie."""
    dd, st = _st(tmp_path)
    lang = ("De Village Update is klaar wanneer er een actueel, compleet overzicht beschikbaar is "
            "van alle lopende initiatieven, acties en besluiten binnen de Village")
    st.projects.create("slaper", lang, "human")
    monkeypatch.setattr(cockpit2, "mens_vervullers", lambda _s, r: [])
    monkeypatch.setattr(cockpit2, "_kan_uitvoeren", lambda _s, r: False)
    titel = aw.wezen(st)[0]["titel"]
    assert titel == lang[:200], "de titel is onderweg afgekapt"
    assert "beschikbaar" in titel
