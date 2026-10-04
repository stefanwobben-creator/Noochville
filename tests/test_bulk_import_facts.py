"""Bulk Import Facts op een wiki-pagina: de Import-knop deed niets (4 oktober 2026, NOTE-FACTOR-003).

De voorvertoning parste goed ("1 fact(s) ready"), maar de klik bereikte de server nooit. Vier
dingen tegelijk, elk genoeg om het te breken:

  1. `zeg(...)` bestaat alleen binnen `uploadInBlok` — hier een ReferenceError, alleen zichtbaar in
     de console; op het scherm gebeurde niets;
  2. het veld heette `csrf_token`, de pagina heeft `csrf` → "Form not found" (via die zeg-fout);
  3. de POST ging naar `/dispatch` — die route bestaat niet (404);
  4. multipart-`FormData`: een multipart-POST met een actie die geen upload is, stuurt de server
     stil door zonder iets te doen.

Het lege Quote-veld was het NIET: een feit zonder citaat is gewoon geldig (zie hieronder).
"""
from __future__ import annotations

import json
import pathlib

from nooch_village import cockpit2, wiki

IK = "b@t.nl"
ROL = "mother_earth__nooch__website_developer"
JS = (pathlib.Path(cockpit2.__file__).parent / "static" / "nooch.js").read_text()

NFW = {
    "Text": "MMG Polymer Company Limited (Phuket, Thailand) holds a valid FSC chain-of-custody "
            "certificate for natural rubber. The holder is not NFW.",
    "Type": "source",
    "Ref": "CERT CANDIDATE: FSC, licence FSC-C164605, certificate CU-COC-874791, valid until 22 Feb 2031",
    "Quote": "",
    "URL": "https://search.fsc.org (search on the licence code; I could not open a direct link)",
}


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Beheerder", IK)
    st.assign.assign(ROL, "person", mens.id)
    return dd, st.att.add(ROL, "note", title="NFW", body="Supplier page.").id


def _importeer(dd, aid, feiten):
    return cockpit2.dispatch(dd, "pagina_bulk_import_facts",
                             {"aid": [aid], "facts_json": [json.dumps(feiten)], "next": ["/"]},
                             username=IK)


def _feiten(dd, aid):
    return wiki.feiten(cockpit2._Stores(dd).att.get(aid))


# ══ de server ════════════════════════════════════════════════════════════════
def test_het_nfw_feit_uit_de_melding_komt_binnen(tmp_path):
    """Precies de invoer uit de melding, met een LEEG citaat: dat mag."""
    dd, aid = _dorp(tmp_path)
    _n, msg = _importeer(dd, aid, [NFW])
    assert not cockpit2.is_weigering(msg), msg
    f = _feiten(dd, aid)[0]
    assert f["grond"]["soort"] == "bron" and f["grond"]["citaat"] == ""
    assert f["grond"]["ref"].startswith("CERT CANDIDATE: FSC")


def test_alleen_het_adres_wordt_de_url(tmp_path):
    """"https://search.fsc.org (search on …)" — de toelichting erachter is geen adres."""
    dd, aid = _dorp(tmp_path)
    _importeer(dd, aid, [NFW])
    assert _feiten(dd, aid)[0]["grond"]["url"] == "https://search.fsc.org"


def test_geen_publieke_url_wordt_een_lege_url(tmp_path):
    """De feiten-prompt laat "NO PUBLIC URL — will show as source missing" invullen. Als URL
    opgeslagen zou dat feit juist NIET als "source missing" tonen — en dat is het wel."""
    dd, aid = _dorp(tmp_path)
    _importeer(dd, aid, [{**NFW, "URL": "NO PUBLIC URL — will show as source missing"}])
    f = _feiten(dd, aid)[0]
    assert f["grond"]["url"] == ""
    assert wiki.grond_status(f)["label"] == wiki.LABEL["geen_bron"] == "no source"


