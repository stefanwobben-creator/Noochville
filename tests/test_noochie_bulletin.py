"""Tests voor Noochie's bulletin-mandaat (geabsorbeerd van Ronnie) — thread-vrij.

Tien scenario's:
1. Noochie abonneert zich op dag_eindigt — na publish staat er werk in de inbox.
2. Op dag_eindigt schrijft Noochie een bulletin (LLM gemockt, vier koppen aanwezig).
3. Lege dag (geen events) → bulletin wordt toch geschreven.
4. LLM-fout (returns None) → geen bestand, warning gelogd.
5. Noochie luistert op de acht event-typen in _TRACK (incl. means_gap_sensed).
6. Field Note wordt meegestuurd in de LLM-prompt.
7. Ontbrekende Field Note → geen crash, bulletin toch geschreven.
8. REGRESSIE: pulse_completed raakt ZOWEL missie-weging (noochie_weighed_in) ALS
   de verzameling (_events_today) — twee onafhankelijke handlers.
9. REGRESSIE: dag_begint raakt ZOWEL de reflectie-kans (inbox job via _maybe_reflect)
   ALS de verzameling (_events_today) — twee onafhankelijke handlers.
10. KANTEL: de prompt aan reason() bevat de kantel-instructie en de kantel-zin
    belandt in het tension_sensed-event na het bereiken van min_count=2.
"""
from __future__ import annotations
import logging
import pytest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.roles import Noochie
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill


def _make_noochie(tmp_path):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    registry.register(BulletinSchrijvenSkill())
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        records=None,
    )
    record = Record(
        id="noochie",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="De droom van NoochVille levend houden in het dagelijkse dorp",
            skills=["bulletin_schrijven"],
        ),
        source="seed",
    )
    noochie = Noochie(record, bus, registry, context)
    return noochie, bus


_MOCK_BULLETIN = (
    "# Dorpsbulletin 2026-06-15\n"
    "## Wat ik vandaag zag\nEen rustige dag in het dorp.\n"
    "## Wie was actief\nDe tijdwachter.\n"
    "## Wat ik signaleer\nNiets bijzonders.\n"
    "## Tot morgen\nTot morgen!"
)


def test_noochie_subscribes_to_dag_eindigt(tmp_path):
    noochie, bus = _make_noochie(tmp_path)
    assert noochie.inbox.pending() == 0
    bus.publish(Event("dag_eindigt", {}, "test"))
    assert noochie.inbox.pending() > 0


def test_noochie_writes_bulletin_on_dag_eindigt(tmp_path):
    noochie, bus = _make_noochie(tmp_path)
    noochie._events_today = [
        {"name": "dag_begint", "by": "facilitator", "note": ""},
        {"name": "pulse_completed", "by": "website_watcher", "note": ""},
    ]

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN):
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    files = list(bulletins_dir.iterdir())
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    for section in ("## Wat ik vandaag zag", "## Wie was actief",
                    "## Wat ik signaleer", "## Tot morgen"):
        assert section in content
    assert noochie._events_today == []


def test_noochie_handles_empty_run(tmp_path):
    noochie, bus = _make_noochie(tmp_path)

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN):
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    files = list(bulletins_dir.iterdir())
    assert len(files) == 1


def test_noochie_handles_llm_failure(tmp_path, caplog):
    noochie, bus = _make_noochie(tmp_path)
    noochie._events_today = [{"name": "dag_begint", "by": "facilitator", "note": ""}]

    with patch("nooch_village.llm.reason", return_value=None):
        with caplog.at_level(logging.WARNING):
            noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    assert not bulletins_dir.exists() or len(list(bulletins_dir.iterdir())) == 0
    assert any(
        "llm" in r.message.lower() or "bulletin" in r.message.lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )


def _drain(noochie) -> None:
    """Drain Noochie's inbox: voer elke event-job uit op de huidige thread."""
    while noochie.inbox.pending() > 0:
        job = noochie.inbox.take(timeout=0.05)
        if job and callable(job):
            job()


def test_noochie_listens_to_track_events(tmp_path):
    noochie, bus = _make_noochie(tmp_path)

    to_publish = [
        Event("tension_sensed",          {"by": "noochie",           "description": "spanning"}, "noochie"),
        Event("means_gap_sensed",         {"by": "kennis_scout",      "gap_key": "test_gap"},     "kennis_scout"),
        Event("pulse_completed",          {"by": "website_watcher"},                                       "website_watcher"),
        Event("tijdgeest_pulse_completed",{"by": "tijdgeest_wachter", "ok": True},                "tijdgeest_wachter"),
    ]
    with patch("nooch_village.llm.reason", return_value=None):
        for e in to_publish:
            bus.publish(e)
        _drain(noochie)

    collected_names = {e["name"] for e in noochie._events_today}
    assert "tension_sensed"           in collected_names
    assert "means_gap_sensed"         in collected_names
    assert "pulse_completed"          in collected_names
    assert "tijdgeest_pulse_completed" in collected_names


