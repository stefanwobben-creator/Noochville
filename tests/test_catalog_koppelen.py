"""Scope 4 — catalogus-koppelscherm: bronnen uit de skills, koppel-status, publiceren volgens het
scope-3-schema, wizard-zichtbaarheid en anchor-lead-autorisatie."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.catalog_koppelen import render_catalogus_koppelen, catalog_sources

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_bronnen_en_raw_velden_uit_skills():
    srcs = {s: f for s, _l, f in catalog_sources()}
    assert "visitors" in srcs["plausible"]
    assert "pairs_sold" in srcs["shopify"]
    assert "impressions" in srcs["gsc"]


def test_geseede_velden_tonen_als_gekoppeld_geen_inline_style(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    html = render_catalogus_koppelen(st, source="plausible")
    assert "cl-filter" in html                               # bron-picker (hergebruikt patroon)
    assert html.count("in catalogus") == 3                  # visitors/pageviews/visit_duration al geseed
    assert "Publiceer naar catalogus" not in html           # niets ongekoppeld → geen formulier
    assert "style=" not in html                             # geen inline styles (UI-regel)


def test_ongekoppeld_veld_toont_formulier(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    # nieuw ruw veld dat nog niet in de catalogus staat
    html = render_catalogus_koppelen(st, source="shopify")
    assert html.count("in catalogus") == 4                  # de vier geseede shopify-velden
    # simuleer een ongekoppeld veld via een niet-geseed veld op een verse def-store
    st.defs._d.clear(); st.defs._save()                     # leeg → alle velden ongekoppeld
    html2 = render_catalogus_koppelen(st, source="shopify")
    assert html2.count("Publiceer naar catalogus") == 4 and "in catalogus" not in html2


def test_publiceren_maakt_item_volgens_scope3(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "catalog_publish", {
        "source": ["shopify"], "veld": ["cart_abandon_rate"], "naam": ["Winkelwagen-verlaat"],
        "categorie": ["Verkoop"], "aard": ["moment"], "unit": ["%"],
        "definition": ["Aandeel sessies dat de winkelwagen verlaat."], "next": ["/"]}, username="guest")
    cur = cockpit2._Stores(dd).defs.current(cockpit2._Stores(dd).defs.find("Winkelwagen-verlaat", "shopify")["id"])
    assert cur["veld"] == "cart_abandon_rate" and cur["categorie"] == "Verkoop"
    assert cur["aard"] == "moment" and cur["aggregatie"] == "" and cur["formule"] is False
    assert cur["unit"] == "%" and cur["source"] == "shopify"
    # niet dubbel publiceren
    _, msg = cockpit2.dispatch(dd, "catalog_publish", {
        "source": ["shopify"], "veld": ["cart_abandon_rate"], "naam": ["X"],
        "categorie": ["Verkoop"], "aard": ["moment"], "next": ["/"]}, username="guest")
    assert "al in de catalogus" in msg


def test_publiceren_verplicht_naam_categorie_aard(tmp_path):
    dd = _dd(tmp_path)
    _, msg = cockpit2.dispatch(dd, "catalog_publish", {
        "source": ["shopify"], "veld": ["x"], "naam": [""], "categorie": [""], "aard": [""],
        "next": ["/"]}, username="guest")
    assert "verplicht" in msg


def test_ongepubliceerd_veld_onzichtbaar_in_wizard_gepubliceerd_wel(tmp_path):
    dd = _dd(tmp_path)
    before = cockpit2.render_kpi_composer(cockpit2._Stores(dd), C, csrf_token="t")
    assert "Winkelwagen-verlaat" not in before
    cockpit2.dispatch(dd, "catalog_publish", {
        "source": ["shopify"], "veld": ["cart_abandon_rate"], "naam": ["Winkelwagen-verlaat"],
        "categorie": ["Verkoop"], "aard": ["moment"], "next": ["/"]}, username="guest")
    after = cockpit2.render_kpi_composer(cockpit2._Stores(dd), C, csrf_token="t")
    assert "Winkelwagen-verlaat" in after


def test_authz_niet_anchor_lead_geweigerd(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Iemand", "iemand@x.nl")                  # ingelogd, maar geen anchor-lead
    _, msg = cockpit2.dispatch(dd, "catalog_publish", {
        "source": ["shopify"], "veld": ["y"], "naam": ["N"], "categorie": ["Verkoop"],
        "aard": ["moment"], "next": ["/"]}, username="iemand@x.nl")
    assert "Geen toegang" in msg
