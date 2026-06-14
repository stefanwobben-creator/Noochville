"""Tests voor Lexicon: symmetrie, word_for, status en filtering."""
from __future__ import annotations
import pytest
from nooch_village.lexicon import Lexicon


@pytest.fixture
def lex(tmp_path):
    l = Lexicon(str(tmp_path / "lexicon.json"))
    l.add_concept("consumer_frame", {"nl": "consument", "en": "consumer"},
                  status="avoid", rationale="passief frame")
    l.add_concept("burger_frame",   {"nl": "burger",    "en": "citizen"},
                  status="avoid", rationale="burgerkader")
    l.add_concept("vegan",          {"nl": "veganistisch", "en": "vegan"},
                  status="approved", rationale="kernmissie")
    l.add_concept("plastic_free",   {"nl": "plasticvrij",  "en": "plastic-free"},
                  status="approved", rationale="harde policy")
    return l


# ── symmetrie ─────────────────────────────────────────────────────────────────

class TestSymmetrie:
    def test_nl_avoid_betekent_en_avoid(self, lex):
        assert lex.status_for_word("consument", "nl") == "avoid"
        assert lex.status_for_word("consumer",  "en") == "avoid"

    def test_avoid_is_forbidden(self, lex):
        assert lex.is_forbidden("consument", "nl")
        assert lex.is_forbidden("consumer",  "en")

    def test_approved_concept_beide_talen(self, lex):
        assert lex.is_approved("veganistisch", "nl")
        assert lex.is_approved("vegan",        "en")

    def test_status_zonder_taalfilter(self, lex):
        # status_for_word zonder lang-parameter: vindt via beide talen
        assert lex.status_for_word("consument") == "avoid"
        assert lex.status_for_word("consumer")  == "avoid"


# ── word_for ──────────────────────────────────────────────────────────────────

class TestWordFor:
    def test_nl_woord_teruggeven(self, lex):
        assert lex.word_for("consumer_frame", "nl") == "consument"

    def test_en_woord_teruggeven(self, lex):
        assert lex.word_for("consumer_frame", "en") == "consumer"

    def test_ontbrekend_taalvak_geeft_none(self, lex):
        assert lex.word_for("consumer_frame", "de") is None

    def test_onbekend_concept_geeft_none(self, lex):
        assert lex.word_for("bestaat_niet", "nl") is None


# ── words_for_lang met status_filter ─────────────────────────────────────────

class TestWordsForLang:
    def test_alleen_approved_nl(self, lex):
        woorden = lex.words_for_lang("nl", status_filter="approved")
        assert "veganistisch" in woorden
        assert "plasticvrij"  in woorden
        assert "consument"    not in woorden
        assert "burger"       not in woorden

    def test_alleen_approved_en(self, lex):
        woorden = lex.words_for_lang("en", status_filter="approved")
        assert "vegan"         in woorden
        assert "plastic-free"  in woorden
        assert "consumer"      not in woorden

    def test_zonder_filter_geeft_alle_woorden(self, lex):
        woorden = lex.words_for_lang("nl")
        assert "consument"    in woorden
        assert "veganistisch" in woorden

    def test_ontbrekende_taal_geeft_lege_lijst(self, lex):
        assert lex.words_for_lang("de", status_filter="approved") == []


# ── concept_for_word / status_for_word ───────────────────────────────────────

class TestConceptLookup:
    def test_concept_voor_nl_woord(self, lex):
        assert lex.concept_for_word("consument", "nl") == "consumer_frame"

    def test_concept_voor_en_woord(self, lex):
        assert lex.concept_for_word("consumer", "en") == "consumer_frame"

    def test_onbekend_woord_geeft_none(self, lex):
        assert lex.concept_for_word("onbekend") is None

    def test_status_voor_approved_woord(self, lex):
        assert lex.status_for_word("vegan", "en") == "approved"


# ── seed is idempotent ────────────────────────────────────────────────────────

class TestSeed:
    def test_seed_overschrijft_niet(self, lex):
        lex.seed([{
            "concept_id": "vegan",
            "words": {"nl": "anders", "en": "anders"},
            "status": "forbidden",
        }])
        assert lex.word_for("vegan", "nl") == "veganistisch"  # ongewijzigd
        assert lex.status_for_word("vegan") == "approved"

    def test_seed_voegt_nieuw_toe(self, lex):
        lex.seed([{
            "concept_id": "nieuw",
            "words": {"nl": "nieuw woord"},
            "status": "approved",
        }])
        assert lex.word_for("nieuw", "nl") == "nieuw woord"


# ── add_words behoudt status ──────────────────────────────────────────────────

class TestAddWords:
    def test_add_words_behoudt_status(self, lex):
        lex.add_words("vegan", {"fr": "végane"})
        assert lex.status_for_word("végane", "fr") == "approved"

    def test_add_words_onbekend_concept(self, lex):
        assert lex.add_words("bestaat_niet", {"nl": "x"}) is False
