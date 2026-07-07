"""Noochie's tweewekelijkse verslag: gegrond (feiten in de prompt), Noochie-stem, fail-closed zonder LLM
(nooit een verzonnen tekst), en schrijven naar output."""
from __future__ import annotations
import datetime
import os
import types

from nooch_village.observations import ObservationStore
from nooch_village.verslag import build_noochie_verslag, write_noochie_verslag


def _st(tmp_path):
    obs = ObservationStore(str(tmp_path / "observations.jsonl"))
    obs.record_daily("plausible", "plausible_visitors_day", 25, bron="plausible", datum="2026-07-05")
    os.makedirs(str(tmp_path / "output"), exist_ok=True)
    with open(str(tmp_path / "output" / "field_note_2026-07-05.md"), "w") as f:
        f.write("# Field Note 2026-07-05\nDe site trok 25 bezoekers vandaag.")
    with open(str(tmp_path / "system_log.jsonl"), "w") as f:
        f.write('{"event": "tijdgeest_signaal", "by": "harry_hemp"}\n')
    return types.SimpleNamespace(observations=obs)


def test_verslag_is_gegrond_en_in_noochie_stem(tmp_path):
    captured = {}
    def fake_reason(prompt):
        captured["p"] = prompt
        return "Beste founder, wat een mooie twee weken voor ons dorp! De cijfers spreken."
    md, facts = build_noochie_verslag(_st(tmp_path), str(tmp_path), datetime.date(2026, 7, 7), 14, reason=fake_reason)
    # feiten zitten in de prompt → de LLM kan niet anders dan gronden
    assert "DATA-ROLL-UP" in captured["p"] and "plausible_visitors_day" in captured["p"]
    assert "Field Note 2026-07-05" in captured["p"] and "25 bezoekers" in captured["p"]
    assert "harry_hemp" in captured["p"]                       # agent-activiteit meegegeven
    assert "Noochie" in captured["p"] and "Verzin GEEN cijfers" in captured["p"]   # stem + anti-fabricatie
    # output wrapt het narratief
    assert "Noochie's tweewekelijkse verslag" in md and "wat een mooie twee weken" in md
    assert "Geen cijfer is verzonnen" in md and facts["field_notes"]


def test_verslag_fail_closed_zonder_llm(tmp_path):
    md, facts = build_noochie_verslag(_st(tmp_path), str(tmp_path), datetime.date(2026, 7, 7),
                                      14, reason=lambda p: None)
    assert md is None and facts["data_rollup"]                 # geen LLM → geen (verzonnen) verslag


def test_write_verslag_naar_output(tmp_path):
    path = write_noochie_verslag(_st(tmp_path), str(tmp_path), datetime.date(2026, 7, 7),
                                 reason=lambda p: "Hoi founder! Een klein verslagje.")
    assert path.endswith("verslag_2026-07-07.md") and "verslagje" in open(path, encoding="utf-8").read()
    # fail-closed schrijft niets
    assert write_noochie_verslag(_st(tmp_path), str(tmp_path), datetime.date(2026, 7, 7), reason=lambda p: "") is None
