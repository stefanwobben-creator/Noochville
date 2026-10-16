"""`village bord_eigenaren` (16 oktober 2026): projecten waarvan de trekker geen gebruiker is.
Dry-run als standaard, --apply met back-up, idempotent. Open projecten: een `person` zonder
people-record en elke `agent` worden leeg ("No owner"); met --email-naar-persoon wordt een
login-e-mailadres het people-id (ook op een gearchiveerd project). Verder blijft alles staan."""
from __future__ import annotations

import os
import sys

from nooch_village import bord_eigenaren as be, cli, cockpit2


def _dorp(tmp_path):
    dd = str(tmp_path)
    st = cockpit2._Stores(dd)
    stefan = st.people.add("Stefan Wobben", "stefan@nooch.earth")
    lotte = st.people.add("Lotte Mulder", "lotte@nooch.earth")
    sid = st.personas.add("Sid the Science Kid")
    pj = st.projects
    ids = {
        "mylo": pj.create("strategie", "Mylo leather", "human", person="stefan@nooch.earth"),
        "biowrap": pj.create("strategie", "BioWrap", "human", person="stefan@nooch.earth"),
        "oud_mail": pj.create("scout", "Same Shoe", "human", person="stefan@nooch.earth"),
        "chitosan": pj.create("strategie", "Chitosan", "human", agent=sid.id),
        "billy_done": pj.create("scout", "Trend monitoring", "human", agent=sid.id),
        "oud_ai": pj.create("scout", "Old AI work", "human", agent=sid.id),
        "spook": pj.create("strategie", "Ghost owner", "human", person="iemand@elders.nl"),
        "lotte": pj.create("strategie", "Lotte's work", "human", person=lotte.id),
        "leeg": pj.create("strategie", "Nobody", "human"),
    }
    pj.get(ids["billy_done"])["status"] = "done"           # afgerond (geen startstatus)
    p = pj.get(ids["oud_mail"])
    p.setdefault("log", []).append({"who": "stefan@nooch.earth", "text": "x", "at": 1})
    p.setdefault("checklists", []).append({"items": [{"id": "i1", "text": "t", "done": False,
                                                      "geclaimd_door": "stefan@nooch.earth"}]})
    pj._save()
    pj.archive(ids["oud_mail"])
    pj.archive(ids["oud_ai"])
    return dd, ids, stefan, lotte


def _plan(dd, **kw):
    st = cockpit2._Stores(dd)
    return {r["pid"]: r for r in be.plan(st.projects, st.people, st.personas, **kw)}


def test_dry_run_per_project_zonder_vlag(tmp_path):
    dd, ids, _s, _l = _dorp(tmp_path)
    plan_ = _plan(dd)
    assert set(plan_) == {ids["mylo"], ids["biowrap"], ids["chitosan"], ids["billy_done"], ids["spook"]}
    assert plan_[ids["mylo"]]["wijzigingen"] == [{"veld": "person", "van": "stefan@nooch.earth", "naar": "",
                                                  "reden": "not a user (no people record)"}]
    assert [w["veld"] for w in plan_[ids["chitosan"]]["wijzigingen"]] == ["agent"]
    assert "Sid the Science Kid" in plan_[ids["chitosan"]]["wijzigingen"][0]["reden"]


def test_email_naar_persoon_ook_op_het_gearchiveerde_project(tmp_path):
    dd, ids, stefan, _l = _dorp(tmp_path)
    plan_ = _plan(dd, email_naar_persoon=True)
    for k in ("mylo", "biowrap", "oud_mail"):
        assert plan_[ids[k]]["wijzigingen"] == [{"veld": "person", "van": "stefan@nooch.earth",
                                                 "naar": stefan.id,
                                                 "reden": "login e-mail → people-id of Stefan Wobben"}]
    assert plan_[ids["oud_mail"]]["gearchiveerd"]
    # een onbekend e-mailadres wordt leeg; een gearchiveerde agent blijft staan
    assert plan_[ids["spook"]]["wijzigingen"][0]["naar"] == ""
    assert ids["oud_ai"] not in plan_ and ids["lotte"] not in plan_ and ids["leeg"] not in plan_


def test_toepassen_raakt_alleen_person_en_agent_en_is_idempotent(tmp_path):
    dd, ids, stefan, lotte = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    voor = {pid: dict(p) for pid, p in ((p["id"], p) for p in st.projects.all())}
    plan_ = be.plan(st.projects, st.people, st.personas, email_naar_persoon=True)
    assert be.toepassen(st.projects, plan_) == 6
    na = {p["id"]: p for p in cockpit2._Stores(dd).projects.all()}
    assert na[ids["mylo"]]["person"] == na[ids["biowrap"]]["person"] == na[ids["oud_mail"]]["person"] == stefan.id
    assert na[ids["chitosan"]]["agent"] is None and na[ids["billy_done"]]["agent"] is None
    assert na[ids["billy_done"]]["status"] == "done"
    assert na[ids["oud_ai"]]["agent"] == voor[ids["oud_ai"]]["agent"]          # gearchiveerd: ongemoeid
    assert na[ids["lotte"]]["person"] == lotte.id
    # historie en geclaimd_door blijven
    assert na[ids["oud_mail"]]["log"][-1]["who"] == "stefan@nooch.earth"
    assert na[ids["oud_mail"]]["checklists"][0]["items"][0]["geclaimd_door"] == "stefan@nooch.earth"
    for pid, p in na.items():
        for k in set(p) | set(voor[pid]):
            if k not in ("person", "agent", "updated_at"):
                assert p.get(k) == voor[pid].get(k), (pid, k)
    st2 = cockpit2._Stores(dd)
    assert be.plan(st2.projects, st2.people, st2.personas, email_naar_persoon=True) == []
    assert be.tekst([]).startswith("Nothing to change")


def test_cli_dry_run_schrijft_niets_en_apply_maakt_eerst_een_back_up(tmp_path, monkeypatch, capsys):
    dd, ids, stefan, _l = _dorp(tmp_path)
    from nooch_village import config
    echt = config.load_context

    def _ctx(_base):
        c = echt(_base)
        c.data_dir = dd
        return c
    monkeypatch.setattr(config, "load_context", _ctx)
    pad = os.path.join(dd, "projects.json")
    voor = open(pad, encoding="utf-8").read()
    monkeypatch.setattr(sys, "argv", ["village", "bord_eigenaren", "--email-naar-persoon"])
    cli.main()
    uit = capsys.readouterr().out
    assert "DRY-RUN" in uit and "Mylo leather" in uit and f"{stefan.id} (Stefan Wobben)" in uit
    assert open(pad, encoding="utf-8").read() == voor
    monkeypatch.setattr(sys, "argv", ["village", "bord_eigenaren", "--email-naar-persoon", "--apply"])
    cli.main()
    uit = capsys.readouterr().out
    assert "Back-up:" in uit and "6 project(s) changed." in uit
    back = [f for f in os.listdir(dd) if f.startswith("projects.json.bak-bord-eigenaren-")]
    assert len(back) == 1 and open(os.path.join(dd, back[0]), encoding="utf-8").read() == voor
    monkeypatch.setattr(sys, "argv", ["village", "bord_eigenaren", "--email-naar-persoon", "--apply"])
    cli.main()
    assert "Nothing to change" in capsys.readouterr().out
