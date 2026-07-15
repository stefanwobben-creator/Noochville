"""Metrics: store (link/kpi/samples/venster/pins) + tab/dispatch (rol-KPI's, cirkeldashboard, bron)."""
from __future__ import annotations
import json
import time

from nooch_village import cockpit2
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.views.metrics import _metrics_tab_html

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"
MKT = "mother_earth__nooch__marketing_lead"


def _mtab(dd, node):
    # Het beheer-blok (eigen KPI's, systeem-KPI's, links) leeft sinds de nieuwe metrics-tab in het
    # oude _metrics_tab_html (niet meer op de node-tab getoond). Deze helper test dat blok direct.
    st = cockpit2._Stores(dd)
    return _metrics_tab_html(st, st.records.get(node), "t")


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_store_link_kpi_sample(tmp_path):
    m = MetricStore(str(tmp_path / "m.json"))
    assert m.add_link(C, "Boekhouding", "https://x/y")
    assert m.add_link(C, "", "") is None
    k = m.add_kpi(RID, "Conversie", "%")
    assert m.add_sample(k["id"], "3.5") and m.add_sample(k["id"], "ab") is False
    assert m.get(k["id"])["samples"][0]["value"] == 3.5


def test_venster_filtert_samples():
    now = time.time()
    samples = [{"at": now - 100 * 86400, "value": 1}, {"at": now - 2 * 86400, "value": 2},
               {"at": now, "value": 3}]
    assert [p[1] for p in filter_samples(samples, window_cutoff("7d", now))] == [2, 3]
    assert [p[1] for p in filter_samples(samples, window_cutoff("alles", now))] == [1, 2, 3]


def test_bron_kpi_pulse_visitors(tmp_path):
    dd = _dd(tmp_path)
    # bron-KPI uit data toevoegen (pulse_visitors), bestaande data van het dorp
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [MKT], "pick": ["source:pulse_visitors"], "next": ["/"]}, username="guest")
    it = [i for i in cockpit2._Stores(dd).metrics.for_node(MKT) if i["kind"] == "kpi"][0]
    assert it["source"] == "pulse_visitors" and it["unit"] == "bezoekers"
    # bron-KPI's accepteren geen handmatige meting
    assert cockpit2._Stores(dd).metrics.add_sample(it["id"], 5) is False


def test_rol_tab_eigen_kpi_en_meting(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Conversie"],
                                        "unit": ["%"], "next": ["/"]}, username="guest")
    mid = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]["id"]
    cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["4.2"], "next": ["/"]}, username="guest")
    page = _mtab(dd, RID)
    # mini-Looker: focus-flow CTA + eigen KPI's + periode
    assert "Conversie" in page and "+ KPI maken" in page and "Periode:" in page
    assert "Eigen KPI's" in page and "+ Link" in page


def test_kpi_composer_combos(tmp_path):
    dd = _dd(tmp_path)
    rec = cockpit2._Stores(dd).records.get(C)
    page = cockpit2.render_kpi_composer(cockpit2._Stores(dd), C, csrf_token="t")
    # deelopdracht 3: één regel per metric (def-namen), geen dim-combos
    assert "Paren verkocht (Shopify)" in page and "Bezoekers (Plausible)" in page
    assert "· per land" not in page and "(per dag) · over tijd" not in page
    assert "tile_add" in page and "Referentie" in page and "benchmark" in page and "doel" in page


def test_kpi_referentie_op_tegel(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # benchmark-referentie: vergelijkwaarde in target, geen project
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["shopify|pairs_sold|none"],
                                       "form": ["doelmeter"], "ref_kind": ["benchmark"],
                                       "target": ["13.6"], "goal_pid": ["irrelevant"], "next": ["/"]}, username="guest")
    t = cockpit2._Stores(dd).metrics.tiles_of(C)[0]
    assert t["ref_kind"] == "benchmark" and t["target"] == 13.6 and t["goal_pid"] == ""
    # doel-referentie: project gekoppeld
    pid = st.projects.create(C, "1000 paar", "human")
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["shopify|pairs_sold|none"],
                                       "form": ["burnup"], "ref_kind": ["doel"],
                                       "goal_pid": [pid], "target": ["1000"], "next": ["/"]}, username="guest")
    t2 = cockpit2._Stores(dd).metrics.tiles_of(C)[1]
    assert t2["ref_kind"] == "doel" and t2["goal_pid"] == pid and t2["target"] == 1000.0


