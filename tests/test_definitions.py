"""Librarian metrics-database: gedeelde indicator-definities + versionering (clarify/backcast/break)."""
from __future__ import annotations

from nooch_village.definitions import DefinitionStore, MIGRATIONS


def test_add_en_current(tmp_path):
    s = DefinitionStore(str(tmp_path / "d.json"))
    d = s.add("Conversie", owner="lib", unit="%", definition="orders / bezoekers",
              direction="up", cadence="week", meettype="venster", window="7d")
    assert d is not None and d["current"] == 1 and d["owner"] == "lib"
    cur = s.current(d["id"])
    assert cur["version"] == 1 and cur["definition"] == "orders / bezoekers"
    assert cur["cadence"] == "week" and cur["meettype"] == "venster" and cur["migration"] == ""
    # lege naam => geen definitie
    assert s.add("   ") is None


def test_amend_maakt_nieuwe_versie(tmp_path):
    s = DefinitionStore(str(tmp_path / "d.json"))
    d = s.add("Bezoekers", unit="n", definition="alle sessies")
    did = d["id"]
    # 'clarify': alleen tekst, reeks blijft heel
    v2 = s.amend(did, "clarify", definition="alle sessies (excl. bots)")
    assert v2["version"] == 2 and v2["migration"] == "clarify"
    assert s.current_version_no(did) == 2
    # niet meegegeven velden erven van de vorige versie
    assert v2["unit"] == "n"
    # oude versie blijft bewaard (nooit in-place)
    assert s.version(did, 1)["definition"] == "alle sessies"
    # 'break': substantiële wijziging
    v3 = s.amend(did, "break", definition="unieke bezoekers", unit="uniek")
    assert v3["version"] == 3 and v3["migration"] == "break" and v3["unit"] == "uniek"
    assert len(s.get(did)["versions"]) == 3


def test_amend_validatie(tmp_path):
    s = DefinitionStore(str(tmp_path / "d.json"))
    d = s.add("X")
    assert s.amend(d["id"], "onzin") is None         # onbekende migratie
    assert s.amend("bestaatniet", "clarify") is None  # onbekende definitie
    assert set(MIGRATIONS) == {"clarify", "backcast", "break"}


def test_zaad_catalogus_valideert_tegen_schema(tmp_path):
    # de toets: elke zaad-definitie (afgeleid uit de databron-skills) MOET door het
    # Pydantic indicator-schema komen, met behoud van zijn meetmoment-velden.
    from nooch_village.definitions import _DEFINITION_SEED
    from nooch_village.metric_schema import normalize, CADANS, MEETTYPE
    assert len(_DEFINITION_SEED) >= 20
    seen = set()
    for e in _DEFINITION_SEED:
        spec = normalize(name=e["name"], unit=e.get("unit", ""), source=e.get("source", ""),
                         definition=e.get("definition", ""), direction=e.get("direction", ""),
                         cadence=e.get("cadence", "ad-hoc"), meettype=e.get("meettype", "snapshot"),
                         window=e.get("window", ""))
        assert spec is not None, f"zaad-definitie valideert niet: {e['name']}"
        # geen stille terugval: de opgegeven cadans/meettype moeten bewaard blijven
        assert spec["cadence"] == e.get("cadence", "ad-hoc"), f"cadans gevallen bij {e['name']}"
        assert spec["meettype"] == e.get("meettype", "snapshot"), f"meettype gevallen bij {e['name']}"
        assert spec["cadence"] in CADANS and spec["meettype"] in MEETTYPE
        key = (e["name"], e.get("source", ""))
        assert key not in seen, f"dubbele zaad-definitie: {key}"
        seen.add(key)


