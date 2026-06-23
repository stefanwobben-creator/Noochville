"""Tests voor de KE-aanjager: per-taal-batches in de human inbox. Thread-vrij, geen credits."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox
from nooch_village.keyword_aanjager import propose_locale_batches, DEFAULT_LOCALES


def _inbox(tmp_path):
    return HumanInbox(str(tmp_path / "inbox.json"))


def test_default_zet_en_en_nl_batch(tmp_path):
    inbox = _inbox(tmp_path)
    queued = propose_locale_batches(inbox)
    locales = {q["locale"] for q in queued}
    assert locales == set(DEFAULT_LOCALES)
    items = [i for i in inbox.all() if i["type"] == "keyword_batch"]
    assert len(items) == len(DEFAULT_LOCALES)


def test_geo_per_taal_klopt(tmp_path):
    inbox = _inbox(tmp_path)
    queued = propose_locale_batches(inbox, ["en", "nl"])
    geo = {q["locale"]: q["geo"] for q in queued}
    assert geo["en"] == "gb"          # Engels in gb
    assert geo["nl"] == "nl"


def test_inbox_item_draagt_locale_en_geo(tmp_path):
    inbox = _inbox(tmp_path)
    propose_locale_batches(inbox, ["en"])
    item = [i for i in inbox.all() if i["type"] == "keyword_batch"][0]
    assert item["context"]["locale"] == "en"
    assert item["context"]["geo"]    == "gb"


def test_tweede_keer_dedupt(tmp_path):
    inbox = _inbox(tmp_path)
    propose_locale_batches(inbox, ["en", "nl"])
    propose_locale_batches(inbox, ["en", "nl"])      # zelfde batches, nog pending
    items = [i for i in inbox.all() if i["type"] == "keyword_batch"]
    assert len(items) == 2                            # geen duplicaten


def test_eigen_locale_lijst_en_tier(tmp_path):
    inbox = _inbox(tmp_path)
    queued = propose_locale_batches(inbox, ["nl"], tier="longtail")
    assert len(queued) == 1
    assert queued[0]["locale"] == "nl"
    item = [i for i in inbox.all() if i["type"] == "keyword_batch"][0]
    assert item["context"]["tier"] == "longtail"
