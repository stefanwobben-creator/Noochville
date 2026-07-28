"""Hefboom 2 — de voorstel-generator: bronnen, dedup, cap, formulering en de mens-poort."""
from __future__ import annotations

import os

from nooch_village.config import Context
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.project_proposals import (
    accept, generate_proposals, overlay_for, radar_key, reject, running_topics)
from nooch_village.projects import ProjectLedger
from nooch_village.radar_store import RadarStore


def _sharpen(ruw, anchors=None):
    """Deterministische stand-in voor de LLM-wizard (die zelf al fail-soft is)."""
    return f"{ruw.capitalize()} — done"


def _setup(tmp_path):
    dd = str(tmp_path)
    ctx = Context(settings={}, data_dir=dd)
    ctx.projects = ProjectLedger(os.path.join(dd, "projects.json"))
    recs = Records(os.path.join(dd, "governance_records.json"))
    recs.put(Record(id="harry", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="wetenschap")))
    ctx.records = recs
    radar = RadarStore(os.path.join(dd, "radar.json"))
    return ctx, recs, radar, dd


def _approved(radar, content, role="harry"):
    rid = radar.add(role=role, feed="f", kind="nieuws", content=content, rationale="want relevant")
    radar.set_status(rid, "goedgekeurd")
    return rid


def test_goedgekeurd_radarsignaal_wordt_een_voorstel(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    rid = _approved(radar, "eu banned pfas in footwear")

    res = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)

    assert len(res["created"]) == 1
    p = ctx.projects.get(res["created"][0]["pid"])
    assert p["status"] == "proposed"            # niet op het bord
    assert p["parent"] is None                  # standalone, mens-gestuurd
    assert p["owner"] == "harry"                # eigenaar = de rol van het signaal
    assert p["scope"].endswith("— done")        # via sharpen_outcome (verleden tijd, Engels)
    assert p["origin"] == "proposal:radar"
    # de herkomst staat op de kaart, zodat de mens kan wegen waar dit vandaan komt
    assert any("approved radar signal" in e["text"] for e in p.get("log", []))
    assert overlay_for(dd).seen(radar_key(rid))


def test_wachtend_of_afgewezen_signaal_levert_niets_op(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    radar.add(role="harry", feed="f", kind="nieuws", content="nog niet beoordeeld")
    weg = radar.add(role="harry", feed="f", kind="nieuws", content="weggeklikt")
    radar.set_status(weg, "afgewezen")

    assert generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)["created"] == []


def test_signaal_van_onbekende_rol_levert_niets_op(tmp_path):
    """Fail-closed: zonder bestaande eigenaar-rol geen voorstel (anders een wees op het bord)."""
    ctx, recs, radar, dd = _setup(tmp_path)
    _approved(radar, "iets", role="bestaat_niet")

    assert generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)["created"] == []


def test_dedup_ook_na_afwijzen(tmp_path):
    """Ruis-bron nummer één: elke puls hetzelfde opnieuw voorstellen. Ook een AFGEWEZEN voorstel
    (het project is dan weg) mag niet terugkomen — daarom leeft de herinnering in de overlay."""
    ctx, recs, radar, dd = _setup(tmp_path)
    _approved(radar, "eu banned pfas in footwear")

    eerste = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)
    tweede = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)
    assert tweede["created"] == [] and tweede["skipped_dedup"] == 1

    reject(ctx.projects, dd, eerste["created"][0]["pid"])
    derde = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)
    assert derde["created"] == [] and derde["skipped_dedup"] == 1
    assert overlay_for(dd).get(eerste["created"][0]["key"])["status"] == "rejected"


def test_cap_slaat_over_en_zwijgt_niet(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    for i in range(5):
        _approved(radar, f"signaal {i}")

    res = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen, cap=2)

    assert len(res["created"]) == 2
    assert len(res["skipped_cap"]) == 3                  # expliciet gerapporteerd, niet stil afgekapt
    assert all(s["raw"] for s in res["skipped_cap"])     # mét wát er is overgeslagen
    assert len(ctx.projects.proposals()) == 2
    # de overgeslagen signalen zijn NIET onthouden → een volgende ronde met ruimte pakt ze alsnog
    vervolg = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen, cap=5)
    assert len(vervolg["created"]) == 3