def test_tile_toevoegen_en_vormen(tmp_path):
    dd = _dd(tmp_path)
    # Zaai een shopify-snapshot in de eigen tmp-map: de doelmeter rendert alleen als bullet
    # wanneer er een waarde is. Zonder dit leunt _shopify_window op het gitignored
    # repo-bestand data/shopify_metrics.json — lokaal aanwezig, in CI niet → test-isolatielek.
    (tmp_path / "poc" / "shopify_metrics.json").write_text(
        json.dumps({"windows": {"0": {"pairs_sold": 250}}}))
    # tegel: verkoop per land als verdeling (staaf)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["shopify|orders|country"],
                                       "form": ["verdeling"], "target": [""], "next": ["/"]}, username="guest")
    t = cockpit2._Stores(dd).metrics.tiles_of(C)[0]
    assert t["source"] == "shopify" and t["dim"] == "country" and t["form"] == "verdeling"
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "tile" in page and ("bars" in page or "geen uitsplitsing" in page)
    # doelmeter met target
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["shopify|pairs_sold|none"],
                                       "form": ["doelmeter"], "target": ["1000"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).metrics.tiles_of(C)[1]["target"] == 1000.0
    dash = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "class='bullet'" in dash and "doel 1000" in dash   # doelmeter rendert als bullet
    # verwijderen
    tid = cockpit2._Stores(dd).metrics.tiles_of(C)[0]["id"]
    cockpit2.dispatch(dd, "tile_remove", {"node": [C], "tid": [tid], "next": ["/"]}, username="guest")
    assert len(cockpit2._Stores(dd).metrics.tiles_of(C)) == 1


def test_grondslag_en_doelkoppeling(tmp_path):
    dd = _dd(tmp_path)
    # handmatige KPI met grondslag (definitie/richting/drempel)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Conversie"],
                                        "unit": ["%"], "definition": ["betaalde orders / bezoekers"],
                                        "direction": ["up"], "threshold": ["2"], "next": ["/"]}, username="guest")
    it = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]
    assert it["definition"] == "betaalde orders / bezoekers" and it["direction"] == "up" and it["threshold"] == 2.0
    g = cockpit2._grondslag(cockpit2._Stores(dd), f"kpi:{it['id']}", "value")
    assert g["definitie"] and g["richting"] == "up"
    # tegel met doel-koppeling aan een project
    st = cockpit2._Stores(dd)
    pid = st.projects.create(RID, "1000 paar in Q4", "human")
    cockpit2.dispatch(dd, "tile_add", {"node": [RID], "combo": ["shopify|pairs_sold|none"],
                                       "form": ["doelmeter"], "target": ["1000"], "goal_pid": [pid], "next": ["/"]}, username="guest")
    t = cockpit2._Stores(dd).metrics.tiles_of(RID)[0]
    assert t["goal_pid"] == pid and t["target"] == 1000.0
    page = cockpit2.render_node(cockpit2._Stores(dd), RID, "metrics", csrf_token="t")
    assert "js-flip" in page and "naar doel:" in page and "1000 paar in Q4" in page   # grondslag (kaart-omdraaien) + doel zichtbaar


def test_built_in_grondslag(tmp_path):
    dd = _dd(tmp_path)
    g = cockpit2._grondslag(cockpit2._Stores(dd), "shopify", "pairs_sold")
    assert "paren" in g["eenheid"] and g["bron"] == "Shopify" and g["richting"] == "up"


