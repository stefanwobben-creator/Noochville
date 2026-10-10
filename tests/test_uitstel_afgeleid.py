"""Uitstellen terugdraaien (fix 11 oktober 2026): de "not yet …"-regel wordt AFGELEID uit de staat
van het veld, nooit uit de tekst gehaald. Bij de uitrol bleek dat uitstellen + terugdraaien de
regel van de pagina liet verdwijnen."""
from __future__ import annotations

import json

from nooch_village import cockpit2, critical_numbers, wiki_dekking as wd
from nooch_village.cockpit2_util import _md_naar_bron
from nooch_village.views.wiki import _body_html, render_pagina

from tests.test_cn3_substantiated import OWNER, _dd

REGEL = "Dye/chemical disclosure: not yet provided"
BODY = ("## Dyes & chemicals\n\n- " + REGEL + "\n\n## Animal-derived\n\n"
        "- Animal-derived status: not yet verified\n\nEigen tekst.")


def _dorp(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="Pliant", body=BODY)
    st.bom_materialen.zet("Outsole", "Pliant")
    return dd, a.id


def _uitstel(dd, aid, tot="2026-12-31"):
    return cockpit2.dispatch(dd, "vraag_uitstel", {"aid": [aid], "soort": ["materiaal"], "k": ["chem"],
                                                   "tot": [tot], "next": ["/"]}, username="guest")[1]


def _terug(dd, aid):
    return cockpit2.dispatch(dd, "vraag_uitstel_weg", {"aid": [aid], "k": ["chem"], "next": ["/"]},
                             username="guest")[1]


def _stand(dd, aid):
    """(body, meta, zichtbaar in de pagina?, cijfers)."""
    st = cockpit2._Stores(dd)
    a = st.att.get(aid)
    d, ctx = wd.uit_stores(st.att, st.bom_leveranciers, st.bom_materialen)
    h = render_pagina(st, aid, csrf_token="t", username="guest")
    tekst = h[h.index("wiki-body"):h.index("<h3>Questions</h3>")] if "<h3>Questions</h3>" in h else h
    return a.body, json.dumps(a.meta, sort_keys=True), f"<li>{REGEL}</li>" in tekst, wd.cijfers(d, **ctx), tekst


def test_uitstellen_en_terugdraaien_geeft_dezelfde_pagina_byte_voor_byte(tmp_path):
    dd, aid = _dorp(tmp_path)
    body0, meta0, zichtbaar0, c0, _t = _stand(dd, aid)
    assert zichtbaar0 and c0["cellen_deferred"] == 0
    assert "✓" in _uitstel(dd, aid)
    body1, _m, zichtbaar1, c1, tekst1 = _stand(dd, aid)
    assert body1 == body0                                         # de tekst is niet aangeraakt
    assert not zichtbaar1 and "deferred, research by 2026-12-31" in tekst1
    assert (c1["cellen_open"], c1["cellen_deferred"]) == (c0["cellen_open"] - 1, 1)
    assert c1["gestaafd"] == c0["gestaafd"]
    assert "✓" in _terug(dd, aid)
    body2, meta2, zichtbaar2, c2, _t = _stand(dd, aid)
    assert body2.encode() == body0.encode() and meta2 == meta0     # byte voor byte, ook de meta
    assert zichtbaar2 and c2 == c0                                # alle tellingen terug op het begin


def test_verlopen_datum_brengt_de_regel_terug(tmp_path):
    dd, aid = _dorp(tmp_path)
    c0 = _stand(dd, aid)[3]
    assert "✓" in _uitstel(dd, aid, tot="2020-01-01")           # meteen verlopen
    body, _m, zichtbaar, c, tekst = _stand(dd, aid)
    assert body == BODY and zichtbaar and "deferred, research by" not in tekst
    assert (c["cellen_open"], c["cellen_deferred"], c["cellen_deferred_verlopen"]) == (c0["cellen_open"], 0, 1)
    assert c["gestaafd"] == c0["gestaafd"]
    assert c["paginas_zonder_placeholder"] == c0["paginas_zonder_placeholder"]