def test_cap_telt_de_al_openstaande_voorstellen_mee(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    ctx.projects.create("harry", "een voorstel dat er al ligt", "role", status="proposed")
    _approved(radar, "nog een signaal")

    res = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen, cap=1)

    assert res["created"] == [] and len(res["skipped_cap"]) == 1 and res["open_before"] == 1


def test_sharpen_faalt_zacht(tmp_path):
    """Valt de LLM weg, dan liever de ruwe tekst dan geen voorstel."""
    ctx, recs, radar, dd = _setup(tmp_path)
    _approved(radar, "ruwe tekst")

    def _kapot(ruw, anchors=None):
        raise RuntimeError("geen LLM-sleutel")

    res = generate_proposals(ctx, records=recs, radar=radar, sharpen=_kapot)
    assert ctx.projects.get(res["created"][0]["pid"])["scope"] == "ruwe tekst"


def test_accepteren_zet_het_in_de_normale_flow(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    _approved(radar, "eu banned pfas in footwear")
    pid = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)["created"][0]["pid"]

    assert accept(ctx.projects, dd, pid, person="stefan") is True
    p = ctx.projects.get(pid)
    assert p["status"] == "future" and p["person"] == "stefan"
    assert ctx.projects.proposals() == []
    assert accept(ctx.projects, dd, pid) is False        # niet twee keer


def test_afwijzen_haalt_het_weg(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    _approved(radar, "eu banned pfas in footwear")
    pid = generate_proposals(ctx, records=recs, radar=radar, sharpen=_sharpen)["created"][0]["pid"]

    assert reject(ctx.projects, dd, pid) is True
    assert ctx.projects.get(pid) is None and ctx.projects.proposals() == []


def test_een_gewoon_project_is_geen_voorstel(tmp_path):
    """accept/reject werken UITSLUITEND op status proposed — nooit op een project van het bord."""
    ctx, recs, radar, dd = _setup(tmp_path)
    pid = ctx.projects.create("harry", "gewoon werk", "human", status="future")

    assert accept(ctx.projects, dd, pid) is False
    assert reject(ctx.projects, dd, pid) is False
    assert ctx.projects.get(pid)["status"] == "future"


def test_kroniek_is_opt_in(tmp_path):
    """De tweede bron staat default uit: een kennisgat is nog door niemand op relevantie beoordeeld."""
    from nooch_village.evidence_ledger import EvidenceLedger
    ctx, recs, radar, dd = _setup(tmp_path)
    ctx.projects.start(ctx.projects.create("harry", "onderzoek barefoot", "human",
                                          status="queued", keyword="barefoot"))
    ev = EvidenceLedger(os.path.join(dd, "evidence_ledger.jsonl"))
    ev.record(role_id="harry", skill="openalex_evidence", query="barefoot soles", source="openalex",
              status="leeg", result_ref="0 hits")

    uit = generate_proposals(ctx, records=recs, radar=radar, evidence=ev, sharpen=_sharpen)
    assert uit["created"] == []

    aan = generate_proposals(ctx, records=recs, radar=radar, evidence=ev, sharpen=_sharpen,
                             kroniek=True)
    assert len(aan["created"]) == 1
    p = ctx.projects.get(aan["created"][0]["pid"])
    assert p["status"] == "proposed" and p["origin"] == "proposal:kroniek" and p["owner"] == "harry"
    assert any("gap in the Chronicle" in e["text"] for e in p.get("log", []))


def test_lopende_onderwerpen_negeren_afgeronde_en_voorgestelde_projecten(tmp_path):
    ctx, recs, radar, dd = _setup(tmp_path)
    led = ctx.projects
    led.create("harry", "loopt", "human", status="queued", keyword="barefoot")
    klaar = led.create("harry", "klaar", "human", status="queued", keyword="afgerond thema")
    led.complete(klaar)
    led.create("harry", "voorstel", "role", status="proposed", keyword="voorgesteld thema")

    assert running_topics(led) == ["barefoot"]