def test_handmatige_kpi_wordt_bron_in_wizard(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [MKT], "pick": ["manual"], "name": ["NPS"],
                                        "unit": ["score"], "next": ["/"]}, username="guest")
    # op de cirkel verschijnt de handmatige KPI als indicator (categorie 'Eigen KPI's'), één regel
    page = cockpit2.render_kpi_composer(cockpit2._Stores(dd), C, csrf_token="t")
    assert "NPS" in page and "Eigen KPI" in page


def test_meetmoment_schema_normalisatie(tmp_path):
    # Pydantic-schema valideert/normaliseert: meetmoment (cadans + meettype) + onzin valt terug
    m = MetricStore(str(tmp_path / "m.json"))
    k = m.add_kpi(RID, "Bezoekers", "n", cadence="week", meettype="venster", window="7d")
    assert k["cadence"] == "week" and k["meettype"] == "venster" and k["window"] == "7d"
    k2 = m.add_kpi(RID, "X", cadence="onzin", meettype="zwabber", direction="zijwaarts", threshold="nan")
    assert k2["cadence"] == "ad-hoc" and k2["meettype"] == "snapshot"
    assert k2["direction"] == "" and k2["threshold"] is None
    # lege naam => geen KPI
    assert m.add_kpi(RID, "   ") is None


def test_meetmoment_in_form_en_popover(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Voorraad"],
                                        "unit": ["paar"], "cadence": ["dag"], "meettype": ["snapshot"],
                                        "next": ["/"]}, username="guest")
    it = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]
    assert it["cadence"] == "dag"
    # meetmoment-velden leven in de catalogus (add/edit), niet meer op de metrics-tab
    cat = cockpit2.render_catalog(cockpit2._Stores(dd), csrf_token="t")
    assert "name='cadence'" in cat and "name='meettype'" in cat
    # de popover op de KPI-rij toont het meetmoment (grondslag)
    g = cockpit2._grondslag(cockpit2._Stores(dd), f"kpi:{it['id']}", "value")
    assert g["cadans"] == "dag"


def test_kpi_export_csv(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Conversie"],
                                        "unit": ["%"], "next": ["/"]}, username="guest")
    mid = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]["id"]
    cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["4.2"], "next": ["/"]}, username="guest")
    res = cockpit2._metric_csv(cockpit2._Stores(dd), mid)
    assert res is not None
    fname, body = res
    assert fname == "Conversie.csv" and "datum,waarde,eenheid" in body and "4.2" in body
    # volledig indicator-schema in de export, ook lege velden (definition, cadence, meettype...)
    assert "indicator-schema" in body
    for f in ("name", "definition", "direction", "cadence", "meettype", "window"):
        assert f in body
    assert cockpit2._metric_csv(cockpit2._Stores(dd), "bestaatniet") is None


def test_verwijderen_vraagt_bevestiging(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["NPS"], "next": ["/"]}, username="guest")
    page = _mtab(dd, RID)
    # delete heeft data-confirm + er is een exportlink
    assert "data-confirm=" in page and "verwijderen?" in page and "/metric_export?mid=" in page


