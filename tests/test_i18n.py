"""Vertaallaag (seam): t() geeft NL, valt terug op de sleutel bij ontbreken, interpoleert, en de
en→nl-fallback werkt. De seam is transparant voor NL, dus de bestaande view-tests blijven groen."""
from __future__ import annotations

from nooch_village import i18n
from nooch_village.i18n import t, set_lang


def test_t_geeft_nl():
    assert t("catalogus.koppelen.publiceer") == "Publiceer naar catalogus"
    assert i18n.lang() == "nl"


def test_ontbrekende_sleutel_geeft_sleutel_terug():
    assert t("bestaat.niet.xyz") == "bestaat.niet.xyz"   # zichtbaar, nooit een crash


def test_interpolatie_via_format():
    i18n._CATALOG["_test.interp"] = {"nl": "aantal: {n}"}
    try:
        assert t("_test.interp", n=5) == "aantal: 5"
    finally:
        i18n._CATALOG.pop("_test.interp", None)


def test_en_valt_terug_op_nl():
    set_lang("en")
    try:
        assert t("catalogus.koppelen.titel") == "Link catalogue"                # en aanwezig
        assert t("catalogus.koppelen.publiceer") == "Publiceer naar catalogus"  # en ontbreekt → nl
    finally:
        set_lang("nl")


def test_seam_toegepast_op_verse_views():
    # de metrics-scopes van vandaag lopen nu via t() — steekproef op sleutel = huidige NL-tekst
    assert t("wizard.modus.formule") == "Formule maken"
    assert t("dashboard.vergelijk") == "Vergelijk met vorige periode"
    assert t("dashboard.geen_live_data") == "geen live data"