def test_seed_catalog_idempotent(tmp_path):
    from nooch_village.definitions import seed_catalog, _DEFINITION_SEED
    s = DefinitionStore(str(tmp_path / "d.json"))
    n1 = seed_catalog(s)
    assert n1 == len(_DEFINITION_SEED) and len(s.all()) == n1
    assert seed_catalog(s) == 0 and len(s.all()) == n1   # tweede keer voegt niets toe
    # nieuwe cadans-waarden uit de inventaris zijn nu geldig
    assert any(s.current(d["id"])["cadence"] == "jaar" for d in s.all())
    assert any(s.current(d["id"])["cadence"] == "uur" for d in s.all())


def test_kpi_uit_catalogus_en_defv(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__marketing_lead"
    # pak een bestaande catalogus-definitie (Bezoekers Plausible)
    d = st.defs.by_name("Bezoekers (Plausible)")
    assert d is not None
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_id": [d["id"]], "next": ["/"]})
    st = cockpit2._Stores(dd)
    it = [i for i in st.metrics.for_node(rid) if i.get("kind") == "kpi"][0]
    assert it["def_id"] == d["id"] and it["def_version"] == 1
    assert it["origin"] == "plausible" and it["auto"] is True   # systeem-bron: geen handmatige invoer
    assert it["cadence"] == "dag" and it["unit"] == "bezoekers"
    assert st.metrics.add_sample(it["id"], 120) is False        # systeem-KPI weigert handmatige meting


def test_zoek_op_naam_en_losse_kpi_met_delen(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    rid = "mother_earth__nooch__marketing_lead"
    # knows-exactly: zoeken op naam koppelt aan de catalogus
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_name": ["Omzet (Shopify)"], "next": ["/"]})
    st = cockpit2._Stores(dd)
    it = [i for i in st.metrics.for_node(rid) if i.get("kind") == "kpi"][0]
    assert it["def_id"] and it["origin"] == "shopify"
    # losse KPI met 'deel in catalogus' maakt een nieuwe gedeelde definitie
    n0 = len(st.defs.all())
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [rid], "pick": ["manual"], "name": ["Retour winkel proef"],
                                        "unit": ["%"], "direction": ["down"], "share": ["1"], "next": ["/"]})
    st = cockpit2._Stores(dd)
    assert len(st.defs.all()) == n0 + 1
    nk = [i for i in st.metrics.for_node(rid) if i.get("name") == "Retour winkel proef"][0]
    assert nk["def_id"] and nk["def_version"] == 1 and nk["auto"] is False
    # handmatige (gedeelde) KPI: meting krijgt het versiestempel defv = 1
    cockpit2.dispatch(dd, "m_sample", {"mid": [nk["id"]], "value": ["4.5"], "next": ["/"]})
    s = cockpit2._Stores(dd).metrics.get(nk["id"])["samples"][0]
    assert s["value"] == 4.5 and s["defv"] == 1


def test_systeem_kpi_blokkeert_handmatige_invoer(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__facilitator"
    if st.records.get(rid) is None:
        rid = "mother_earth__nooch"
    d = st.defs.by_name("Tevredenheid werkoverleg")
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_id": [d["id"]], "next": ["/"]})
    st = cockpit2._Stores(dd)
    it = [i for i in st.metrics.for_node(rid) if i.get("def_id") == d["id"]][0]
    assert it["auto"] is True and it["origin"] == "werkoverleg"
    # store weigert handmatige meting voor een systeem-KPI
    assert st.metrics.add_sample(it["id"], 8) is False
    # UI toont geen invoerveld maar wel het 'systeem'-label
    page = cockpit2.render_node(cockpit2._Stores(dd), rid, "metrics", csrf_token="t")
    assert "systeem" in page
    # een losse handmatige KPI mag wél
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [rid], "pick": ["manual"], "name": ["Eigen telling"], "next": ["/"]})
    st = cockpit2._Stores(dd)
    mk = [i for i in st.metrics.for_node(rid) if i.get("name") == "Eigen telling"][0]
    assert mk.get("auto") is False and st.metrics.add_sample(mk["id"], 3) is True