def test_bullet_vervangt_doelmeter(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # handmatige KPI met waarde + benchmark, richting hoger=beter
    k = st.metrics.add_kpi(C, "Conversie", "%", direction="up", benchmark="goed 2-3%")
    # gisteren gemeten: een complete-dagen-venster (7d) sluit vandaag uit, dus dateer op een volle dag
    st.metrics.add_sample(k["id"], 1.5, at=time.time() - 86400)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["doelmeter"], "target": ["3"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    # Few-bullet: balk + doel-tick + benchmark-label, geen vlakke 'goal'-meter
    assert "class='bullet'" in page and "doel 3" in page and "benchmark: goed 2-3%" in page
    # 1,5 < doel 3 bij hoger=beter → coral-balk
    assert "var(--coral)" in page


def test_bullet_richtingbewust_lager_is_beter(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # CO2-achtig: lager = beter, waarde onder het doel → groene balk
    k = st.metrics.add_kpi(C, "CO2 per paar", "kg", direction="down")
    st.metrics.add_sample(k["id"], 4.75, at=time.time() - 86400)   # gisteren (complete dag, valt in 7d)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["doelmeter"], "target": ["6"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "class='bullet'" in page and "var(--green)" in page   # 4,75 <= doel 6 → goed


def test_tufte_datatabel_en_delta_bij_grafiek(tmp_path):
    import time
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Trendje", "n")
    now = time.time()
    st.metrics.add_sample(k["id"], 10, at=now - 3 * 86400)
    st.metrics.add_sample(k["id"], 14, at=now - 1 * 86400)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["trend"], "target": [""], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    # Tufte: inklapbare datatabel onder de grafiek. De dag-op-dag-delta is verwijderd: een delta
    # verschijnt alleen nog bij 'Vergelijk met vorige periode' (zie test_delta_alleen_bij_compare).
    assert "<details class='tile-data'>" in page and "datum" in page and "waarde" in page
    assert "▲" not in page and "▼" not in page


def test_getal_geen_datatabel(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Losse waarde", "n")
    st.metrics.add_sample(k["id"], 7)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["getal"], "target": [""], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "<details class='tile-data'>" not in page   # bij een enkel getal geen tabel forceren


def test_burnup_doeltempo(tmp_path):
    import time
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # handmatige cumulatieve KPI (paren) met metingen over de tijd
    k = st.metrics.add_kpi(C, "Paren cumulatief", "paar", cadence="dag", meettype="cumulatief")
    now = time.time()
    st.metrics.add_sample(k["id"], 100, at=now - 20 * 86400)
    st.metrics.add_sample(k["id"], 300, at=now - 5 * 86400)
    # doel-project met deadline in de toekomst
    pid = st.projects.create(C, "1000 paar", "human")
    p = st.projects.get(pid)
    import datetime
    p["due"] = (datetime.date.today() + datetime.timedelta(days=40)).isoformat()
    p["created_at"] = now - 25 * 86400
    st.projects._save()
    # burn-up tegel die de KPI als bron neemt, gekoppeld aan het doel
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["burnup"], "target": ["1000"], "goal_pid": [pid], "next": ["/"]}, username="guest")
    t = cockpit2._Stores(dd).metrics.tiles_of(C)[0]
    assert t["form"] == "burnup" and t["goal_pid"] == pid
    # render met een periode die de 20-dagen-oude metingen omvat (default is nu 7 dagen, scope 6)
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t", mw="kwartaal")
    assert "burnup" in page and "/dag" in page and "benodigd" in page and "prognose" in page


def test_burnup_zonder_doel_vraagt_koppeling(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    k = st.metrics.add_kpi(C, "Paren cum", "paar", meettype="cumulatief")
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": [f"kpi:{k['id']}|value|none"],
                                       "form": ["burnup"], "target": [""], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "Koppel een doel" in page


def test_link_metric(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_link", {"node": [C], "name": ["Jaarcijfers"],
                                         "url": ["https://docs.example/x"], "next": ["/"]}, username="guest")
    page = _mtab(dd, C)
    assert "Jaarcijfers" in page and "kpi-link" in page


def test_werk_fetch_afgeleide_afwezigheid_en_reguliere_count(tmp_path):
    # Werkoverleg-log → dashboard-measures: afgeleide afwezigheid (lijst → aantal) +
    # nieuwe reguliere count (roloverleg), plus een bestaande count als controle.
    from nooch_village.views.metrics import _werk_fetch
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    w = st.werk

    # overleg 1: 2 afwezig, 1 spanning naar roloverleg
    w.open(C)
    w.set_presence(C, "a", True); w.set_presence(C, "b", False); w.set_presence(C, "c", False)
    it = w.agenda_add(C, "spanning 1"); w.agenda_resolve(C, it["id"], "roloverleg")
    w.close(C)

    # overleg 2: 1 afwezig, 1 spanning naar roloverleg
    w.open(C)
    w.set_presence(C, "a", False)
    it = w.agenda_add(C, "spanning 2"); w.agenda_resolve(C, it["id"], "roloverleg")
    w.close(C)

    # afgeleide: afwezig-lijst → aantal, som over de twee overleggen = 2 + 1
    assert _werk_fetch(st, C, "afwezigheid", "totaal", 0)["value"] == 3
    # nieuwe reguliere count: roloverleg-uitkomsten = 1 + 1
    assert _werk_fetch(st, C, "roloverleg", "totaal", 0)["value"] == 2
    # bestaande count blijft werken: behandelde spanningen = 1 + 1
    assert _werk_fetch(st, C, "spanningen", "totaal", 0)["value"] == 2


def test_werk_aggregaat_respecteert_periodefilter(tmp_path):
    """Regressie: gemiddeld/totaal aggregeren over de werkoverleg-records BINNEN het venster
    (cutoff), net als de reeks-tegel — niet all-time (de gedriftte periodefilter is dicht)."""
    from nooch_village.views.metrics import _werk_fetch
    st = cockpit2._Stores(_dd(tmp_path))
    now, day = time.time(), 86400
    st.werk._m.setdefault(C, {})["log"] = [
        {"at": now - 60 * day, "tevredenheid": 4.0, "duur_min": 100},   # oud, buiten "maand"
        {"at": now - 1 * day, "tevredenheid": 8.0, "duur_min": 10},     # recent, binnen "maand"
    ]
    st.werk._save()
    cutoff = window_cutoff("maand", now)                     # alleen het recente record telt mee
    assert _werk_fetch(st, C, "tevredenheid", "gemiddeld", cutoff)["value"] == 8.0   # niet 6.0
    assert _werk_fetch(st, C, "duur", "totaal", cutoff)["value"] == 10               # niet 110
    # zonder filter (None) → all-time gemiddelde/som over beide records
    assert _werk_fetch(st, C, "tevredenheid", "gemiddeld", None)["value"] == 6.0
    assert _werk_fetch(st, C, "duur", "totaal", None)["value"] == 110


# ── bezoekers 'over tijd': echt lijn-diagram uit de dagreeks (observations) ───
def test_bezoekers_lijndiagram_toont_meerdere_punten(tmp_path):
    """Zodra er meerdere dagwaarden (bron=plausible) in de observatie-store staan, toont de
    bezoekers-'over tijd'-tegel een echt lijn-diagram met meerdere punten (geen micro-sparkline)."""
    import datetime as dt
    from nooch_village.views.metrics import _fetch, _line_chart_svg, _render_form
    st = cockpit2._Stores(_dd(tmp_path))
    base = dt.datetime(2026, 7, 1, 12, 0, tzinfo=dt.timezone.utc)
    for i, v in enumerate([40, 55, 48]):
        ts = (base + dt.timedelta(days=i)).timestamp()
        st.observations.record_daily("website_watcher", "plausible_visitors_day", v,
                                     bron="plausible", datum=f"2026-07-0{i+1}", ts=ts)
    res = _fetch(st, "pulse_visitors", "visitors", "time", None)
    assert res["chart"] == "line" and [p[1] for p in res["points"]] == [40, 55, 48]
    svg = _line_chart_svg(res["points"], "bezoekers")
    assert svg.count("<circle") == 3          # drie echte dagpunten als stippen
    assert "<polyline" in svg                 # verbonden lijn
    assert "01-07" in svg and "03-07" in svg  # leesbare x-as (eerste + laatste datum)
    # de tegel-vorm (verdeling → trend) routeert naar het lijn-diagram, niet de sparkline
    assert "<polyline" in _render_form(res, "verdeling", None)


def test_bezoekers_lijndiagram_geen_data_status(tmp_path):
    from nooch_village.views.metrics import _fetch, _line_chart_svg
    st = cockpit2._Stores(_dd(tmp_path))
    res = _fetch(st, "pulse_visitors", "visitors", "time", None)
    assert res["points"] == []
    assert "geen data" in _line_chart_svg(res["points"], "bezoekers")   # nette status, geen vlakke lijn


def test_bezoekers_lijndiagram_een_punt_geen_lijn(tmp_path):
    from nooch_village.views.metrics import _line_chart_svg
    svg = _line_chart_svg([(1000.0, 42)], "bezoekers")   # één datapunt
    assert "te weinig" in svg and "<polyline" not in svg  # geen lijn, geen interpolatie


def test_source_samples_ontdubbelt_dagreeks_vs_7d(tmp_path):
    """pulse_visitors = de dagreeks (observations); pulse_visitors_7d = de rollende 7d (pulse_history).
    Twee heldere eigen metric_keys — niet langer als hetzelfde ding gelezen."""
    import os, json as _json
    from nooch_village.views.metrics import _source_samples
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    st.observations.record_daily("ww", "plausible_visitors_day", 40, bron="plausible", datum="2026-07-01", ts=1.0)
    st.observations.record_daily("ww", "plausible_visitors_day", 55, bron="plausible", datum="2026-07-02", ts=2.0)
    with open(os.path.join(dd, "pulse_history.jsonl"), "w") as f:
        f.write(_json.dumps({"ts": 10.0, "visitors_7d": 300}) + "\n")
        f.write(_json.dumps({"ts": 20.0, "visitors_7d": 320}) + "\n")
    assert [s["value"] for s in _source_samples(dd, "pulse_visitors")] == [40, 55]        # dagreeks
    assert [s["value"] for s in _source_samples(dd, "pulse_visitors_7d")] == [300, 320]   # rollende 7d


def test_backfill_geval_sorteert_en_labelt_op_datum(tmp_path):
    """Backfill schrijft historische dagen op één dag → gelijke ts, verschillende datums. De tegel-lezing
    moet op MEETDAG (datum) sorteren en labelen, niet op de schrijf-ts. Regressie: vóór de fix stond alles
    onder de backfill-dag (bv. '06-07') en was 'Actueel' de laatste-op-ts i.p.v. de laatste meetdag."""
    import re
    from nooch_village.views.metrics import _fetch, _data_table
    st = cockpit2._Stores(_dd(tmp_path))
    # ZELFDE ts=17.0 (één schrijfmoment), verschillende datums, in willekeurige schrijf-volgorde
    for datum, val in [("2026-06-05", 21), ("2026-05-26", 151), ("2026-07-05", 15), ("2026-06-02", 246)]:
        st.observations.record_daily("plausible", "plausible_visitors_day", val,
                                     bron="plausible", datum=datum, ts=17.0)
    res = _fetch(st, "pulse_visitors", "visitors", "time", None)
    # (1) chronologisch OP MEETDAG, niet op (gelijke) ts
    assert [p[2] for p in res["points"]] == ["2026-05-26", "2026-06-02", "2026-06-05", "2026-07-05"]
    assert [p[1] for p in res["points"]] == [151, 246, 21, 15]
    # (2) ruwe-data-tabel labelt per MEETDAG (vier verschillende datums, niet 4× de ts-datum)
    tab = _data_table(res, bron="plausible")
    assert re.findall(r"<td>(\d\d-\d\d-\d\d)</td>", tab) == ["26-05-26", "02-06-26", "05-06-26", "05-07-26"]
    # (3) 'Actueel' = laatste MEETDAG (2026-07-05 → 15), niet de laatste-op-ts (2026-06-05 → 21)
    last = st.observations.daily_series("plausible_visitors_day", bron="plausible")[-1]
    assert last["datum"] == "2026-07-05" and last["value"] == 15