def test_invullen_na_uitstel_laat_geen_placeholder_staan(tmp_path):
    dd, aid = _dorp(tmp_path)
    c0 = _stand(dd, aid)[3]
    _uitstel(dd, aid)
    st = cockpit2._Stores(dd)
    a = st.att.get(aid)
    feit = {"id": "F1", "tekst": "No azo dyes", "sectie": "Dyes & chemicals", "gezien": {"door": "Stefan", "op": "2026-10-11"},
            "grond": {"soort": "bron", "url": "https://x", "citaat": "", "ref": ""}}
    st.att.update(aid, meta={**a.meta, "feiten": [feit]}, actor_id="t", actor_type="person",
                  governance_ref=f"role:{OWNER}")
    _terug(dd, aid)                                               # ook na het weghalen van het uitstel
    body, _m, zichtbaar, c, tekst = _stand(dd, aid)
    st = cockpit2._Stores(dd)
    d, _ctx = wd.uit_stores(st.att, st.bom_leveranciers, st.bom_materialen)
    assert d["materialen"][0]["cellen"]["chem"]["status"] == wd.GECHECKT
    assert not zichtbaar and REGEL not in tekst.replace(f"data-blok-bron='- {REGEL}'", "")
    assert (c["cellen_checked"], c["cellen_open"], c["cellen_deferred"]) == (
        c0["cellen_checked"] + 1, c0["cellen_open"] - 1, 0)
    assert body == BODY                                           # de bron bewaart de regel nog


def test_bewerken_en_opslaan_schrijft_de_verborgen_regel_ongewijzigd_terug():
    for cel in ({"status": "deferred", "tot": "2026-12-31"}, {"status": "checked"}):
        h = _body_html(BODY, [], blokken=True, placeholders={REGEL: cel})
        assert f"<li>{REGEL}</li>" not in h
        assert _md_naar_bron(h) == BODY


def test_cn3_en_open_vragen_op_de_productie_vorm(tmp_path):
    """De tellingen op /open-questions en CN3 lezen hetzelfde als de pagina."""
    from nooch_village.views.open_vragen import render_open_vragen
    dd, aid = _dorp(tmp_path)
    _uitstel(dd, aid)
    h = render_open_vragen(cockpit2._Stores(dd), csrf_token="t", username="guest")
    assert "Deferred" in h
    rapport = critical_numbers.zaai(cockpit2._Stores(dd).metrics, critical_numbers.laad(), apply=False)
    assert any(r["sleutel"] == "cn3_deferred" for r in rapport)


def test_wie_de_ruwe_tekst_leest_ziet_de_afspraak_niet_een_leeg_veld(tmp_path):
    """Zoeken, /context (systeemprompt en export), de wiki-kaarten en de wiki-tab op /node lezen de
    tekst buiten de pagina om. Een deferred veld mag daar niet als "not yet provided" staan."""
    from nooch_village import artefacts
    from nooch_village.views.overview import render_node
    from nooch_village.views.search import _pages
    from nooch_village.views.wiki import render_wiki_index
    dd, aid = _dorp(tmp_path)

    def lezers():
        st = cockpit2._Stores(dd)
        ctx = artefacts.serialize_context(OWNER, st.records, st.att)
        pagina_ctx = next(n for n in ctx["notes"]["own"] if n["id"] == aid)
        zoek = [p for p in _pages(st, ["pliant"]) if aid in p["url"]][0]
        return {"context_json": pagina_ctx["body"],
                "context_md": artefacts.render_context_markdown(ctx),
                "zoek": zoek["snip"] + " " + " ".join(p["url"] for p in _pages(st, ["provided"])),
                "wiki": render_wiki_index(st),
                "node": render_node(st, OWNER, "wiki")}

    voor = lezers()
    assert REGEL in voor["context_json"] and REGEL in voor["context_md"]
    _uitstel(dd, aid)
    tijdens = lezers()
    assert REGEL not in tijdens["context_json"] and "deferred, research by 2026-12-31" in tijdens["context_json"]
    assert REGEL not in tijdens["context_md"] and "deferred, research by 2026-12-31" in tijdens["context_md"]
    assert "not yet provided" not in tijdens["zoek"] and aid not in tijdens["zoek"].split(" ", 1)[1]
    assert REGEL not in tijdens["wiki"]
    assert f"<li>{REGEL}</li>" not in tijdens["node"]
    assert "Animal-derived status: not yet verified" in tijdens["context_md"]   # de andere vraag blijft
    assert cockpit2._Stores(dd).att.get(aid).body == BODY                        # de bron blijft
    _terug(dd, aid)
    assert lezers()["context_json"] == voor["context_json"]
