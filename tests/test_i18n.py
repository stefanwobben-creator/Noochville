"""Vertaallaag (seam): t() geeft EN (de UI-taal sinds i18n fase 1), valt terug op de sleutel bij
ontbreken, interpoleert, en de en→nl-fallback werkt nog voor een sleutel zonder `en`."""
from __future__ import annotations

from nooch_village import i18n
from nooch_village.i18n import t, set_lang


def test_t_geeft_en():
    assert t("catalogus.koppelen.publiceer") == "Publish to catalogue"
    assert i18n.lang() == "en"


def test_ontbrekende_sleutel_geeft_sleutel_terug():
    assert t("bestaat.niet.xyz") == "bestaat.niet.xyz"   # zichtbaar, nooit een crash


def test_interpolatie_via_format():
    i18n._CATALOG["_test.interp"] = {"nl": "aantal: {n}", "en": "count: {n}"}
    try:
        assert t("_test.interp", n=5) == "count: 5"
    finally:
        i18n._CATALOG.pop("_test.interp", None)


def test_en_valt_terug_op_nl():
    i18n._CATALOG["_test.nl_only"] = {"nl": "alleen Nederlands"}
    try:
        assert t("_test.nl_only") == "alleen Nederlands"   # en ontbreekt → nl-fallback
    finally:
        i18n._CATALOG.pop("_test.nl_only", None)


def test_nl_blijft_beschikbaar():
    set_lang("nl")
    try:
        assert t("catalogus.koppelen.publiceer") == "Publiceer naar catalogus"
    finally:
        set_lang("en")


def test_elke_sleutel_heeft_en():
    # fase 1 is af: er mag geen sleutel meer zonder `en` in de catalogus staan.
    assert [k for k, v in i18n._CATALOG.items() if not v.get("en")] == []


def test_seam_toegepast_op_verse_views():
    assert t("wizard.modus.formule") == "Create formula"
    assert t("dashboard.vergelijk") == "Compare with previous period"
    assert t("dashboard.geen_live_data") == "no live data"
