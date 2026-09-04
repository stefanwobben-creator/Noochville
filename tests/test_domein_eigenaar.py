"""Wie bezit dit onderwerp? Een domein is een verklaring, geen gevolgtrekking uit tekst.

WAAROM DIT ER IS (4 sep 2026): de radar-exit moest landen op "de rol die materiaal bezit", en dat
mocht geen rol-id in code zijn — rolvervulling én rol-eigenaarschap veranderen, en dan wijst een
bevroren id stil naar de verkeerde plek. De secretary-classificatie was de eerste kandidaat, maar
die matcht accountability-TEKST via een model: subtieler dan een hardcode, even broos.

Een domein staat in het governance-record. Het verschuift met een amendement, zonder codewijziging.
"""
from __future__ import annotations

import logging
import types

from nooch_village import triage_rol


def _st(*rollen):
    class _R:
        @staticmethod
        def all():
            return list(rollen)
    return types.SimpleNamespace(records=_R())


def _rol(rid, domeinen, *, slaapt=False, archived=False):
    return types.SimpleNamespace(
        id=rid, slaapt=slaapt, archived=archived,
        definition=types.SimpleNamespace(domains=domeinen))


def test_een_houder_is_de_eigenaar():
    st = _st(_rol("creator_of_shoes", ["Materials"]), _rol("librarian", ["bibliotheek"]))
    uit = triage_rol.domein_eigenaar(st, "Materials")
    assert uit["rol"] == "creator_of_shoes" and "houdt het domein" in uit["grond"]


def test_hoofdletters_maken_niet_uit():
    """De governance-tekst is mensenwerk; 'materials' en 'Materials' zijn hetzelfde domein."""
    st = _st(_rol("creator_of_shoes", ["materials"]))
    assert triage_rol.domein_eigenaar(st, "  MATERIALS ")["rol"] == "creator_of_shoes"


def test_geen_domein_geconfigureerd_is_STIL(caplog):
    """Niets mis: de config zegt niets over eigenaarschap, de secretary neemt het over."""
    with caplog.at_level(logging.WARNING):
        uit = triage_rol.domein_eigenaar(_st(_rol("x", [])), "")
    assert uit["rol"] == "" and "geen eigenaar_domein" in uit["grond"]
    assert caplog.text == ""                                  # geen enkele waarschuwing


def test_een_geconfigureerd_domein_dat_NIEMAND_houdt_is_LUID(caplog):
    """DE TOEVOEGING VAN STEFAN. Zonder deze regel routeert de radar stil voor altijd naar de
    founder: een signaal dat bestaat maar niet gelezen wordt. Een typefout in feeds.json of een
    governance-akte dat nooit gezet is, mag zich niet als gewone terugval verstoppen."""
    with caplog.at_level(logging.WARNING):
        uit = triage_rol.domein_eigenaar(_st(_rol("x", ["iets anders"])), "Materials")
    assert uit["rol"] == ""
    assert "CONFIG-FOUT" in caplog.text and "Materials" in caplog.text
    assert "geen enkele wakkere rol" in caplog.text.lower() or "GEEN enkele" in caplog.text


def test_twee_houders_is_een_governance_fout_en_dus_LUID(caplog):
    """Ertussen kiezen zou de fout verbergen achter een gok."""
    st = _st(_rol("a", ["Materials"]), _rol("b", ["Materials"]))
    with caplog.at_level(logging.WARNING):
        uit = triage_rol.domein_eigenaar(st, "Materials")
    assert uit["rol"] == ""
    assert "GOVERNANCE-FOUT" in caplog.text


def test_een_slapende_of_gearchiveerde_houder_telt_niet(caplog):
    """Een slapende rol draagt geen capaciteit; hem meetellen zou een echt gat verbergen — zelfde
    regel als bij de verweesde pulse-skills (#426)."""
    st = _st(_rol("slaper", ["Materials"], slaapt=True),
             _rol("weg", ["Materials"], archived=True))
    with caplog.at_level(logging.WARNING):
        assert triage_rol.domein_eigenaar(st, "Materials")["rol"] == ""
    assert "CONFIG-FOUT" in caplog.text                       # want niemand LEVENDS houdt hem


def test_het_domein_gaat_VOOR_de_classificatie(monkeypatch):
    """Een verklaring gaat vóór een gevolgtrekking: staat de eigenaar in governance, dan hoeft er
    geen model aan te pas te komen."""
    geroepen = []
    monkeypatch.setattr(triage_rol, "classificeer",
                        lambda *a, **k: geroepen.append(1) or {"rol": "iemand_anders", "grond": "x"})
    import nooch_village.cockpit2 as c
    monkeypatch.setattr(c, "mens_vervullers", lambda st, rol: ["lotte"])
    st = _st(_rol("creator_of_shoes", ["Materials"]))
    uit = triage_rol.menselijke_eigenaar(st, "sample aanvragen", domein="Materials")
    assert uit["rol"] == "creator_of_shoes" and uit["mens"] == "lotte"
    assert geroepen == []                                     # het model is niet aangeroepen


def test_zonder_eigenaar_valt_hij_terug_op_de_secretary(monkeypatch):
    monkeypatch.setattr(triage_rol, "classificeer",
                        lambda *a, **k: {"rol": "harry_hemp", "grond": "gematcht"})
    import nooch_village.cockpit2 as c
    monkeypatch.setattr(c, "mens_vervullers", lambda st, rol: ["iemand"])
    st = _st(_rol("x", []))
    uit = triage_rol.menselijke_eigenaar(st, "sample", domein="Materials")
    assert uit["rol"] == "harry_hemp"
    # de reden van de terugval reist mee, zodat een droge run leesbaar blijft
    assert "wordt door niemand gehouden" in uit["waarom"] and "gematcht" in uit["waarom"]


def test_de_feed_draagt_de_domeinnaam_en_niet_de_code():
    from nooch_village.radar_store import _DEFAULT_FEEDS
    mat = [f for f in _DEFAULT_FEEDS if f.get("label") == "Material Innovation"][0]
    assert mat["eigenaar_domein"] == "Materials"
    assert mat["role"] == "harry_hemp"        # wie kijkt ≠ wie bezit
