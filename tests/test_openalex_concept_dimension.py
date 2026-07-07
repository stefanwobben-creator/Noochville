"""OpenAlex concept-dimensie: gepinde concept-ID's (query via /concepts/<id> DIRECT, geen naamgenoot),
config-selectie (label→ID), opruiming van de vervuilde biologie-totalen (idempotent), collector per concept
(weekly-snapshot), en de tegel die 'per concept' aanbiedt náást keyword/land."""
from __future__ import annotations
import datetime
import logging
import types

from nooch_village.observations import ObservationStore
from nooch_village.source_status import SourceStatusStore
from nooch_village.skills_impl.openalex import OpenalexSkill
from nooch_village.collector import collect_daily_observations, _dimension_values

_CONCEPTS = "C2777448596:circular economy, C54924851:sustainable agriculture, C2911178952:vegan diet"


def _ctx(**s):
    base = {"openalex_concepts": _CONCEPTS}
    base.update(s)
    return types.SimpleNamespace(settings=base, library=None)


# ── contract: directe /concepts/<id>, géén search= ───────────────────────────
def test_openalex_concept_direct_id_geen_naamgenoot():
    s = OpenalexSkill()
    assert s.DIMENSION == "concept"
    urls = []
    api = {"C2777448596": {"works_count": 60727, "cited_by_count": 840784},
           "C54924851": {"works_count": 97598, "cited_by_count": 646054}}

    def fake_fetch(url):
        urls.append(url)
        return api[url.split("/concepts/")[1].split("?")[0]]
    out = s.daily_dimension_values(_ctx(), "2026-07-06",
                                   ["circular economy", "sustainable agriculture"], _fetch=fake_fetch)
    assert all("/concepts/C" in u and "search=" not in u for u in urls)         # directe ID, geen search-ranking
    assert out[("works", "circular economy")] == 60727
    assert out[("citations", "sustainable agriculture")] == 646054


def test_openalex_onbekend_label_en_fail_closed():
    s = OpenalexSkill()
    assert s.daily_dimension_values(_ctx(), "2026-07-06", ["onbekend"], _fetch=lambda u: {}) == {}   # niet in config
    boom = lambda u: (_ for _ in ()).throw(RuntimeError("429"))
    assert s.daily_dimension_values(_ctx(), "2026-07-06", ["vegan diet"], _fetch=boom) == {}          # fout → geen entry


def test_daily_values_is_dimensie_only():
    assert OpenalexSkill().daily_values(_ctx(), "2026-07-06") == {"works": None, "citations": None}


# ── selectie + cap ───────────────────────────────────────────────────────────
def test_concept_selectie_labels_uit_config():
    assert _dimension_values(_ctx(), "concept") == ["circular economy", "sustainable agriculture", "vegan diet"]


def test_concept_cap_en_drop_log(caplog):
    ctx = _ctx(openalex_concepts=", ".join(f"C{i:03d}:concept {i:02d}" for i in range(10)),
               openalex_dimension_max="3")
    with caplog.at_level(logging.WARNING):
        got = _dimension_values(ctx, "concept")
    assert len(got) == 3 and "dimensie 'concept' afgekapt op 3" in caplog.text and "7 waarde(n) gedropt" in caplog.text


# ── opruiming: vervuilde biologie-totalen weg (idempotent), dimensie blijft ──
def test_remove_metric_ruimt_undimensioned_op(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    obs.record_daily("openalex", "openalex_works_day", 274760, bron="openalex", datum="2026-06-29")
    obs.record_daily("openalex", "openalex_works_day", 274760, bron="openalex", datum="2026-07-06")
    obs.record_daily("openalex", "openalex_works_day::circular_economy", 60727, bron="openalex",
                     datum="2026-07-06", meta={"dimension": "concept", "value": "circular economy"})
    assert obs.remove_metric("openalex_works_day", bron="openalex") == 2        # alleen de undimensioned totalen
    assert obs.daily_series("openalex_works_day", bron="openalex") == []        # weg
    assert len(obs.dimensioned_series("openalex_works_day", bron="openalex")["circular economy"]) == 1  # dim onaangetast
    assert obs.remove_metric("openalex_works_day", bron="openalex") == 0        # idempotent


# ── collector per concept (weekly-snapshot → maandag) ────────────────────────
class _FakeOA(OpenalexSkill):
    def daily_dimension_values(self, context, datum, labels, *, _fetch=None):
        return {("works", "circular economy"): 60727, ("citations", "circular economy"): 840784}


class _Reg:
    def __init__(self, s): self._s = s
    def all(self): return self._s


def test_collector_openalex_concept_idempotent(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    sources = SourceStatusStore(str(tmp_path / "s.json")); sources.set_active("openalex", True)
    reg = _Reg([_FakeOA()])
    collect_daily_observations(reg, sources, obs, _ctx(), today=datetime.date(2026, 7, 8))     # wo → maandag 07-06
    w = [r for r in obs._read_all() if r["metric"] == "openalex_works_day::circular_economy"]
    assert w and w[0]["value"] == 60727 and w[0]["datum"] == "2026-07-06"        # weekly → maandag
    assert w[0]["meta"] == {"dimension": "concept", "value": "circular economy"}
    assert collect_daily_observations(reg, sources, obs, _ctx(), today=datetime.date(2026, 7, 8)) == []  # idempotent


# ── tegel: drie dimensie-bronnen naast elkaar (keyword/land/concept) ─────────
def test_drie_dimensie_bronnen_naast_elkaar(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views import metrics as vm
    C = "mother_earth__nooch"
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ids = {
        "gsc": st.metrics.add_kpi(C, "Vertoningen (GSC)", "n", origin="gsc", veld="impressions",
                                  categorie="Zoekprestaties", aard="reeks", meetwijze="systeem", auto=True)["id"],
        "plausible": st.metrics.add_kpi(C, "Bezoekers (Plausible)", "n", origin="plausible", veld="visitors",
                                        categorie="Website", aard="reeks", meetwijze="systeem", auto=True)["id"],
        "openalex": st.metrics.add_kpi(C, "Academische werken (OpenAlex)", "n", origin="openalex", veld="works",
                                       categorie="Content", aard="reeks", meetwijze="systeem", auto=True)["id"],
    }
    st2 = cockpit2._Stores(dd)
    srcs = {s["id"]: s for s in vm._sources_for(st2, st2.records.get(C))}
    dims = {src: [d[0] for d in srcs[f"kpi:{mid}"]["dims"]] for src, mid in ids.items()}
    assert "keyword" in dims["gsc"] and "country" in dims["plausible"] and "concept" in dims["openalex"]
    assert "concept" not in dims["gsc"] and "keyword" not in dims["openalex"]    # elk exclusief zijn eigen dim
