"""Kennislaag brok 1: de SOORT op het Insight-model + de classifier.
Soort verandert nooit; None = onbeslist → mens-review. Definities → Lexicon (apart gemarkeerd)."""
from __future__ import annotations

from nooch_village.insight import Insight, ClaimKind, EvidenceType, GroundingStatus
from nooch_village.claim_classify import classify_kind, looks_like_definition


def test_kind_optioneel_en_backward_compatible():
    # bestaand kaartje zonder kind laadt prima (None = onbeslist)
    n = Insight(id="x", claim="iets", source="s")
    assert n.kind is None
    # kind kan gezet worden
    n2 = Insight(id="y", claim="iets", source="s", kind=ClaimKind.BEVINDING)
    assert n2.kind == ClaimKind.BEVINDING
    # serialiseert en herlaadt
    assert Insight(**n2.model_dump(mode="json")).kind == ClaimKind.BEVINDING


def test_classify_heldere_gevallen():
    assert classify_kind("De EU Green Claims Directive verplicht onderbouwing") == ClaimKind.KADER
    assert classify_kind("Natuurrubber degradeert 15,6% in 236 dagen",
                         evidence_type="measured") == ClaimKind.BEVINDING
    assert classify_kind("Zoekvolume rond microplastics stijgt dit kwartaal") == ClaimKind.SIGNAAL
    assert classify_kind("Onze schoen is composteerbaar",
                         evidence_type="claimed") == ClaimKind.STANDPUNT


def test_evidence_type_hint_beslist_als_tekst_zwijgt():
    # neutrale tekst, maar measured → bevinding
    assert classify_kind("hennepveters", evidence_type="measured") == ClaimKind.BEVINDING
    # reported is bewust GEEN soort → val terug op tekst; neutrale tekst → onbeslist
    assert classify_kind("iets neutraals", evidence_type="reported") is None


def test_kader_in_tekst_over_norm_is_niet_per_se_kader():
    # 'voldoet aan EN13432' gaat niet over de norm zelf maar over een claim eronder
    k = classify_kind("Onze lijm voldoet aan EN13432", evidence_type="claimed")
    assert k == ClaimKind.STANDPUNT


def test_onbeslist_bij_twijfel():
    # normatief/leeg → None (mens beslist), geen gokje
    assert classify_kind("Een merk hoort eerlijk te zijn") in (ClaimKind.STANDPUNT, None)
    assert classify_kind("") is None


def test_definitie_herkend_voor_lexicon():
    assert looks_like_definition("Vegan materiaal betekent de afwezigheid van dierlijke grondstoffen")
    assert not looks_like_definition("Natuurrubber degradeert traag")
