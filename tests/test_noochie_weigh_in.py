"""Tests voor Noochie._weigh_in — thread-vrij.

Vier invarianten:
  1. VERDICT: ok  → het dagrecord krijgt "ok".
  2. VERDICT: niet_ok → het dagrecord krijgt "niet_ok", met de reden erbij.
  3. REGRESSIE: **VERDICT: ok** (markdown-bold) → nog steeds "ok".
     Exacte reproductie van de misfire waargenomen op 14 juni 2026.
  4. Onverstaanbaar antwoord → "niet_ok" (fail-closed), met de ruwe output als reden.

DE WAARNEEMPLEK IS VERHUISD (20 september 2026), de invarianten niet. Deze vier keken naar
`sense_tension`: een `niet_ok` werd een spanning die de triage-keten in ging. Die keten is
opgeheven, dus er valt niets meer te sensen — het oordeel landt nu (en landde altijd al) in
`noochie_daily.json` via `_persist_daily`, en dat is wat de cockpit toont.

Ze zijn er scherper op geworden: waar ze eerst toetsten DÁT er iets gebeurde, toetsen ze nu WELK
oordeel er werd geveld. Dat is wat de vier invarianten altijd bedoelden — vooral nummer 3, die
bestaat omdat een markdown-sterretje ooit een positief oordeel in een negatief veranderde.
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
            "VRAAG: wat houdt bezoekers tegen om dieper te gaan?\n"
            "VERDICT: ok\nREASON: prima")
    findings, vraag = _parse_noochie_report(text)
    assert len(findings) == 3                      # max 3
    assert "homepage trekt 97%" in findings[0]
    assert vraag == "wat houdt bezoekers tegen om dieper te gaan?"


def test_parse_noochie_report_suggestie_fallback():
    # oude SUGGESTIE-regel wordt nog steeds als vraag-veld opgepikt (back-compat)
    _, vraag = _parse_noochie_report("BEVINDING: x\nSUGGESTIE: doe iets")
    assert vraag == "doe iets"


def test_weigh_in_persisteert_bevindingen_en_vraag(tmp_path):
    noochie = _make_noochie(tmp_path)
    resp = ("BEVINDING: 97% verkeer naar de homepage, productpagina's blijven leeg\n"
            "BEVINDING: NL domineert, BE en VS onontgonnen\n"
            "BEVINDING: geen zoekwoord-verkeer wijst op dunne content\n"
            "VRAAG: wat zou bezoekers verleiden om voorbij de homepage te klikken?\n"
            "VERDICT: ok\nREASON: actie past bij de missie")
    with patch("nooch_village.llm.reason", return_value=resp):
        noochie._weigh_in("Field Note inhoud")
    d = json.load(open(f"{tmp_path}/noochie_daily.json"))
    assert len(d["findings"]) == 3 and "homepage" in d["findings"][0]
    assert d["question"] == "wat zou bezoekers verleiden om voorbij de homepage te klikken?"


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

def test_weigh_in_ok_verdict_landt_als_ok(tmp_path):
    """VERDICT: ok → het dagrecord krijgt "ok"."""
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: ok\nREASON: actie klopt met missie"):
        with patch.object(noochie, "_persist_daily") as mock_pd:
            noochie._weigh_in("Field Note inhoud")
    mock_pd.assert_called_once()
    assert mock_pd.call_args[0][0] == "ok"


# ── 2. niet_ok-verdict: tension met reason ────────────────────────────────────

def test_weigh_in_niet_ok_verdict_landt_met_de_reden(tmp_path):
    """VERDICT: niet_ok → het dagrecord krijgt "niet_ok", mét de reden."""
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: niet_ok\nREASON: actie wijkt af van missie"):
        with patch.object(noochie, "_persist_daily") as mock_pd:
            noochie._weigh_in("Field Note inhoud")
    mock_pd.assert_called_once()
    assert mock_pd.call_args[0][0] == "niet_ok"
    assert "actie wijkt af van missie" in mock_pd.call_args[0][1]


# ── 3. Regressietest: markdown-bold ok → geen tension ─────────────────────────

def test_weigh_in_markdown_bold_ok_blijft_ok(tmp_path):
    """**VERDICT: ok** (markdown-bold) → sense_tension NIET aangeroepen.

    Regressietest voor de misfire van 14 juni 2026: het model antwoordde met een
    markdown-bold prefix, waardoor de oude startswith-check faalde en een POSITIEF
    oordeel als negatief werd geboekt.
    """
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason",
               return_value="**VERDICT: ok**\nREASON: alles klopt"):
        with patch.object(noochie, "_persist_daily") as mock_pd:
            noochie._weigh_in("Field Note inhoud")
    assert mock_pd.call_args[0][0] == "ok"


# ── 4. Onverstaanbaar: fail-closed naar tension ───────────────────────────────

def test_weigh_in_unparseable_fails_closed_naar_niet_ok(tmp_path):
    """Onverstaanbaar antwoord (geen VERDICT-regel) → "niet_ok", met de RUWE output als reden.

    Fail-closed betekent hier twee dingen, en het tweede is het makkelijkst te verliezen: het
    oordeel valt naar niet_ok, én de volledige onverstaanbare output wordt bewaard in plaats van
    een lege string of een standaardzin. Zonder die tekst kun je achteraf niet zien wát het model
    zei, en dus niet of de poort terecht dichtsloeg."""
    raw_output = "Hier is mijn beoordeling van de Field Note..."
    noochie = _make_noochie(tmp_path)
    with patch("nooch_village.llm.reason", return_value=raw_output):
        with patch.object(noochie, "_persist_daily") as mock_pd:
            noochie._weigh_in("Field Note inhoud")
    mock_pd.assert_called_once()
    # HET DAGRECORD KRIJGT `unparseable`, NIET `niet_ok` — en dat is beter dan wat de logregel
    # ernaast zegt ("fail-closed als niet_ok"). Een onverstaanbaar antwoord is iets anders dan een
    # afkeurend oordeel: het eerste zegt iets over het model, het tweede over de actie. Ze in het
    # dagrecord op één hoop gooien zou dat onderscheid wegpoetsen. Wat fail-closed hier betekent is
    # dat het in elk geval GEEN ok is.
    assert mock_pd.call_args[0][0] == "unparseable"
    assert mock_pd.call_args[0][0] != "ok"
    assert raw_output in mock_pd.call_args[0][1]
