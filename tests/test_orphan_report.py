"""Wees-bestand-rapportage: een bestand op schijf zonder 'file'-attachment-entry = wees; een geregistreerd
bestand niet. Read-only (rapporteert, wijzigt niets)."""
from __future__ import annotations

import json
import os

from nooch_village.orphan_report import find_orphans


def test_vindt_wees_niet_geregistreerd(tmp_path):
    dd = tmp_path
    (dd / "attachments" / "pid1").mkdir(parents=True)
    (dd / "attachments" / "pid1" / "abc_geregistreerd.pdf").write_bytes(b"x")   # heeft entry
    (dd / "attachments" / "pid1" / "def_wees.docx").write_bytes(b"y" * 100)      # GEEN entry
    projects = {"pid1": {"id": "pid1", "attachments": [
        {"kind": "file", "stored": "attachments/pid1/abc_geregistreerd.pdf", "name": "x.pdf"},
        {"kind": "link", "url": "http://ergens"},                               # link telt niet mee
    ]}}
    (dd / "projects.json").write_text(json.dumps(projects))

    orphans, n_reg = find_orphans(str(dd))
    assert n_reg == 1
    assert len(orphans) == 1
    o = orphans[0]
    assert o["name"] == "def_wees.docx" and o["pid"] == "pid1" and o["size"] == 100
    # niets gewijzigd op schijf (read-only)
    assert (dd / "attachments" / "pid1" / "def_wees.docx").exists()


def test_geen_wezen_als_alles_geregistreerd(tmp_path):
    dd = tmp_path
    (dd / "attachments" / "p").mkdir(parents=True)
    (dd / "attachments" / "p" / "a.pdf").write_bytes(b"x")
    (dd / "projects.json").write_text(json.dumps(
        {"p": {"id": "p", "attachments": [{"kind": "file", "stored": "attachments/p/a.pdf", "name": "a"}]}}))
    orphans, n_reg = find_orphans(str(dd))
    assert orphans == [] and n_reg == 1
