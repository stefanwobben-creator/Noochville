"""Noochie werkt een spanning uit tot een concreet voorstel (voorstel_schrijven).

LLM gemockt; fail-closed zonder LLM. Plus de inbox-opslag en de cockpit-delegatie."""
from __future__ import annotations
from unittest.mock import patch

from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
from nooch_village.human_inbox import HumanInbox


def test_voorstel_met_llm():
    out = "SCOPE: Onderzoek Delpher.\nAANPAK: API-check + dekkingstest.\nAFWEGING: alleen bij NL-prioriteit."
    with patch("nooch_village.llm.reason", return_value=out):
        res = VoorstelSchrijvenSkill().run({"tension": "NL-corpus onbruikbaar", "role": "harry_hemp"})
    assert res["ok"] and "SCOPE" in res["voorstel"] and res["by"] == "noochie"


def test_voorstel_fail_closed_zonder_llm():
    with patch("nooch_village.llm.reason", return_value=None):
        res = VoorstelSchrijvenSkill().run({"tension": "iets"})
    assert not res["ok"]


def test_voorstel_zonder_spanning():
    res = VoorstelSchrijvenSkill().run({"tension": ""})
    assert not res["ok"]


def test_add_voorstel_inbox(tmp_path):
    hi = HumanInbox(str(tmp_path / "i.json"))
    iid = hi.add_voorstel("nl_corpus", "SCOPE: ...", by="noochie", origin="nl_corpus")
    item = hi.get(iid)
    assert item["type"] == "voorstel" and item["context"]["voorstel"] == "SCOPE: ..."
    # dedup per spanning zolang open
    assert hi.add_voorstel("nl_corpus", "ander", by="noochie") == iid
