"""Stil skill-aanbod bij checklist-toevoeging.

- plan_offers: cockpit-side match (LLM gestubd), machine-check tegen DNA, fail-closed.
- Trigger: alleen op de "Uitvoerplan"-checklist bij een echte rol-owner; II/andere titel → geen aanbod.
- Accepteren: hangt skill+payload aan het item, aanbod weg. Negeren = afwijzen (blijft staan).
- Render: het aanbod verschijnt als "🤖 kan dit oppakken"-knop.
"""
from __future__ import annotations

from unittest.mock import patch

from nooch_village import cockpit2
from nooch_village.skill_match import plan_offers
from nooch_village.registry_factory import shared_registry
from nooch_village.models import Record, RoleDefinition, RecordType

_TITLE = "Uitvoerplan"


def _owner(skills):
    return Record(id="mother_earth__nooch__website_developer", type=RecordType.ROLE, parent="mother_earth__nooch",
                  definition=RoleDefinition(purpose="p", accountabilities=["seo"], domains=[], skills=skills),
                  source="seed")


def _fake_reason(payload_json):
    def _r(prompt, **k):
        return payload_json
    return _r


# ── plan_offers ────────────────────────────────────────────────────────────────
def test_plan_offers_match():
    rec = _owner(["openalex_evidence"])
    js = '{"matches":[{"skill":"openalex_evidence","payload":{"term":"hennep"}}]}'
    with patch("nooch_village.llm.reason", side_effect=_fake_reason(js)):
        out = plan_offers(rec, ["onderzoek hennep-claims"], shared_registry())
    assert len(out) == 1 and out[0]["skill"] == "openalex_evidence"
    assert out[0]["payload"] == {"term": "hennep"} and isinstance(out[0]["payload_ok"], bool)


def test_plan_offers_skill_niet_in_dna_wordt_none():
    rec = _owner(["openalex_evidence"])
    js = '{"matches":[{"skill":"verzonnen_skill","payload":{}}]}'   # buiten de harde DNA-lijst
    with patch("nooch_village.llm.reason", side_effect=_fake_reason(js)):
        out = plan_offers(rec, ["iets"], shared_registry())
    assert out == [None]


def test_plan_offers_geen_dna_skills():
    with patch("nooch_village.llm.reason", side_effect=_fake_reason("x")):
        assert plan_offers(_owner([]), ["iets"], shared_registry()) == [None]


def test_plan_offers_owner_none_en_llm_none_en_exceptie():
    assert plan_offers(None, ["a", "b"], shared_registry()) == [None, None]
    with patch("nooch_village.llm.reason", side_effect=_fake_reason(None)):     # LLM gaf niets
        assert plan_offers(_owner(["openalex_evidence"]), ["a"], shared_registry()) == [None]
    def _boom(prompt, **k):
        raise RuntimeError("stuk")
    with patch("nooch_village.llm.reason", side_effect=_boom):                  # exceptie → fail-closed
        assert plan_offers(_owner(["openalex_evidence"]), ["a"], shared_registry()) == [None]


# ── trigger via dispatch (check_add) ─────────────────────────────────────────────
def _setup(tmp_path, title=_TITLE):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    pid = st.projects.create(rid, "Doel", "human")
    cl = st.projects.checklist_add(pid, title=title)
    return dd, pid, cl["id"]


def _offer_of(dd, pid, clid):
    cl = next(c for c in cockpit2._Stores(dd).projects.get(pid)["checklists"] if c["id"] == clid)
    return cl["items"][-1].get("offer")


def test_trigger_alleen_op_uitvoerplan(tmp_path):
    dd, pid, clid = _setup(tmp_path, title=_TITLE)
    fake = [{"skill": "openalex_evidence", "payload": {"term": "x"}, "payload_ok": True}]
    with patch("nooch_village.cockpit2.plan_offers", return_value=fake):
        cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["onderzoek"], "next": ["/"]}, "guest")
    off = _offer_of(dd, pid, clid)
    assert off and off["skill"] == "openalex_evidence"


def test_trigger_andere_titel_geen_aanbod(tmp_path):
    dd, pid, clid = _setup(tmp_path, title="Mijn eigen lijst")
    fake = [{"skill": "openalex_evidence", "payload": {}, "payload_ok": True}]
    with patch("nooch_village.cockpit2.plan_offers", return_value=fake):
        cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["x"], "next": ["/"]}, "guest")
    assert _offer_of(dd, pid, clid) is None                     # geen "Uitvoerplan" → geen aanbod


def test_trigger_ii_owner_geen_aanbod(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create("ii:mother_earth__nooch", "Doel", "human")   # II-owner: geen rol-DNA
    clid = st.projects.checklist_add(pid, title=_TITLE)["id"]
    called = []
    with patch("nooch_village.cockpit2.plan_offers", side_effect=lambda *a, **k: called.append(1) or [None]):
        cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["x"], "next": ["/"]}, "guest")
    assert not called and _offer_of(dd, pid, clid) is None      # stil overgeslagen, geen match-call


# ── accepteren + render ──────────────────────────────────────────────────────────
def test_accept_hangt_skill_aan_item(tmp_path):
    dd, pid, clid = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.check_add(pid, clid, "onderzoek")
    item = st.projects.get(pid)["checklists"][0]["items"][-1]
    st.projects.set_item_offer(pid, clid, item["id"],
                               {"skill": "openalex_evidence", "payload": {"term": "x"}, "payload_ok": True})
    cockpit2.dispatch(dd, "check_accept",
                      {"pid": [pid], "clid": [clid], "item": [item["id"]], "next": ["/"]}, "guest")
    it2 = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][-1]
    assert it2.get("skill") == "openalex_evidence" and it2.get("payload") == {"term": "x"}
    assert "offer" not in it2                                    # aanbod verbruikt


def test_render_toont_aanbod_knop(tmp_path):
    dd, pid, clid = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.check_add(pid, clid, "onderzoek")
    item = st.projects.get(pid)["checklists"][0]["items"][-1]
    st.projects.set_item_offer(pid, clid, item["id"],
                               {"skill": "openalex_evidence", "payload": {}, "payload_ok": True})
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "🤖 kan dit oppakken" in frag and "value='check_accept'" in frag