def test_noochie_includes_field_note_in_prompt(tmp_path):
    noochie, bus = _make_noochie(tmp_path)

    output_dir = Path(tmp_path) / "output"
    output_dir.mkdir()
    today = date.today().isoformat()
    field_note_text = "## Groei-analyse\nBezoekers stabiel op 234 unieke bezoekers."
    (output_dir / f"field_note_{today}.md").write_text(field_note_text, encoding="utf-8")

    noochie._events_today = [{"name": "dag_begint", "by": "facilitator", "note": ""}]

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN) as mock_llm:
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    assert mock_llm.called
    prompt = mock_llm.call_args[0][0]
    assert "Groei-analyse" in prompt
    assert "Bezoekers stabiel op 234" in prompt


def test_noochie_handles_missing_field_note(tmp_path):
    noochie, bus = _make_noochie(tmp_path)
    noochie._events_today = [{"name": "dag_begint", "by": "facilitator", "note": ""}]

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN):
        noochie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    assert len(list(bulletins_dir.iterdir())) == 1


def test_noochie_pulse_triggers_weigh_and_collect(tmp_path):
    """REGRESSIE: pulse_completed raakt ZOWEL _on_pulse_completed ALS _collect_event."""
    noochie, bus = _make_noochie(tmp_path)

    output_dir = Path(tmp_path) / "output"
    output_dir.mkdir()
    today = date.today().isoformat()
    note_path = str(output_dir / f"field_note_{today}.md")
    (output_dir / f"field_note_{today}.md").write_text(
        "## Test\nBezoekers: 100.", encoding="utf-8"
    )

    weigh_events: list[str] = []
    bus.subscribe("noochie_weighed_in", lambda e: weigh_events.append(e.name))

    mock_verdict = "VERDICT: ok\nREASON: missie-alignment prima."
    with patch("nooch_village.llm.reason", return_value=mock_verdict):
        bus.publish(Event("pulse_completed", {"note_path": note_path, "by": "website_watcher"}, "website_watcher"))
        _drain(noochie)

    assert "noochie_weighed_in" in weigh_events, "missie-weging moet hebben plaatsgevonden"
    collected = {e["name"] for e in noochie._events_today}
    assert "pulse_completed" in collected, "pulse_completed moet verzameld zijn door _collect_event"


def test_noochie_dag_begint_triggers_reflect_and_collect(tmp_path):
    """REGRESSIE: dag_begint raakt ZOWEL _maybe_reflect (inbox-job) ALS _collect_event."""
    noochie, bus = _make_noochie(tmp_path)
    assert noochie.inbox.pending() == 0

    with patch("nooch_village.llm.reason", return_value=None):
        bus.publish(Event("dag_begint", {"label": "test"}, "facilitator"))
        pending_before_drain = noochie.inbox.pending()
        _drain(noochie)

    assert pending_before_drain >= 2, (
        "dag_begint moet minimaal twee inbox-jobs opleveren: "
        "_maybe_reflect én _collect_event"
    )
    collected = {e["name"] for e in noochie._events_today}
    assert "dag_begint" in collected, "dag_begint moet verzameld zijn door _collect_event"


def test_noochie_reflect_kantel_in_prompt_and_tension(tmp_path):
    """KANTEL: prompt bevat kantel-instructie; kantel-zin belandt in tension_sensed na min_count=2."""
    noochie, bus = _make_noochie(tmp_path)

    mock_voorstel = (
        "Het dorp mist een vergelijkingspagina voor duurzame materialen. "
        "Een materiaalwijzer zou helpen omdat kopers bewuste keuzes kunnen maken. "
        "Dit advies kantelt als er al een externe vergelijkingssite bestaat die deze rol beter vult."
    )

    tensions: list[dict] = []
    bus.subscribe("tension_sensed", lambda e: tensions.append(dict(e.data)))

    prompts_gezien: list[str] = []

    def mock_reason(prompt: str):
        prompts_gezien.append(prompt)
        return mock_voorstel

    with patch("nooch_village.llm.reason", side_effect=mock_reason):
        # Eerste aanroep: count=1, nog onder min_count=2 — geen spanning
        noochie._reflect()
        assert len(tensions) == 0

        # Tweede aanroep: count=2, drempel bereikt — spanning gepubliceerd
        noochie._reflect()

    assert len(prompts_gezien) >= 2, "reason() moet minstens tweemaal zijn aangeroepen"
    prompt = prompts_gezien[0]
    assert "kantelt als" in prompt, f"kantel-instructie ontbreekt in prompt:\n{prompt}"

    assert len(tensions) >= 1, "tension_sensed moet na min_count=2 gepubliceerd zijn"
    description = tensions[0].get("description", "")
    assert "kantelt als" in description, (
        f"kantel-zin ontbreekt in de tension_sensed description:\n{description}"
    )
