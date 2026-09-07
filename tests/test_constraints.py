"""Huis-regels (constraints): triage voedt het dorp. ✗-met-reden → constraint → reflex respecteert."""
from __future__ import annotations
import json

from nooch_village.constraints import Constraints



def test_constraint_store(tmp_path):
    c = Constraints(str(tmp_path / "constraints.json"))
    assert c.add("Alle producten moeten bio-afbreekbaar zijn", by="human", source="triage")
    assert c.add("alle producten moeten bio-afbreekbaar zijn") is False   # dedup (case-insensitief)
    assert c.texts() == ["Alle producten moeten bio-afbreekbaar zijn"]
    # herladen vanaf schijf
    assert Constraints(str(tmp_path / "constraints.json")).texts()[0].startswith("Alle producten")


