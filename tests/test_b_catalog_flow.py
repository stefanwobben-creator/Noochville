"""B: catalogus-flow-redesign — STATUS (met/zonder data + reden-splitsing) + ACTIVEREN (checkbox →
rol/cirkel-dashboard, open books, gelogd wie/wat/wanneer) + formulier-hulp per bron."""
from __future__ import annotations
import datetime
import json

from nooch_village import cockpit2
from nooch_village.observations import ObservationStore
from nooch_village.views.catalog_koppelen import (_bron_indicators, _status_section, _activate_section,
                                                  _geen_data_reden, _koppel_section)

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _seed_obs(dd, metric, value):
    y = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
    ObservationStore(f"{dd}/observations.jsonl").record_daily("plausible", metric, value, bron="plausible", datum=y)


def test_status_split_met_en_zonder_data(tmp_path):
    dd = _dd(tmp_path)
    _seed_obs(dd, "plausible_visitors_day", 15)               # bezoekers → fresh
    st = cockpit2._Stores(dd)
    inds = _bron_indicators(st)
    bezoekers = next(i for i in inds if i["veld"] == "visitors")
    assert bezoekers["heeft_data"] and bezoekers["fresh"] == "fresh"
    zonder = [i for i in inds if not i["heeft_data"]]
    assert zonder and all(i["reden"][0] in ("veld", "hapert") for i in zonder)   # elke reden geclassificeerd
    html = _status_section(st)
    assert "Status · met data" in html and "Status · zonder data" in html
    assert "Bezoekers (Plausible)" in html and "style=" not in html              # UI-regel: geen inline styles


def test_reden_hapert_vs_bron_levert_niet():
    produces = {"gdelt_tone": {"tone"}, "shopify": set()}
    active = {"gdelt_tone": {"active": True}, "shopify": {"active": False}}
    # actief + levert het veld + geen data → tijdelijke hapering (fail-closed gat)
    assert _geen_data_reden("none", "gdelt_tone", "tone", produces, active)[0] == "hapert"
    # bron levert dit veld niet → configuratie/bug
    assert _geen_data_reden("none", "shopify", "pairs_sold", produces, active)[0] == "veld"
    # ontbrekende creds → altijd 'veld' (config), niet 'hapert'
    assert _geen_data_reden("unconfigured", "plausible", "visitors", produces, active)[0] == "veld"


def test_activeren_maakt_tegel_en_logt_wie_wat_wanneer(tmp_path):
    dd = _dd(tmp_path)
    _seed_obs(dd, "plausible_pageviews_day", 20)
    st = cockpit2._Stores(dd)
    did = next(i["did"] for i in _bron_indicators(st) if i["veld"] == "pageviews")
    n_before = len(st.metrics.tiles_of(C))
    nxt, msg = cockpit2.dispatch(dd, "indicator_activate",
                                 {"did": [did], "node": [C], "next": ["/catalog"]}, username="stefan@x")
    tiles = cockpit2._Stores(dd).metrics.tiles_of(C)
    assert len(tiles) == n_before + 1 and any(t["source"] == f"kpi:{did}" or t["source"].startswith("kpi:") for t in tiles)
    assert "geactiveerd" in msg
    ev = [json.loads(l) for l in open(f"{dd}/system_log.jsonl") if '"indicator_activated"' in l]
    assert ev and ev[-1]["by"] == "stefan@x" and did in ev[-1]["def_ids"] and ev[-1]["node"] == C


def test_activeren_zonder_keuze_geen_tegel(tmp_path):
    dd = _dd(tmp_path)
    nxt, msg = cockpit2.dispatch(dd, "indicator_activate", {"did": [], "node": [C]}, username="x")
    assert "kies" in msg.lower()


def test_activeer_form_toont_alleen_indicatoren_met_data(tmp_path):
    dd = _dd(tmp_path)
    _seed_obs(dd, "plausible_visitors_day", 15)
    html = _activate_section(cockpit2._Stores(dd), "t")
    assert "indicator_activate" in html and "type='checkbox'" in html and "Bezoekers (Plausible)" in html


def test_formulier_hulp_per_bron(tmp_path):
    dd = _dd(tmp_path)
    html = _koppel_section(cockpit2._Stores(dd), "t", "semanticscholar")   # nog ongekoppeld → hulp toont
    assert "Voorbeeld" in html and "Semantic Scholar citaties" in html           # concrete invul-hulp (quotes ge-escaped)