def test_rol_aanbevelingen_in_picker(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__marketing_lead"
    rec = st.records.get(rid)
    page = cockpit2.render_node(st, rid, "metrics", csrf_token="t")
    assert "+ KPI toevoegen" in page and "Voor jouw rol" in page and "id='cat-defs'" in page
    # relevantie: voor een marketing-rol komen marketing/SEO-bronnen bovendrijven
    recs = [c["name"] for _did, c in cockpit2._role_relevant_defs(st, rec, 8)]
    assert recs, "verwacht aanbevelingen voor de marketing-rol"


def test_suggest_migration_heuristiek():
    from nooch_village.definitions import suggest_migration
    old = {"definition": "orders / bezoekers", "unit": "%", "meettype": "venster"}
    # alleen tekst → clarify
    m, _ = suggest_migration(old, {"definition": "orders / unieke bezoekers"})
    assert m == "clarify"
    # meetbaar veld (eenheid) → break
    m, _ = suggest_migration(old, {"unit": "ratio"})
    assert m == "break"
    # niets gewijzigd → clarify
    assert suggest_migration(old, {})[0] == "clarify"


def _manual_def_kpi(dd, rid="mother_earth__nooch__marketing_lead"):
    from nooch_village import cockpit2
    # losse KPI gedeeld → een handmatige catalogus-definitie + een KPI die ernaar verwijst
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [rid], "pick": ["manual"], "name": ["Teamscore proef"],
                                        "unit": ["score"], "definition": ["promoters - detractors"],
                                        "share": ["1"], "next": ["/"]})
    st = cockpit2._Stores(dd)
    kpi = [i for i in st.metrics.for_node(rid) if i.get("name") == "Teamscore proef"][0]
    for v in (10, 20, 30):
        cockpit2.dispatch(dd, "m_sample", {"mid": [kpi["id"]], "value": [str(v)], "next": ["/"]})
    return kpi["def_id"], kpi["id"]


def test_amend_clarify_houdt_reeks_heel(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    did, mid = _manual_def_kpi(dd)
    cockpit2.dispatch(dd, "def_amend", {"def_id": [did], "definition": ["promoters minus detractors"],
                                        "migration": ["auto"], "next": ["/"]})
    st = cockpit2._Stores(dd)
    kpi = st.metrics.get(mid)
    assert kpi["def_version"] == 2 and not kpi.get("breaks")        # geen breuk
    assert kpi["definition"] == "promoters minus detractors"        # grondslag bijgewerkt
    assert all("defv" in s for s in kpi["samples"])                 # samples behouden


def test_amend_break_zet_breukpunt(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    did, mid = _manual_def_kpi(dd)
    # eenheid wijzigt → meetbaar → break (geen LLM-key in test → veilige default)
    cockpit2.dispatch(dd, "def_amend", {"def_id": [did], "unit": ["%"], "migration": ["auto"], "next": ["/"]})
    st = cockpit2._Stores(dd)
    kpi = st.metrics.get(mid)
    assert kpi["def_version"] == 2 and kpi["breaks"] == [2]
    # oude samples houden defv=1; een nieuwe meting krijgt defv=2 → breukpunt in de reeks
    assert {s["defv"] for s in kpi["samples"]} == {1}
    cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["40"], "next": ["/"]})
    kpi = cockpit2._Stores(dd).metrics.get(mid)
    assert kpi["samples"][-1]["defv"] == 2
    assert cockpit2._break_indices(kpi["samples"]) == [3]           # breuk na de 3 oude punten


