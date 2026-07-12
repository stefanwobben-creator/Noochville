"""De Kroniek fase 1 — EvidenceLedger (het bewijsregister). Onthouden: elke run (feit, leegte, fout)
landt getypt; leeg/fout zijn eersteklas; geheugen-eerst en het ladder-signaal werken; corrupte regels
worden fail-loud overgeslagen."""
from __future__ import annotations

import json

import pytest

from nooch_village.evidence_ledger import EvidenceLedger, STATUSES


def _led(tmp_path):
    return EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))


def test_record_schrijft_en_valideert_status(tmp_path):
    led = _led(tmp_path)
    row = led.record(role_id="harry_hemp", skill="epo_patents", query="PHA zolen",
                     source="epo", status="fout", result_ref="")
    assert row["id"] and row["ts"] and row["status"] == "fout"
    # één regel op schijf, geldig JSON
    lines = [l for l in open(led.path, encoding="utf-8").read().splitlines() if l.strip()]
    assert len(lines) == 1 and json.loads(lines[0])["skill"] == "epo_patents"
    # onbekende status = fail-closed, geen stille default
    with pytest.raises(ValueError):
        led.record(role_id="x", skill="s", query="q", source="b", status="onbekend")
    assert set(STATUSES) == {"bevestigd", "leeg", "fout"}


def test_leeg_en_fout_zijn_eersteklas(tmp_path):
    led = _led(tmp_path)
    led.record(role_id="harry_hemp", skill="openalex_evidence", query="enkelmobiliteit",
               source="openalex", status="leeg")                       # no_data, géén fout
    led.record(role_id="harry_hemp", skill="epo_patents", query="abrasie", source="epo", status="fout")
    statuses = {r["status"] for r in led.all_records()}
    assert "leeg" in statuses and "fout" in statuses                   # beide bevraagbaar, niet weggeslikt
    assert led.for_skill("openalex_evidence")[0]["status"] == "leeg"


def test_geheugen_eerst_last_good(tmp_path):
    led = _led(tmp_path)
    q = ("semscholar_tldr", "mulch film")
    led.record(role_id="harry_hemp", skill=q[0], query=q[1], source="semscholar", status="leeg", ts=100)
    led.record(role_id="harry_hemp", skill=q[0], query=q[1], source="semscholar", status="bevestigd",
               result_ref="deliv-1", ts=200)
    led.record(role_id="harry_hemp", skill=q[0], query=q[1], source="semscholar", status="fout", ts=300)
    good = led.last_good(*q)
    assert good is not None and good["result_ref"] == "deliv-1"        # het bevestigde, niet de latere fout
    assert led.last(*q)["status"] == "fout"                            # last = de nieuwste, ongeacht status


def test_consecutive_failures_ladder_signaal(tmp_path):
    led = _led(tmp_path)
    S, B = "epo_patents", "epo"
    led.record(role_id="harry_hemp", skill=S, query="q1", source=B, status="fout", ts=1)
    led.record(role_id="harry_hemp", skill=S, query="q2", source=B, status="bevestigd", ts=2)  # breekt de reeks
    led.record(role_id="harry_hemp", skill=S, query="q3", source=B, status="fout", ts=3)
    led.record(role_id="harry_hemp", skill=S, query="q4", source=B, status="fout", ts=4)
    assert led.consecutive_failures(S, B) == 2                         # alleen de trailing fouten tellen
    assert led.consecutive_failures(S, "andere_bron") == 0


def test_cache_en_verse_read(tmp_path):
    led = _led(tmp_path)
    led.record(role_id="r", skill="s", query="q", source="b", status="bevestigd")
    assert len(led.all_records()) == 1                                 # cache incrementeel bijgewerkt
    vers = _led(tmp_path)                                              # nieuwe instance leest van schijf
    assert len(vers.all_records()) == 1 and vers.all_records()[0]["skill"] == "s"


def test_corrupte_regel_wordt_overgeslagen(tmp_path):
    led = _led(tmp_path)
    led.record(role_id="r", skill="s", query="q", source="b", status="leeg")
    with open(led.path, "a", encoding="utf-8") as f:
        f.write("{ dit is geen geldige json\n")                        # corrupte regel erbij
    vers = _led(tmp_path)
    assert len(vers.all_records()) == 1                                # goede regel blijft; corrupte weg


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
