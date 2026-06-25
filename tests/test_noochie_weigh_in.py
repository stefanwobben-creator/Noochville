"""Tests voor Noochie._weigh_in — thread-vrij.

Vier invarianten:
  1. VERDICT: ok  → sense_tension NIET aangeroepen.
  2. VERDICT: niet_ok → sense_tension aangeroepen met reason als description.
  3. REGRESSIE: **VERDICT: ok** (markdown-bold) → sense_tension NIET aangeroepen.
     Exacte reproductie van de misfire waargenomen op 14 juni 2026.
  4. Onverstaanbaar antwoord → sense_tension WORDT aangeroepen (fail-closed).
"""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch, patch as _patch

import json
from nooch_village.roles import Noochie, _parse_noochie_report
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry


def test_parse_noochie_report():
    text = ("**BEVINDING:** homepage trekt 97% van het verkeer\n"
            "- BEVINDING: NL domineert, BE/VS onontgonnen\n"
            "BEVINDING: geen zoekwoord-verkeer\n"
            "BEVINDING: vierde wordt genegeerd\n"
            "SUGGESTIE: koppel homepage aan missiepagina's\n"
            "VERDICT: ok\nREASON: prima")
    findings, suggestion = _parse_noochie_report(text)
    assert len(findings) == 3                      # max 3
    assert "homepage trekt 97%" in findings[0]
    assert suggestion == "koppel homepage aan missiepagina's"


def test_weigh_in_persisteert_bevindingen_en_suggestie(tmp_path):
    noochie = _make_noochie(tmp_path)
    resp = ("BEVINDING: 97% verkeer naar de homepage, productpagina's blijven leeg\n"
            "BEVINDING: NL domineert, BE en VS onontgonnen\n"
            "BEVINDING: geen zoekwoord-verkeer wijst op dunne content\n"
            "SUGGESTIE: koppel de homepage aan de missiepagina's\n"
            "VERDICT: ok\nREASON: actie past bij de missie")
    with patch("nooch_village.llm.reason", return_value=resp):
        noochie._weigh_in("Field Note inhoud")
    d = json.load(open(f"{tmp_path}/noochie_daily.json"))
    assert len(d["findings"]) == 3 and "homepage" in d["findings"][0]
    assert d["suggestion"] == "koppel de homepage aan de missiepagina's"


def _make_noochie(tmp_path):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=None,
        records=None,
        observations=None,
    )
    record = Record(
        id="noochie",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="missiestem", accountabilities=[], domains=[], skills=[]),
        source="seed",
    )
    return Noochie(record, bus, registry, context)


# ── 1. ok-verdict: geen tension ───────────────────────────────────────────────

def test_weigh_in_ok_verdict_does_not_sense_tension(tmp_path):
    """VERDICT: ok → sense_tension niet aangeroepen."""
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: ok\nREASON: actie klopt met missie"):
        with patch.object(noochie, "sense_tension") as mock_st:
            noochie._weigh_in("Field Note inhoud")
    mock_st.assert_not_called()


# ── 2. niet_ok-verdict: tension met reason ────────────────────────────────────

def test_weigh_in_niet_ok_verdict_calls_sense_tension(tmp_path):
    """VERDICT: niet_ok → sense_tension aangeroepen met reason als description."""
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: niet_ok\nREASON: actie wijkt af van missie"):
        with patch.object(noochie, "sense_tension") as mock_st:
            noochie._weigh_in("Field Note inhoud")
    mock_st.assert_called_once()
    assert "actie wijkt af van missie" in mock_st.call_args[0][0]


# ── 3. Regressietest: markdown-bold ok → geen tension ─────────────────────────

def test_weigh_in_markdown_bold_ok_does_not_sense_tension(tmp_path):
    """**VERDICT: ok** (markdown-bold) → sense_tension NIET aangeroepen.

    Regressietest voor de misfire van 14 juni 2026: LLM antwoordde met
    markdown-bold prefix, waardoor de oude startswith-check faalde en
    sense_tension onterecht werd aangeroepen op een positieve beoordeling.
    """
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason",
               return_value="**VERDICT: ok**\nREASON: alles klopt"):
        with patch.object(noochie, "sense_tension") as mock_st:
            noochie._weigh_in("Field Note inhoud")
    mock_st.assert_not_called()


# ── 4. Onverstaanbaar: fail-closed naar tension ───────────────────────────────

def test_weigh_in_unparseable_fails_closed_to_tension(tmp_path):
    """Onverstaanbaar antwoord (geen VERDICT-regel) → sense_tension aangeroepen met ruwe output.

    Fail-closed betekent hier: de volledige onverstaanbare LLM-output gaat als
    description naar sense_tension, niet een lege string of een standaard-fallback.
    """
    raw_output = "Hier is mijn beoordeling van de Field Note..."
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason", return_value=raw_output):
        with patch.object(noochie, "sense_tension") as mock_st:
            noochie._weigh_in("Field Note inhoud")
    mock_st.assert_called_once()
    description = mock_st.call_args[0][0]
    assert description == raw_output