def test_een_afsluitend_leesteken_hoort_niet_bij_het_adres(tmp_path):
    dd, aid = _dorp(tmp_path)
    _importeer(dd, aid, [{**NFW, "URL": "https://example.org/cert.pdf."}])
    assert _feiten(dd, aid)[0]["grond"]["url"] == "https://example.org/cert.pdf"


# ══ de knop (de client-kant: hier zat de fout) ══════════════════════════════
def _bulk_js() -> str:
    a = JS.index("function bulkImportFacts(")
    return JS[a:JS.index("\n  }\n", a)]


def test_de_knop_post_naar_de_echte_route_met_de_echte_velden():
    js = _bulk_js()
    assert 'fetch("/action"' in js and "/dispatch" not in js.replace("`/dispatch`", "")
    assert 'data.set("csrf"' in js and "csrf_token" not in js.split("// Import")[-1].replace("`csrf_token`", "")
    assert "new URLSearchParams()" in js


def test_de_knop_roept_geen_functie_aan_die_hier_niet_bestaat():
    """`zeg` hoort bij `uploadInBlok`. In deze functie bestaat hij niet."""
    js = _bulk_js()
    assert "zeg(" not in js
    assert "function meld(" in js


# ══ Value: het getal dat /bom optelt (3 oktober 2026) ═══════════════════════
# "+ Add fact" was de enige weg voor een getal; met dat formulier weg moet Bulk Import de
# `Value:`-regel uit de feiten-prompts lezen, anders kan /bom nergens meer een cijfer vandaan halen.
def test_een_value_regel_wordt_een_getal_op_het_feit(tmp_path):
    dd, aid = _dorp(tmp_path)
    _n, msg = _importeer(dd, aid, [{**NFW, "Value": '"Cost price per kg" = 4,20'},
                                   {**NFW, "Value": "CO2e per kg (kg CO2e/kg) = 2.4"},
                                   {**NFW, "Value": "water_per_kg = 180"}])
    assert not cockpit2.is_weigering(msg) and "warning" not in msg, msg
    ws = [wiki.waarde(f) for f in _feiten(dd, aid)]
    assert ws == [{"grootheid": "prijs_per_kg", "getal": 4.2},
                  {"grootheid": "co2e_per_kg", "getal": 2.4},
                  {"grootheid": "water_per_kg", "getal": 180.0}]


def test_een_onleesbare_value_valt_niet_stil_weg(tmp_path):
    """Het feit komt binnen, zonder getal — en de melding zegt waarom."""
    dd, aid = _dorp(tmp_path)
    _n, msg = _importeer(dd, aid, [{**NFW, "Value": "Cost price per metre = 3.10"}])
    assert "1 facts imported" in msg and "without a number" in msg and "Cost price per kg" in msg, msg
    f = _feiten(dd, aid)[0]
    assert wiki.waarde(f) is None


def test_de_knop_geeft_de_value_regel_door():
    assert "fact.Value = val" in _bulk_js()


def test_er_is_geen_tweede_feitenformulier_meer(tmp_path):
    from nooch_village.views.wiki import render_pagina
    dd, aid = _dorp(tmp_path)
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="tok", username=IK)
    assert "+ Add fact" not in h and "value='pagina_feit_add'" not in h
    assert "Bulk Import Facts" in h


# ══ For: wordt de sectie van het feit (4 oktober 2026) ══════════════════════
def test_de_for_regel_wordt_de_sectie(tmp_path):
    dd, aid = _dorp(tmp_path)
    _importeer(dd, aid, [{**NFW, "For": "Company certification"}, NFW])
    f1, f2 = _feiten(dd, aid)
    assert f1["sectie"] == "Company certification"
    assert "sectie" not in f2                          # zonder For: geen sectie, wel het feit


def test_de_knop_geeft_de_for_regel_door():
    assert "fact.For = val" in _bulk_js()
