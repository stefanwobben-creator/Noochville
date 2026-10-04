"""Een feit met een GETAL: de vorm waarin CO2e, water en kostprijs op een wiki-pagina staan, en die
het BOM-scherm straks optelt (BOM-tool, stuk 2 — 1 oktober 2026).

Het getal is een veld OP het feit en deelt dus diens grond: één feit is één bewering. De grootheden
en hun vaste eenheid staan op één plek (`wiki.GROOTHEDEN`); een vrije eenheid zou een getal opleveren
waarmee niet te rekenen valt.
"""
from __future__ import annotations

from nooch_village import artefacts, cockpit2, wiki, wiki_seed
from nooch_village.data_bom import NOOCH_SCHOEN_BOM
from nooch_village.views.wiki import render_pagina

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _add(dd, aid, **velden):
    form = {"aid": [aid], "next": ["/"], **{k: [v] for k, v in velden.items()}}
    return cockpit2.dispatch(dd, "pagina_feit_add", form, username="guest")[1]


# ── het model ───────────────────────────────────────────────────────────────

def test_een_waarde_is_fail_closed():
    assert wiki.maak_waarde("co2e_per_kg", "2,4") == {"grootheid": "co2e_per_kg", "getal": 2.4}
    assert wiki.maak_waarde("co2e_per_kg", "0") == {"grootheid": "co2e_per_kg", "getal": 0.0}
    for grootheid, getal in (("onbekend", "1"), ("co2e_per_kg", ""), ("co2e_per_kg", "abc"),
                             ("co2e_per_kg", "-1"), ("water_per_kg", "nan"), ("water_per_kg", "inf")):
        assert wiki.maak_waarde(grootheid, getal) is None, (grootheid, getal)


def test_een_waarde_wordt_bij_het_lezen_opnieuw_gekeurd():
    """Wat in de opslag staat is niet per se door `maak_waarde` gegaan."""
    assert wiki.waarde({"tekst": "x", "waarde": {"grootheid": "co2e_per_kg", "getal": -3}}) is None
    assert wiki.waarde({"tekst": "x", "waarde": "2.4"}) is None
    assert wiki.waarde({"tekst": "x"}) is None


def test_de_tekst_van_een_waarde():
    assert wiki.waarde_tekst(wiki.maak_waarde("co2e_per_kg", "2.4")) == "2.4 kg CO2e/kg"
    assert wiki.waarde_tekst(wiki.maak_waarde("water_per_kg", "180")) == "180 L/kg"
    assert wiki.waarde_tekst(wiki.maak_waarde("prijs_per_kg", "1234567")) == "1234567 EUR/kg"


# ── de route ────────────────────────────────────────────────────────────────

def test_een_feit_met_waarde_wordt_opgeslagen(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="Helios 200")
    msg = _add(dd, a.id, tekst="CO2e volgens de TDS", soort="bron", url="https://lta.example/tds.pdf",
               grootheid="co2e_per_kg", getal="2,4")
    assert "fact added" in msg
    f = wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]
    assert f["waarde"] == {"grootheid": "co2e_per_kg", "getal": 2.4}
    assert f["grond"]["url"] == "https://lta.example/tds.pdf"       # het getal deelt de grond


def test_een_feit_zonder_waarde_blijft_zoals_het_was(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p")
    assert "fact added" in _add(dd, a.id, tekst="Gewoon een feit", grootheid="", getal="")
    assert "waarde" not in wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]


def test_half_ingevuld_is_een_fout_en_geen_stil_feit(tmp_path):
    """Een feit dat er staat maar in het BOM-scherm nooit meetelt, valt niemand op."""
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p")
    for velden in ({"grootheid": "co2e_per_kg", "getal": ""},
                   {"grootheid": "", "getal": "2.4"},
                   {"grootheid": "co2e_per_kg", "getal": "veel"}):
        msg = _add(dd, a.id, tekst="iets", **velden)
        assert "needs both" in msg, velden
    assert wiki.feiten(cockpit2._Stores(dd).att.get(a.id)) == []


# ── wat je ziet ─────────────────────────────────────────────────────────────

def test_de_pagina_toont_het_getal(tmp_path):
    # Het "+ Add fact"-formulier met zijn grootheden-keuzelijst is weg (3 oktober 2026); een getal
    # komt nu binnen via de `Value:`-regel van Bulk Import — zie tests/test_bulk_import_facts.py.
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Alice", "alice@nooch.earth")
    st.assign.assign(OWNER, "person", st.people.by_email("alice@nooch.earth").id)
    a = st.att.add(OWNER, "note", title="Helios 200")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit(
        "Water volgens de TDS", soort="bron", url="https://x", waarde=wiki.maak_waarde("water_per_kg", "180"))]})
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="tok", username="alice@nooch.earth")
    assert "Water per kg: <strong>180 L/kg</strong>" in html
    assert "value='pagina_feit_add'" not in html                   # het oude formulier is weg


def test_de_context_van_een_ai_vervuller_krijgt_het_getal_mee():
    class A:
        kind, id, meta = "note", "NOTE-1", {"feiten": [
            wiki.maak_feit("CO2", waarde=wiki.maak_waarde("co2e_per_kg", "2.4"))]}
    assert artefacts._feiten_van(A(), None, None)[0]["waarde"] == "2.4 kg CO2e/kg"


# ── het zaad ────────────────────────────────────────────────────────────────

def test_een_nieuwe_materiaalpagina_heeft_de_plek_voor_co2_en_water():
    paginas = wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM)
    assert paginas and all("## CO2 & Water" in p["body"] for p in paginas)
    # Geen bewering dat het getal ontbreekt: die zin blijft staan als het feit er komt, en liegt dan.
    assert not any("not yet" in p["body"].split("## CO2 & Water")[1].split("##")[0].lower()
                   for p in paginas)


def test_een_nieuwe_leverancierpagina_heeft_de_plek_voor_de_prijs(monkeypatch):
    monkeypatch.setattr(wiki_seed.cert_register, "certs_uit_kroniek",
                        lambda _l: [{"leverancier": "LTA S.R.L.", "materiaal": "Helios 200"}])
    [p] = wiki_seed.leverancier_paginas(object())
    assert "## Price agreement" in p["body"]
    assert "## CO2 & Water" not in p["body"]           # prijs bij de leverancier, CO2 bij het materiaal
