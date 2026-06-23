"""Tests voor de ngram year_end-cap (verwijderd). Thread-vrij, netwerk gemockt.

De zelf-opgelegde 2019-cap is weg: standaard vragen we op tot het huidige jaar,
en het corpus bepaalt waar de data echt ophoudt. Een expliciete override blijft werken.
"""
from __future__ import annotations

import datetime
from unittest.mock import patch

from nooch_village.skills_impl.ngram import NgramCultureSkill
import nooch_village.skills_impl.ngram as ng


def _run(payload):
    skill = NgramCultureSkill()
    with patch("nooch_village.skills_impl.ngram._fetch_ngram", return_value=[]) as mock, \
         patch("nooch_village.skills_impl.ngram.time.sleep"):
        skill.run(payload, context=None)
    return mock


def test_default_year_end_is_huidig_jaar():
    mock = _run({"terms": ["vegan"]})
    # _fetch_ngram(batch, corpus, year_start, year_end, smoothing) → year_end = arg index 3
    assert mock.call_args[0][3] == datetime.date.today().year


def test_year_end_override_blijft_werken():
    mock = _run({"terms": ["vegan"], "year_end": 2010})
    assert mock.call_args[0][3] == 2010


def test_geen_hardgecodeerde_2019_cap_meer():
    assert not hasattr(ng, "_YEAR_END")
