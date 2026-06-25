"""De twee poorten uit de governance-filosofie: rijpheid (accountability = gestolde frictie) en
omkeerbaarheid (een project mag vrij tenzij het onherstelbare schade kan doen)."""
from __future__ import annotations

from nooch_village.maturity import friction_evidence, irreversible_harm


def test_friction_evidence():
    assert friction_evidence("Dit komt elke week terug en blijft liggen")
    assert friction_evidence("kans", "anderen wachten op deze data")
    assert not friction_evidence("Eenmalig idee om reviews te tonen")


def test_irreversible_harm():
    assert irreversible_harm("Nieuwsbrief versturen naar klanten")
    assert irreversible_harm("Adverteren op Google", "betaald")
    assert irreversible_harm("Prijs verlagen met korting")
    # omkeerbaar experiment → vrij
    assert not irreversible_harm("Reviews tonen op de productpagina als test")
    assert not irreversible_harm("Een blog schrijven over veganisme")


def test_rijpheidspoort_in_secretary_check():
    from nooch_village.roloverleg import secretary_check
    from nooch_village.governance import Records
    from nooch_village.models import Record, RoleDefinition, RecordType
    recs = Records.__new__(Records)
    recs.path = ":mem:"; recs._data = {}
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="Nooch", policies=[]), source="seed"))
    recs.put(Record(id="scout", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="markt", accountabilities=[]), source="seed"))
    # accountability zonder frictie-bewijs → 'let op: nog niet gestold'
    item = {"id": "x", "role_id": "scout", "kind": "amend_role",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]},
            "reason": "lijkt me nuttig", "title": "Social", "reactions": []}
    issues = secretary_check(item, recs)
    assert any("nog niet gestold" in i["msg"] for i in issues)
    # mét frictie-bewijs → geen rijpheids-let-op
    item2 = dict(item, reason="dit komt elke week terug, anderen wachten erop")
    assert not any("nog niet gestold" in i["msg"] for i in secretary_check(item2, recs))


def test_project_omkeerbaar_naar_bord_onomkeerbaar_concept(tmp_path):
    # via de cockpit-dispatch: een omkeerbaar experiment → queued, een risicovol → draft
    import json
    from nooch_village import cockpit
    data = tmp_path / "data"; data.mkdir()
    for f in ("governance_records.json", "projects.json", "library.json"):
        (data / f).write_text("{}", encoding="utf-8")
    from nooch_village.human_inbox import HumanInbox
    from nooch_village.projects import ProjectLedger
    inbox = HumanInbox(str(data / "human_inbox.json"))
    iid = inbox.add_opportunity("Reviews tonen op de productpagina", by="analyst",
                                wat="sterren tonen als test")
    # geen LLM in sandbox → formulate_project valt terug op de titel (omkeerbaar) → queued
    cockpit._dispatch_action(str(data), "tac_project", iid, "", extra={"owner": "analyst"})
    ps = ProjectLedger(str(data / "projects.json")).all()
    assert ps and ps[0]["status"] == "queued"             # omkeerbaar experiment → direct op bord

    iid2 = inbox.add_opportunity("Nieuwsbrief versturen naar klanten", by="analyst",
                                 wat="mailen naar klanten")
    cockpit._dispatch_action(str(data), "tac_project", iid2, "", extra={"owner": "analyst"})
    ps2 = ProjectLedger(str(data / "projects.json")).all()
    risky = next(p for p in ps2 if "Nieuwsbrief" in str(p["scope"]))
    assert risky["status"] == "draft"                     # mogelijk onomkeerbaar → concept
