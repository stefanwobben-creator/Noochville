"""Rapport-lus: het einddocument van een done-project gaat door het bestaande intake-pad
(kennisbank_intake.atomiseer, geïnjecteerde nep-LLM — geen netwerk) naar de kennisbank-STAGING
("even nakijken", mens-gated), nooit direct de bibliotheek in. Dekt: herkomst op de voorstellen
(source "project: <scope>", reference "/project?id=<pid>", source_date = afronddatum) en de
doorwerking naar de bibliotheek bij commit; skip zonder/te kort rapport; fail-closed zonder LLM
(geen half werk, latere run mag opnieuw); idempotentie (heropend + zelfde rapport → niets,
gewijzigd rapport → wél een nieuwe set); het daemon-pad (village._poll_board-stub) mét het
insight_proposed-metadata-event; Lara's log-only-poort (target="staging" schrijft nooit dubbel);
de backfill-CLI-helper (dry-run telt alleen); en de staging-view die de herkomst klikbaar toont."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from nooch_village.event_bus import EventBus, Event
from nooch_village.kennisbank_staging import StagingStore, commit_batch
from nooch_village.notes_store import NotesStore
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.project_signal import (backfill_reports_to_staging, report_source_hint,
                                          report_to_staging)
from nooch_village.projects import ProjectLedger
from nooch_village.village import Village
from nooch_village.views.kennisbank_staging import render_kennisbank_staging

RAPPORT = ("## Afbraakproef hennepzolen\n\n"
           "De proef liep 90 dagen onder industriële compostering. Meting: 87% van het "
           "zoolmateriaal was afgebroken na 90 dagen. Conclusie: het hennepcomposiet haalt "
           "de gestelde drempel; de vervolgstap is een veldproef onder thuiscompost-condities "
           "met wekelijkse bemonstering en een controlegroep van conventioneel zoolmateriaal.")

_LLM_ATOMS = [
    {"content": "Hennepzolen: 87% afgebroken na 90 dagen industriële compostering.",
     "subject": "materiaal", "provenance": "internal_data",
     "source": "LLM-verzonnen-bron", "reference": "", "flags": [], "link_hints": []},
    {"content": "Vervolgstap: veldproef onder thuiscompost-condities met controlegroep.",
     "subject": "materiaal", "provenance": "internal_judgment",
     "source": "x", "flags": [], "link_hints": []},
]


def _fake_reason(prompt, **kw):
    return json.dumps(_LLM_ATOMS)


def _boem(*a, **k):
    raise AssertionError("de LLM mag hier niet draaien")


def _done_project(tmp_path, scope="Afbraakproef hennep", rapport=RAPPORT):
    dd = str(tmp_path)
    led = ProjectLedger(f"{dd}/projects.json")
    pid = led.create("harry_hemp", scope, "human")
    led.complete(pid, "proef geslaagd")
    if rapport is not None:
        ProjectDocStore(dd).write(pid, rapport)
    return dd, led, pid


def _staging(dd):
    return StagingStore(f"{dd}/kennisbank_staging.json")


def _afronddatum(p) -> str:
    return datetime.fromtimestamp(float(p["updated_at"]), tz=timezone.utc).date().isoformat()


# ── 1. Rapport → voorstellen in de STAGING, met zichtbare herkomst ───────────────────────────

def test_rapport_naar_staging_met_herkomst(tmp_path):
    dd, led, pid = _done_project(tmp_path)
    res = report_to_staging(dd, led.get(pid), reason_fn=_fake_reason)
    assert res["atoms"] == 2
    b = _staging(dd).get(res["batch"])
    assert b["kind"] == "projectrapport"
    assert b["source_label"] == "project: Afbraakproef hennep"
    for a in b["atoms"]:
        assert a["source"] == "project: Afbraakproef hennep"      # LLM-bron bewust overschreven
        assert a["reference"] == f"/project?id={pid}"             # interne link naar het project
        assert a["source_date"] == _afronddatum(led.get(pid))     # afronddatum
    # Mens-gated: NIETS in de bibliotheek tot de reviewer de set commit.
    assert NotesStore(f"{dd}/notes.json").all() == []


def test_commit_zet_herkomst_door_naar_bibliotheek(tmp_path):
    dd, led, pid = _done_project(tmp_path)
    res = report_to_staging(dd, led.get(pid), reason_fn=_fake_reason)
    assert commit_batch(_staging(dd), res["batch"], dd) == (2, 0, 0)
    kaarten = NotesStore(f"{dd}/notes.json").all()
    assert len(kaarten) == 2
    for k in kaarten:
        assert k.source == report_source_hint(led.get(pid))
        assert k.reference == f"/project?id={pid}"
        assert k.source_date == _afronddatum(led.get(pid))


# ── 2. Geen of te kort rapport → skip, zonder LLM ────────────────────────────────────────────

def test_geen_of_te_kort_rapport_skipt_zonder_llm(tmp_path):
    dd, led, pid = _done_project(tmp_path, rapport=None)
    assert report_to_staging(dd, led.get(pid), reason_fn=_boem) == {"skipped": "geen rapport"}
    ProjectDocStore(dd).write(pid, "Te kort voor een rapport.")
    assert report_to_staging(dd, led.get(pid), reason_fn=_boem) == {"skipped": "geen rapport"}
    assert _staging(dd).open_batches() == []
    assert report_to_staging(dd, {}, reason_fn=_boem) == {"skipped": "geen project"}


# ── 3. Zonder LLM: fail-closed, geen half werk, latere run mag opnieuw ───────────────────────

def test_zonder_llm_fail_closed_en_later_opnieuw(tmp_path):
    dd, led, pid = _done_project(tmp_path)
    res = report_to_staging(dd, led.get(pid), reason_fn=lambda *a, **k: None)
    assert res == {"failed": "geen atomen (LLM)"}
    assert _staging(dd).open_batches() == []                      # geen kaartjes, geen half werk
    # Er is bewust GEEN ledger-record gezet: een latere run met werkende ladder maakt de set alsnog.
    res = report_to_staging(dd, led.get(pid), reason_fn=_fake_reason)
    assert res["atoms"] == 2 and len(_staging(dd).open_batches()) == 1


# ── 4. Idempotentie: heropend + zelfde rapport → niets; gewijzigd rapport → nieuwe set ───────

def test_idempotent_heropend_zelfde_en_gewijzigd_rapport(tmp_path):
    dd, led, pid = _done_project(tmp_path)
    assert report_to_staging(dd, led.get(pid), reason_fn=_fake_reason)["atoms"] == 2
    # Heropend + opnieuw afgerond met ongewijzigd rapport → IntakeLedger-dedupe, geen LLM.
    led.reopen(pid)
    led.complete(pid, "opnieuw afgerond")
    assert report_to_staging(dd, led.get(pid), reason_fn=_boem) == {"skipped": "al verwerkt"}
    assert len(_staging(dd).open_batches()) == 1
    # Gewijzigd rapport → wél een nieuwe staging-set (alleen het nieuwe werk).
    ProjectDocStore(dd).write(pid, RAPPORT + "\n\nNieuwe bevinding: thuiscompost haalt 60%.")
    res = report_to_staging(dd, led.get(pid), reason_fn=_fake_reason)
    assert res.get("batch") and len(_staging(dd).open_batches()) == 2


# ── 5. Daemon-pad: _poll_board zet het rapport in staging en geeft de poort zijn afzender ────

def _watch(tmp_path, ledger):
    """Minimale village-stub (zelfde patroon als test_project_signal) mét data_dir."""
    bus = EventBus(name="test")
    events = []
    bus.subscribe("insight_proposed", lambda e: events.append(e.data))
    ctx = SimpleNamespace(projects=ledger, deliverables=None, data_dir=str(tmp_path),
                          _autonomous_done=set())
    return SimpleNamespace(context=ctx, bus=bus, _activated_seen=set(),
                           _completed_seen=set()), events


def test_poll_board_rapport_naar_staging_met_event(tmp_path, monkeypatch):
    monkeypatch.setattr("nooch_village.llm.reason", _fake_reason)   # report_to_staging importeert lazy
    dd, led, pid = _done_project(tmp_path)
    stub, events = _watch(tmp_path, led)
    Village._poll_board(stub)
    batches = _staging(dd).open_batches()
    assert len(batches) == 1 and batches[0]["kind"] == "projectrapport"
    assert events == [{"project_id": pid, "atoms": 2, "batch_id": batches[0]["id"],
                       "target": "staging"}]
    # Het bestaande signaal-pad blijft onaangeraakt naast de rapport-lus draaien.
    from nooch_village.radar_store import RadarStore
    assert len(RadarStore(f"{dd}/radar.json").for_role("harry_hemp")) == 1
    Village._poll_board(stub)                                       # tweede poll → geen dubbel
    assert len(_staging(dd).open_batches()) == 1 and len(events) == 1


# ── 6. Lara's poort: target="staging" wordt herkend en alleen gelogd — nooit dubbel schrijven ─

def test_librarian_logt_staging_event_en_schrijft_niet(tmp_path):
    from nooch_village.roles import Librarian
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.skills import SkillRegistry, Skill

    class _CurateBoem(Skill):
        name = "curate"
        description = "mag voor target=staging nooit draaien"

        def run(self, payload, context):
            raise AssertionError("curate mag niet draaien: de schrijfweg is de staging-review")

    bus = EventBus(name="t")
    registry = SkillRegistry()
    registry.register(_CurateBoem())
    notes = NotesStore(str(tmp_path / "notes.json"))
    rec = Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["curate"]), source="seed")
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path), records=None,
                          library=SimpleNamespace(status=lambda w: None),
                          lexicon=SimpleNamespace(concept_for_word=lambda w: None),
                          notes=notes)
    lib = Librarian(rec, bus, registry, ctx)
    # Zelfs mét een fuzzy-veld erbij wint target="staging": alleen loggen, geen tweede schrijfweg.
    lib._on_insight_proposed(Event("insight_proposed",
        {"target": "staging", "project_id": "p1", "atoms": 2, "batch_id": "stg_x",
         "fuzzy": "zou anders gecureerd en weggeschreven worden"}, "board_watch"))
    assert notes.all() == []


# ── 7. Backfill: dry-run telt alleen; echt maakt sets; herdraaien is idempotent ──────────────

def test_backfill_dry_run_vs_echt(tmp_path):
    dd = str(tmp_path)
    led = ProjectLedger(f"{dd}/projects.json")
    a = led.create("harry_hemp", "Proef A", "human")
    b = led.create("harry_hemp", "Proef B", "human")
    c = led.create("harry_hemp", "Zonder rapport", "human")
    led.create("harry_hemp", "Loopt nog", "human")                  # geen done → telt niet mee
    for pid in (a, b, c):
        led.complete(pid)
    docs = ProjectDocStore(dd)
    docs.write(a, RAPPORT)
    docs.write(b, RAPPORT + "\n\nVariant B: meting onder zeewater-condities toegevoegd.")
    res = backfill_reports_to_staging(led, dd, dry_run=True, reason_fn=_boem)
    assert res == {"done": 3, "batches": 2, "atoms": 0, "skipped": 1, "mislukt": 0}
    assert _staging(dd).open_batches() == []                        # dry-run schrijft niets
    res = backfill_reports_to_staging(led, dd, reason_fn=_fake_reason)
    assert res == {"done": 3, "batches": 2, "atoms": 4, "skipped": 1, "mislukt": 0}
    assert len(_staging(dd).open_batches()) == 2
    res = backfill_reports_to_staging(led, dd, reason_fn=_boem)     # herdraaien: ledger-dedupe
    assert res == {"done": 3, "batches": 0, "atoms": 0, "skipped": 3, "mislukt": 0}
    assert len(_staging(dd).open_batches()) == 2


# ── 8. Staging-view: herkomst zichtbaar — "project: <scope>" + klikbare interne link ─────────

def test_staging_view_toont_projectherkomst_met_link(tmp_path):
    dd, led, pid = _done_project(tmp_path)
    res = report_to_staging(dd, led.get(pid), reason_fn=_fake_reason)
    st = SimpleNamespace(staging=_staging(dd))
    html = render_kennisbank_staging(st, res["batch"], csrf_token="t")
    assert "project: Afbraakproef hennep" in html
    assert f"<a href='/project?id={pid}'>" in html                  # interne reference is klikbaar
