"""Huis-regels (constraints): triage voedt het dorp. ✗-met-reden → constraint → reflex respecteert."""
from __future__ import annotations
import json

from nooch_village.constraints import Constraints
from nooch_village import cockpit


def test_constraint_store(tmp_path):
    c = Constraints(str(tmp_path / "constraints.json"))
    assert c.add("Alle producten moeten bio-afbreekbaar zijn", by="human", source="triage")
    assert c.add("alle producten moeten bio-afbreekbaar zijn") is False   # dedup (case-insensitief)
    assert c.texts() == ["Alle producten moeten bio-afbreekbaar zijn"]
    # herladen vanaf schijf
    assert Constraints(str(tmp_path / "constraints.json")).texts()[0].startswith("Alle producten")


def test_cockpit_toont_huisregels(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "human_inbox.json", "projects.json", "library.json"):
        (data / f).write_text("{}", encoding="utf-8")
    (data / "constraints.json").write_text(json.dumps(
        [{"text": "We bieden geen kinderschoenen aan", "source": "triage: schoolruil"}]),
        encoding="utf-8")
    page = cockpit.render_html(cockpit.gather(str(data)), csrf_token="t")
    assert "Huis-regels" in page and "geen kinderschoenen" in page
