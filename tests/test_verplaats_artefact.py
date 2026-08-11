"""Verplaats-artefact-script — identiteit en historie moeten de verhuizing overleven.

Waarom deze tests bestaan: archiveren-plus-opnieuw-aanmaken is de makkelijke weg en verliest
stilzwijgend de id en de versiehistorie. Dit script belooft het tegenovergestelde. Deze tests
bewaken die belofte, plus de fail-closed domeincheck (een policy hoort nooit bij een eigenaar die
het domein niet bezit).
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

from nooch_village.attachments import AttachmentStore
from nooch_village.governance import Records

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "verplaats_artefact.py")


def _laad_script():
    spec = importlib.util.spec_from_file_location("verplaats_artefact", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


va = _laad_script()


def _records(tmp_path, nooch_domeinen=("Tone of voice",)):
    def rec(rid, naam, parent, rtype, domeinen=()):
        return {"id": rid, "type": rtype, "parent": parent,
                "definition": {"name": naam, "purpose": "", "domains": list(domeinen),
                               "accountabilities": []},
                "members": [], "version": 1}
    pad = os.path.join(str(tmp_path), "governance_records.json")
    json.dump({
        "nooch": rec("nooch", "Nooch", None, "circle", nooch_domeinen),
        "nooch__email": rec("nooch__email", "Community and Email", "nooch", "role",
                            ["Tone of voice"]),
    }, open(pad, "w"))
    return Records(pad)


@pytest.fixture()
def omgeving(tmp_path):
    att_pad = os.path.join(str(tmp_path), "attachments.json")
    att = AttachmentStore(att_pad)
    pol = att.add("nooch__email", "policy", title="Tone of Voice", body="Eerste tekst.",
                  domain="Tone of voice", actor_id="stefan", actor_type="person")
    att.update(pol.id, body="Tweede tekst.", actor_id="stefan", actor_type="person")
    return att_pad, pol.id, tmp_path


def test_droogloop_raakt_niets_aan(omgeving):
    att_pad, pid, tmp = omgeving
    voor = json.load(open(att_pad))
    uit = va.verplaats(att_pad, pid, "nooch", _records(tmp))
    assert uit["toegepast"] is False
    assert uit["naar"] == "nooch"
    assert json.load(open(att_pad)) == voor


def test_verhuizing_behoudt_id_en_historie(omgeving):
    att_pad, pid, tmp = omgeving
    uit = va.verplaats(att_pad, pid, "nooch", _records(tmp), actor_id="stefan",
                       governance_ref="GOV-2026-08", doen=True)
    assert uit["toegepast"] is True
    d = json.load(open(att_pad))[pid]
    assert d["anchor"] == "nooch"
    assert d["body"] == "Tweede tekst."
    # versie 1 (aangemaakt) + 2 (bewerkt) + 3 (verplaatst) — niets weggegooid
    assert [v["version_nr"] for v in d["versions"]] == [1, 2, 3]
    assert "verplaatst van nooch__email naar nooch" in d["versions"][-1]["change_note"]
    assert d["versions"][-1]["governance_ref"] == "GOV-2026-08"
    assert d["versions"][0]["body_snapshot"] == "Eerste tekst."


def test_na_verhuizing_erft_de_oude_eigenaar_hem(omgeving):
    """De policy hangt nu bij de cirkel, dus de rol ziet hem als geerfd in plaats van eigen."""
    from nooch_village import artefacts
    att_pad, pid, tmp = omgeving
    records = _records(tmp)
    va.verplaats(att_pad, pid, "nooch", records, doen=True)
    oi = artefacts.own_and_inherited("nooch__email", "policy", records,
                                     AttachmentStore(att_pad))
    assert [a.id for a in oi["own"]] == []
    assert [a["artefact"].id for a in oi["inherited"]] == [pid]


def test_doel_zonder_domein_wordt_geweigerd(omgeving):
    att_pad, pid, tmp = omgeving
    with pytest.raises(va.VerplaatsFout) as e:
        va.verplaats(att_pad, pid, "nooch", _records(tmp, nooch_domeinen=("Money",)), doen=True)
    assert "Tone of voice" in str(e.value)
    assert json.load(open(att_pad))[pid]["anchor"] == "nooch__email"   # niets gewijzigd


def test_onbekend_doel_en_onbekend_artefact(omgeving):
    att_pad, pid, tmp = omgeving
    with pytest.raises(va.VerplaatsFout):
        va.verplaats(att_pad, pid, "bestaat_niet", _records(tmp), doen=True)
    with pytest.raises(va.VerplaatsFout):
        va.verplaats(att_pad, "GEEN-001", "nooch", _records(tmp), doen=True)


def test_tweede_keer_verplaatsen_is_een_nette_weigering(omgeving):
    att_pad, pid, tmp = omgeving
    records = _records(tmp)
    va.verplaats(att_pad, pid, "nooch", records, doen=True)
    with pytest.raises(va.VerplaatsFout) as e:
        va.verplaats(att_pad, pid, "nooch", records, doen=True)
    assert "hangt al" in str(e.value)


def test_changelog_krijgt_een_regel(omgeving):
    att_pad, pid, tmp = omgeving
    va.verplaats(att_pad, pid, "nooch", _records(tmp), actor_id="stefan", doen=True)
    regels = open(os.path.join(str(tmp), "artefact_changelog.jsonl"), encoding="utf-8").readlines()
    entry = json.loads(regels[-1])
    assert entry["artefact_id"] == pid
    assert entry["anchor"] == "nooch"
