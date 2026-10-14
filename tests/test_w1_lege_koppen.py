"""W1 (3): de lege vraagkopjes gaan van de pagina's af; de uitleg staat bij de vraag ("What counts").
Alleen een kopje met EXACT zijn uitlegzin eronder en verder niets gaat weg."""
from __future__ import annotations

from nooch_village import cockpit2, wiki, wiki_dekking as wd, wiki_seed

from tests.test_cn3_substantiated import OWNER, _dd

P, B, C = wiki.PLASTIC, wiki.BIOBASED, wiki.CERTIFICERING


def _body(*delen):
    return "\n\n".join(delen)


def test_alleen_helemaal_lege_kopjes_gaan_weg():
    body = _body("## CO2 & Water\nAs a fact with a value.",
                 f"{P[0]}\n{P[1]}",                                   # leeg: weg
                 f"{B[0]}\n{B[1]}\n{{{{fact:F1}}}}",                   # met een feit: blijft
                 f"{C[0]}\n{C[1]}\nOur own note about certificates.",  # met eigen tekst: blijft
                 "## Open items\n- Animal-derived status: not yet verified")
    nieuw, weg = wiki_seed._lege_vraagkop_blokken(body)
    assert weg == ["Contains plastic"]
    assert P[0] not in nieuw and B[0] in nieuw and "{{fact:F1}}" in nieuw and C[0] in nieuw
    assert "Our own note about certificates." in nieuw and "- Animal-derived status" in nieuw
    assert "\n\n\n" not in nieuw


def test_dry_run_schrijft_niets_en_apply_is_idempotent(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="HyphaLite", body=_body("## Characteristics\nx", f"{P[0]}\n{P[1]}", f"{B[0]}\n{B[1]}"))
    assert wiki_seed.lege_koppen(st.att, apply=False) == [{"id": a.id, "titel": "HyphaLite",
                                                          "weg": ["Contains plastic", "Biobased"]}]
    assert P[0] in cockpit2._Stores(dd).att.get(a.id).body
    wiki_seed.lege_koppen(cockpit2._Stores(dd).att, apply=True, actor_id="t")
    body = cockpit2._Stores(dd).att.get(a.id).body
    assert P[0] not in body and B[0] not in body and "## Characteristics" in body
    assert wiki_seed.lege_koppen(cockpit2._Stores(dd).att, apply=False) == []


def test_wat_telt_staat_bij_de_vraag(tmp_path):
    assert wd.wat_telt("materiaal", "biobased") == B[1]
    assert "number" in wd.wat_telt("materiaal", "co2") and wd.wat_telt("materiaal", "bestaat_niet") == ""
    from nooch_village.views.wiki import render_pagina
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="Pliant", body="## Characteristics\nx")
    st.bom_materialen.zet("Outsole", "Pliant")
    h = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="guest")
    blok = h[h.index("<h2>Questions and facts</h2>"):]
    assert "a measured biobased content" in blok
