"""Facilitator-rolreview: per rol één verbetervoorstel als kans in de inbox (mens-gated),
gegrond in de referentiebank. Kernrollen/cirkels worden overgeslagen. Fail-closed zonder LLM."""
from __future__ import annotations

from nooch_village.governance import Records
from nooch_village.governance_examples import GovernanceExamples
from nooch_village.governance_review import (review_role, review_all_roles, _parse_review,
                                             review_role_teleology, teleology_review_all_roles,
                                             _parse_teleology, _ing_start)
from nooch_village.models import Record, RoleDefinition, RecordType


def test_parse_review():
    assert _parse_review("SUGGESTIE: Bewaken van X\nWAAROM: helderder") == {
        "suggestion": "Bewaken van X", "why": "helderder"}
    assert _parse_review("GEEN") is None
    assert _parse_review("") is None


def test_parse_review_volledige_meerregelige_suggestie():
    """Een voorstel als 'Vervang X door:\\n<nieuwe tekst>' mag NIET afkappen op 'door:'."""
    txt = ("SUGGESTIE: Vervang de accountability 'tijdgeest-signalen publiceren' door:\n"
           "Signaleren van culturele taalverschuivingen die de missie raken\n"
           "WAAROM: korter en in de -en-vorm")
    out = _parse_review(txt)
    assert "Signaleren van culturele taalverschuivingen" in out["suggestion"]
    assert out["suggestion"].endswith("raken")               # volledige zin, niet 'door:'
    assert out["why"].startswith("korter")


def test_review_role_failclosed():
    role = {"id": "scout", "purpose": "markt observeren", "accountabilities": ["markt kijken"]}
    assert review_role(role, "", llm_reason=lambda p: None) is None


def test_review_role_levert_suggestie():
    role = {"id": "scout", "purpose": "markt observeren", "accountabilities": ["markt kijken"]}
    out = review_role(role, "(voorbeelden)",
                      llm_reason=lambda p: "SUGGESTIE: Volgen van concurrenten en markttrends\n"
                                           "WAAROM: -en-vorm en concreter")
    assert out["suggestion"].startswith("Volgen van")


def _recs(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    r.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                 definition=RoleDefinition(purpose="Nooch"), source="seed"))
    r.put(Record(id="facilitator", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="proces"), source="seed"))
    r.put(Record(id="scout", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="markt observeren",
                                           accountabilities=["markt kijken"]), source="seed"))
    r.put(Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="woorden cureren"), source="seed"))
    return r




def _dorp(tmp_path):
    """Een dorp met een founder, zodat `signaal.terugval` een mens vindt om aan te leveren."""
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _berichten(dd):
    """De DM-teksten in het dorp. De voorstellen van de rolreview landen sinds 20 september 2026
    hier en niet meer als kans in de human inbox — zie de kop van `governance_review`."""
    from nooch_village import channels, signaal
    st = signaal._MiniStores(dd)
    return [e.get("text") or "" for k in st.channels.bestaande()
            if channels.soort_van(k) == channels.DM for e in st.channels.trail(k)]


def test_review_all_roles_bericht_de_founder_en_skipt_kernrollen(tmp_path):
    recs = _recs(tmp_path)
    ge = GovernanceExamples(str(tmp_path / "ge.json"))   # leeg → grounding fail-closed, prima
    dd = _dorp(tmp_path)
    res = review_all_roles(recs, ge, dd,
                           llm_reason=lambda p: "SUGGESTIE: Aanscherpen van dit aandachtsgebied\n"
                                                "WAAROM: helderder")
    # facilitator (kernrol) + wortelcirkel overgeslagen; scout + librarian gereviewd
    assert res["reviewed"] == 2 and res["proposed"] == 2
    msgs = _berichten(dd)
    assert len(msgs) == 2
    assert any("scout" in m for m in msgs)
    assert not any("facilitator" in m for m in msgs)              # kernrol niet gereviewd
    assert all("waarom: helderder" in m for m in msgs)            # de onderbouwing reist mee


def test_review_all_roles_failclosed_geen_voorstellen(tmp_path):
    recs = _recs(tmp_path)
    ge = GovernanceExamples(str(tmp_path / "ge.json"))
    dd = _dorp(tmp_path)
    res = review_all_roles(recs, ge, dd, llm_reason=lambda p: None)
    assert res["reviewed"] == 2 and res["proposed"] == 0
    assert _berichten(dd) == []


# ── Teleologie-review (EN, B1, -ing) ────────────────────────────────────────────

_TELE_OK = ("PURPOSE: Guarding the market awareness of the village\n"
            "ACCOUNTABILITIES:\n"
            "- Watching competitor movements closely\n"
            "- Reporting emerging trends every week\n"
            "WAAROM: purpose drukt het bestaansdoel uit; accountabilities in Engels, B1, -ing")


def test_ing_start():
    assert _ing_start("Watching competitors") and _ing_start("- Guarding X")
    assert not _ing_start("Watch the market") and not _ing_start("")


def test_parse_teleology():
    out = _parse_teleology(_TELE_OK)
    assert out["purpose"] == "Guarding the market awareness of the village"
    assert out["accountabilities"] == ["Watching competitor movements closely",
                                       "Reporting emerging trends every week"]
    assert out["why"].startswith("purpose")
    assert _parse_teleology("GEEN") is None and _parse_teleology("") is None


def test_review_role_teleology_failclosed_en_levert():
    role = {"id": "scout", "purpose": "markt observeren", "accountabilities": ["markt kijken"]}
    assert review_role_teleology(role, llm_reason=lambda p: None) is None
    out = review_role_teleology(role, llm_reason=lambda p: _TELE_OK)
    assert out["purpose"].startswith("Guarding") and len(out["accountabilities"]) == 2


def test_teleology_review_bericht_de_founder_en_skipt_kernrollen(tmp_path):
    recs = _recs(tmp_path)
    dd = _dorp(tmp_path)
    res = teleology_review_all_roles(recs, dd, llm_reason=lambda p: _TELE_OK)
    assert res["reviewed"] == 2 and res["proposed"] == 2 and res["incomplete"] == 0
    msgs = _berichten(dd)
    assert len(msgs) == 2
    assert any("Teleologie-review 'scout'" in m for m in msgs)
    assert not any("facilitator" in m for m in msgs)                 # kernrol overgeslagen
    scout = next(m for m in msgs if "scout" in m)
    # De VOLLEDIGE herschrijving moet in het bericht staan: zonder purpose én accountabilities
    # valt er niets te beoordelen, en dat is het enige wat dit voorstel nog doet.
    assert "Guarding" in scout and "Watching" in scout


# WAT HIER WEG IS (20 september 2026): `test_parse_teleology_opportunity` en
# `test_route_teleology_naar_roloverleg`. Die toetsten dat een teleologie-kans uit de human inbox
# terug te lezen was en als `amend_role` op de roloverleg-agenda belandde — een door een model
# geschreven purpose, in de wachtrij voor structuurwijziging, zonder mens ertussen. De route is weg;
# het voorstel komt nu als bericht bij de founder en wat ermee gebeurt begint bij hem.

def test_teleology_markeert_niet_ing(tmp_path):
    recs = _recs(tmp_path)
    dd = _dorp(tmp_path)
    bad = "PURPOSE: Market observation\nACCOUNTABILITIES:\n- Watch the market\nWAAROM: x"
    res = teleology_review_all_roles(recs, dd, llm_reason=lambda p: bad)
    assert res["incomplete"] == 2                                    # 'Watch' is niet -ing → gemarkeerd
    assert "Nog niet in -ing-vorm" in _berichten(dd)[0]
