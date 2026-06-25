"""Governance-referentiebank: parse echte exports tot rol-skeletten (drop projecten/namen),
zoek op verwantschap, en gebruik als few-shot-grounding bij het Holacracy-correct formuleren
van een accountability. Vertrouwelijk: blijft een eigen store, los van content/notes."""
from __future__ import annotations

from nooch_village.governance_examples import (
    GovernanceExamples, parse_governance_text, few_shot_block)
from nooch_village.inbox_actions import formulate_accountability, _route_kans_to_governance


_EXPORT = """Marketing
Purpose
Het merk zichtbaar maken
Domeinen
De nieuwsbrief
Verantwoordelijkheden
Ontwikkelen en beheren van de socialemediakanalen
Schrijven van wekelijkse nieuwsbrieven aan
klanten
Projecten
Nieuwe webshop live (Actief) Jan Jansen
Facilitator
Purpose
Governance verloopt volgens de grondwet
Domeinen
Aan deze rol is geen domein verleend om te beheren.
Verantwoordelijkheden
Faciliteren van de overleggen
Projecten
Er zijn geen projecten.
"""


def test_parse_drop_projecten_en_namen():
    roles = parse_governance_text(_EXPORT, "e-commerce")
    by_name = {r["role"]: r for r in roles}
    assert "Marketing" in by_name and "Facilitator" in by_name
    m = by_name["Marketing"]
    assert m["purpose"] == "Het merk zichtbaar maken"
    assert m["domains"] == ["De nieuwsbrief"]
    # vervolgregel 'klanten' is samengevoegd met de vorige accountability
    assert "Ontwikkelen en beheren van de socialemediakanalen" in m["accountabilities"]
    assert any("nieuwsbrieven aan klanten" in a for a in m["accountabilities"])
    # projecten en persoonsnamen zijn NIET bewaard (vertrouwelijk)
    import json
    blob = json.dumps(roles, ensure_ascii=False)
    assert "Jan Jansen" not in blob and "webshop" not in blob


def test_store_zoek_en_few_shot(tmp_path):
    store = GovernanceExamples(str(tmp_path / "ge.json"))
    store.replace(parse_governance_text(_EXPORT, "e-commerce"))
    hits = store.search("merk zichtbaar nieuwsbrieven", 2)
    assert hits and hits[0]["role"] == "Marketing"          # meest verwant
    block = few_shot_block(store, "nieuwsbrieven merk", k=2)
    assert "Marketing" in block and "socialemediakanalen" in block
    # leeg/afwezig → lege grounding (fail-closed)
    assert few_shot_block(GovernanceExamples(str(tmp_path / "leeg.json")), "x") == ""


def test_formulate_accountability_en_regel_en_failclosed():
    out = formulate_accountability("social media bijhouden", "posts plaatsen",
                                   examples_block="(voorbeelden)",
                                   llm_reason=lambda p: "Bewaken van de socialemediakanalen van Nooch")
    assert out == "Bewaken van de socialemediakanalen van Nooch"
    # zonder LLM → fail-closed naar de titel
    assert formulate_accountability("social media bijhouden", "x",
                                    llm_reason=lambda p: None) == "social media bijhouden"


def test_route_naar_governance_gebruikt_geformuleerde_accountability(tmp_path):
    from nooch_village.governance import Records
    from nooch_village.models import Record, RoleDefinition, RecordType
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                    definition=RoleDefinition(purpose="Nooch", policies=[]), source="seed"))
    recs.put(Record(id="scout", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="markt observeren", accountabilities=[]),
                    source="seed"))
    res = _route_kans_to_governance(
        recs, "scout", "social media bijhouden", "posts plaatsen", "meer bereik", None,
        examples_block="(voorbeelden)",
        llm_reason=lambda p: "Bewaken van de socialemediakanalen")
    assert res["status"] in ("adopted", "escalated")
    if res["status"] == "adopted":
        accs = recs.get("scout").definition.accountabilities
        assert "Bewaken van de socialemediakanalen" in accs   # geformuleerd, niet de ruwe titel
