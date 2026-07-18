"""Taak 1 — de koppelingslaag: skill als gedeeld dorpsmiddel aan een belofte.

Additief: koppelen/ontkoppelen werkt en logt, de domeinpoort houdt beslis-skills bij de
domeinhouder, en de UITVOERING blijft in deze fase ongewijzigd (`effectief` is weergave).
"""
from __future__ import annotations

from nooch_village import acc_ids, cockpit2, skill_links, skill_meta
from nooch_village.ai_tasks import AITaskStore, KIND_MIDDEL


_ROLE = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _first_acc(st, role=_ROLE):
    return acc_ids.acc_id_at(st.records.get(role).definition, 0)


# ── De store ─────────────────────────────────────────────────────────────────

def test_middel_en_autonoom_leven_naast_elkaar(tmp_path):
    ai = AITaskStore(str(tmp_path / "ai.json"))
    ai.add("rol_x", "acc_a", "persona_1", "schrijft de code")
    link = ai.add_link("rol_x", "acc_a", "site_health", gelegd_door="lead@nooch.earth")
    assert link is not None and link.kind == KIND_MIDDEL and link.skill == "site_health"
    assert link.gelegd_door == "lead@nooch.earth" and link.gelegd_op > 0

    soorten = sorted(t.kind for t in ai.for_acc("rol_x", "acc_a"))
    assert soorten == ["autonoom", "middel"]
    assert [t.skill for t in ai.links_for_role("rol_x")] == ["site_health"]


def test_zelfde_middel_op_zelfde_belofte_is_een_koppeling(tmp_path):
    ai = AITaskStore(str(tmp_path / "ai.json"))
    a = ai.add_link("rol_x", "acc_a", "site_health")
    b = ai.add_link("rol_x", "acc_a", "site_health")
    assert a.id == b.id and len(ai.links_for_role("rol_x")) == 1


def test_effectief_is_dna_plus_links(tmp_path):
    dd, st = _st(tmp_path)
    rec = st.records.get(_ROLE)
    dna = set(rec.definition.skills or [])
    st.ai.add_link(_ROLE, _first_acc(st), "site_health")
    eff = skill_links.effectief(rec, st.ai)
    assert dna <= eff and "site_health" in eff          # DNA is de vloer, links zijn de plus


def test_effectief_faalt_zacht_zonder_store_of_record():
    assert skill_links.effectief(None, None) == set()


# ── De domeinpoort (absoluut, geen policy-omweg) ─────────────────────────────

def _hoeder(st, rid="hoeder"):
    """Een rol die het bibliotheek-domein houdt (de cockpit-fixture heeft er geen)."""
    from nooch_village.models import Record, RecordType, RoleDefinition
    st.records.put(Record(id=rid, type=RecordType.ROLE, parent="mother_earth__nooch",
                          definition=RoleDefinition(purpose="hoeder van de woordenschat",
                                                    accountabilities=["woorden beoordelen"],
                                                    domains=["bibliotheek"])))
    return st.records.get(rid)


def test_beslisskill_alleen_bij_domeinhouder(tmp_path):
    dd, st = _st(tmp_path)
    lara = _hoeder(st)
    ander = st.records.get(_ROLE)

    mag, _ = skill_meta.koppelbaar("keyword_review", lara)
    assert mag is True
    mag2, reden = skill_meta.koppelbaar("keyword_review", ander)
    assert mag2 is False and "bibliotheek" in reden and "domeinhouder" in reden


def test_domeinhouders_vindt_de_juiste_rol(tmp_path):
    dd, st = _st(tmp_path)
    _hoeder(st)
    assert skill_meta.domeinhouders("keyword_review", st.records.all()) == ["hoeder"]
    assert skill_meta.domeinhouders("site_health", st.records.all()) == []   # vrij middel


def test_leesskill_is_vrij_koppelbaar(tmp_path):
    dd, st = _st(tmp_path)
    assert skill_meta.koppelbaar("site_health", st.records.get(_ROLE))[0] is True