def test_amend_backcast_hertagt_historie(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    did, mid = _manual_def_kpi(dd)
    # expliciete back-cast: mens stelt dat historie vergelijkbaar blijft → herstempelen, één reeks
    cockpit2.dispatch(dd, "def_amend", {"def_id": [did], "unit": ["pt"], "migration": ["backcast"], "next": ["/"]})
    kpi = cockpit2._Stores(dd).metrics.get(mid)
    assert kpi["def_version"] == 2 and not kpi.get("breaks")
    assert {s["defv"] for s in kpi["samples"]} == {2}              # alles op nieuwe versie


def test_catalogus_pagina_rendert(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    page = cockpit2.render_catalog(st, csrf_token="t")
    assert "Metrics-catalogus" in page and "Librarian" in page
    assert "+ Nieuwe definitie" in page
    assert "Bezoekers (Plausible)" in page and "Tevredenheid werkoverleg" in page
    # bron-secties met leesbare labels
    assert "Shopify" in page and "Werkoverleg-archief" in page
    # gebruik + wijzig-actie aanwezig
    assert "in gebruik" in page and "wijzig definitie" in page


def test_def_add_via_dispatch(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    n0 = len(cockpit2._Stores(dd).defs.all())
    cockpit2.dispatch(dd, "def_add", {"name": ["Winkel-NPS regio"], "unit": ["NPS"], "csource": [""],
                                      "definition": ["promoters - detractors in de fysieke winkel"],
                                      "direction": ["up"], "cadence": ["kwartaal"], "next": ["/catalog"]})
    st = cockpit2._Stores(dd)
    assert len(st.defs.all()) == n0 + 1
    d = st.defs.by_name("Winkel-NPS regio")
    cur = st.defs.current(d["id"])
    assert cur["cadence"] == "kwartaal" and cur["direction"] == "up" and cur["source"] == ""


def test_catalogus_usage_telt_gebruik(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__marketing_lead"
    d = st.defs.by_name("Omzet (Shopify)")
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_id": [d["id"]], "next": ["/"]})
    page = cockpit2.render_catalog(cockpit2._Stores(dd), csrf_token="t")
    assert "1× in gebruik" in page


def test_meetwijze_per_bron_en_invoer(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    # systeem-bron (ERP) → meetwijze systeem → KPI blokkeert handmatige invoer
    erp = st.defs.by_name("Voorraadwaarde")
    assert st.defs.current(erp["id"])["meetwijze"] == "systeem"
    # enquête-bron → handmatig invoerbaar
    nps = st.defs.by_name("NPS")
    assert st.defs.current(nps["id"])["meetwijze"] == "enquete"
    rid = "mother_earth__nooch__marketing_lead"
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_id": [erp["id"]], "next": ["/"]})
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_id": [nps["id"]], "next": ["/"]})
    st = cockpit2._Stores(dd)
    kerp = [i for i in st.metrics.for_node(rid) if i.get("def_id") == erp["id"]][0]
    knps = [i for i in st.metrics.for_node(rid) if i.get("def_id") == nps["id"]][0]
    assert kerp["auto"] is True and st.metrics.add_sample(kerp["id"], 5) is False
    assert knps["auto"] is False and st.metrics.add_sample(knps["id"], 42) is True


def test_meetwijze_wijzigen_flipt_invoer(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    # nieuwe handmatige definitie + KPI
    cockpit2.dispatch(dd, "def_add", {"name": ["Eigen meter"], "unit": ["n"], "csource": [""],
                                      "meetwijze": ["handmatig"], "next": ["/catalog"]})
    did = cockpit2._Stores(dd).defs.by_name("Eigen meter")["id"]
    rid = "mother_earth__nooch__marketing_lead"
    cockpit2.dispatch(dd, "m_add_from_def", {"node": [rid], "def_id": [did], "next": ["/"]})
    mid = [i for i in cockpit2._Stores(dd).metrics.for_node(rid) if i.get("def_id") == did][0]["id"]
    assert cockpit2._Stores(dd).metrics.add_sample(mid, 1) is True
    # zet meetwijze op systeem → KPI's flippen naar auto, invoer geblokkeerd
    cockpit2.dispatch(dd, "def_amend", {"def_id": [did], "meetwijze": ["systeem"],
                                        "migration": ["clarify"], "next": ["/catalog"]})
    st = cockpit2._Stores(dd)
    assert st.metrics.get(mid)["auto"] is True and st.metrics.add_sample(mid, 2) is False


def test_catalogus_navigatie(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    page = cockpit2.render_catalog(cockpit2._Stores(dd), csrf_token="t")
    # zoekveld + meetwijze-filters + inklapbare secties + filter-data op de kaarten
    assert "id='cat-q'" in page and "class='cat-f'" in page and "data-val='systeem'" in page
    assert "class='cat-sec'" in page and "data-text=" in page
    assert "meetwijze:" in page


def test_metavelden_grondslag_en_aard(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    # de meeste seed-definities zijn nog ongegrond (de gegronde IT/DORA-set is de uitzondering)
    assert st.defs.current(st.defs.by_name("Bezoekers (Plausible)")["id"])["standaard"] == "interne aanname"
    assert "DORA" in st.defs.current(st.defs.by_name("Deploy-frequentie")["id"])["standaard"]
    # nieuwe gegronde definitie met aard + benchmark
    cockpit2.dispatch(dd, "def_add", {"name": ["Doorvoertijd proef"], "unit": ["uur"], "csource": ["monitoring"],
                                      "tijd": ["lagging"], "bruikbaar": ["actionable"],
                                      "standaard": ["DORA"], "benchmark": ["elite < 1 dag"],
                                      "next": ["/catalog"]})
    d = cockpit2._Stores(dd).defs.by_name("Doorvoertijd proef")
    cur = cockpit2._Stores(dd).defs.current(d["id"])
    assert cur["standaard"] == "DORA" and cur["tijd"] == "lagging" and cur["bruikbaar"] == "actionable"
    assert cur["benchmark"] == "elite < 1 dag"
    # filter-attributen + Lean/grounded-filters op de pagina
    page = cockpit2.render_catalog(cockpit2._Stores(dd), csrf_token="t")
    assert "data-facet='bruikbaar'" in page and "data-val='actionable'" in page
    assert "data-val='0'" in page and "ongegrond" in page
    assert "data-bruikbaar='actionable'" in page and "DORA" in page


def test_it_domein_gegrond_tegen_dora(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for naam in ("Deploy-frequentie", "Lead time for changes", "Wijzigingsfaalpercentage",
                 "Hersteltijd na falen"):
        d = st.defs.by_name(naam)
        assert d is not None, naam
        cur = st.defs.current(d["id"])
        assert "DORA" in cur["standaard"] and cur["benchmark"] and cur["bruikbaar"] == "actionable"
    # IT-incidenten eerlijk gemarkeerd als géén DORA-kern
    inc = st.defs.current(st.defs.by_name("IT-incidenten")["id"])
    assert "geen DORA" in inc["standaard"]


def test_reground_idempotent(tmp_path):
    from nooch_village import definitions as D
    s = D.DefinitionStore(str(tmp_path / "d.json"))
    # bootstrap-achtig: eerst ongegrond zaaien zoals oude data, dan regronden
    D.seed_catalog(s)
    dep = s.by_name("Deploy-frequentie")
    # simuleer 'oude' opslag: zet standaard terug op interne aanname
    s._d[dep["id"]]["versions"][-1]["standaard"] = "interne aanname"
    n1 = D.reground_seed(s)
    assert n1 == 1 and "DORA" in s.current(dep["id"])["standaard"]   # alleen de teruggezette
    assert s.current(dep["id"])["version"] == 2          # nieuwe versie (clarify)
    assert D.reground_seed(s) == 0                        # tweede keer: niets te doen


def test_store_in_cockpit(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    base = len(st.defs.all())                          # bootstrap heeft de catalogus geseed
    assert base >= 20
    assert st.defs.add("Omzet", unit="EUR") is not None
    assert len(cockpit2._Stores(dd).defs.all()) == base + 1   # persistent