def test_domeinpoort_faalt_closed(tmp_path):
    assert skill_meta.koppelbaar("keyword_review", None)[0] is False
    assert skill_meta.koppelbaar("", object())[0] is False


# ── Dispatch: koppelen, weigeren, ontkoppelen, loggen ────────────────────────

def test_koppelen_via_dispatch_logt_in_de_kroniek(tmp_path):
    dd, st = _st(tmp_path)
    aid = _first_acc(st)
    _, msg = cockpit2.dispatch(dd, "skilllink_add",
                               {"role": [_ROLE], "acc_id": [aid], "skill": ["site_health"],
                                "next": ["/x"]}, username="guest")
    assert "gekoppeld" in msg

    st2 = cockpit2._Stores(dd)
    assert [t.skill for t in st2.ai.links_for_role(_ROLE)] == ["site_health"]
    rows = st2.link_kroniek.for_role(_ROLE)
    assert len(rows) == 1
    assert rows[0]["action"] == "gelegd" and rows[0]["skill"] == "site_health"
    assert rows[0]["acc_id"] == aid


def test_dispatch_weigert_beslisskill_bij_niet_domeinhouder(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "skilllink_add",
                               {"role": [_ROLE], "acc_id": [_first_acc(st)],
                                "skill": ["keyword_review"], "next": ["/x"]}, username="guest")
    assert "Niet gekoppeld" in msg and "domeinhouder" in msg
    assert cockpit2._Stores(dd).ai.links_for_role(_ROLE) == []


def test_ontkoppelen_logt_ook(tmp_path):
    dd, st = _st(tmp_path)
    aid = _first_acc(st)
    cockpit2.dispatch(dd, "skilllink_add", {"role": [_ROLE], "acc_id": [aid],
                                            "skill": ["site_health"], "next": ["/x"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    tid = st2.ai.links_for_role(_ROLE)[0].id
    _, msg = cockpit2.dispatch(dd, "aitask_remove", {"tid": [tid], "next": ["/x"]}, username="guest")
    assert "verwijderd" in msg

    st3 = cockpit2._Stores(dd)
    assert st3.ai.links_for_role(_ROLE) == []
    acties = [r["action"] for r in st3.link_kroniek.for_role(_ROLE)]
    assert acties == ["gelegd", "verwijderd"]


def test_koppelen_geweigerd_voor_niet_circle_lead(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "skilllink_add",
                               {"role": [_ROLE], "acc_id": [_first_acc(st)],
                                "skill": ["site_health"], "next": ["/x"]},
                               username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "Circle Lead" in msg
    assert cockpit2._Stores(dd).ai.links_for_role(_ROLE) == []


# ── Weergave ─────────────────────────────────────────────────────────────────

def test_dialoog_biedt_middelen_aan_maar_niet_de_beslisskill(tmp_path):
    dd, st = _st(tmp_path)
    frag = cockpit2.render_aitask(st, _ROLE, _first_acc(st), csrf_token="t", fragment=True)
    assert "skilllink_add" in frag
    assert "site_health" in frag                        # vrij koppelbaar middel
    assert "keyword_review" not in frag                 # beslis-skill: niet eens aangeboden


def test_dialoog_biedt_beslisskill_wel_aan_bij_domeinhouder(tmp_path):
    dd, st = _st(tmp_path)
    _hoeder(st)
    frag = cockpit2.render_aitask(st, "hoeder", _first_acc(st, "hoeder"),
                                  csrf_token="t", fragment=True)
    assert "keyword_review" in frag


def test_rolpagina_toont_gekoppeld_middel(tmp_path):
    dd, st = _st(tmp_path)
    cockpit2.dispatch(dd, "skilllink_add", {"role": [_ROLE], "acc_id": [_first_acc(st)],
                                            "skill": ["site_health"], "next": ["/x"]},
                      username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), _ROLE, "overview", csrf_token="t")
    assert "site_health" in page
    assert "🔗" in page
