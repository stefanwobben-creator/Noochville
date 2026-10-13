"""W1 (2): de bulk-import-parser splitst GROUNDING-feiten ook als er koppen in de geplakte tekst
staan, en `Type: link` wordt een webbron. Zie `tests/js/bulk_import.test.js`."""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from nooch_village import cockpit2, wiki

from tests.test_cn3_substantiated import OWNER, _dd


def test_de_parser_in_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("node niet geïnstalleerd")
    t = pathlib.Path(__file__).resolve().parent / "js" / "bulk_import.test.js"
    uit = subprocess.run([node, str(t)], capture_output=True, text=True, timeout=60)
    assert uit.returncode == 0, uit.stdout + uit.stderr
    assert uit.stdout.count("  ok   ") >= 11, uit.stdout


def test_de_pagina_geeft_bulk_import_de_bestaande_feiten_mee(tmp_path):
    """W1b: de dubbelwaarschuwing vergelijkt met `data-feiten` op `#wiki-form`; de links wijzen naar
    het anker `feit-<id>` dat elk feit op de pagina draagt."""
    import html as _html
    import re
    from nooch_village.views.wiki import _bestaande_feiten_attr
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="LTA", body="x", meta={"feiten": [
        {"id": "F1", "tekst": "It's 60% bio", "grond": {"soort": "bron", "url": "https://a", "citaat": "60'%"}}]})
    attr = _bestaande_feiten_attr(cockpit2._Stores(dd).att.get(a.id))
    waarde = re.fullmatch(r" data-feiten='([^']*)'", attr).group(1)     # geen losse ' in het attribuut
    assert json.loads(_html.unescape(waarde)) == [
        {"id": "F1", "tekst": "It's 60% bio", "citaat": "60'%", "url": "https://a"}]


def test_type_link_wordt_een_webbron(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="LTA", body="## Location & contact")
    feiten = [{"Text": "LTA runs its plant at Via Bologna", "Type": "link", "Ref": "contact page",
               "Quote": "Via Bologna 230/250", "URL": "https://lta.example/contact", "For": "Location & contact"}]
    cockpit2.dispatch(dd, "pagina_bulk_import_facts", {"aid": [a.id], "facts_json": [json.dumps(feiten)], "next": ["/"]},
                      username="guest")
    f = wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]
    assert f["grond"]["soort"] == "bron" and f["grond"]["citaat"] == "Via Bologna 230/250"
    assert f["tekst"] == "LTA runs its plant at Via Bologna" and f["sectie"] == "Location & contact"


# ── het herstelscript (`village wiki_feit_herstel`) ─────────────────────────

from nooch_village import wiki_seed  # noqa: E402

_PDF = {"soort": "document", "ref": "x.pdf", "url": "/wiki-bestand/P/x.pdf", "citaat": ""}


def _geplakt(**kw):
    tekst = ("Composition & content Text: Self-reported: Full Green is 70% TENCEL and 30% PLA. "
             "Type: link Ref: LTA product sheet R.01-22 Quote: 30% Mais/fibre PLA")
    return {"id": "F1", "tekst": tekst, "grond": dict(_PDF), "gezien": {"door": "S", "op": "2026-10-06"}, **kw}


def test_herstel_maakt_de_tekst_schoon_en_zet_het_volledige_citaat_bij_de_bron():
    nieuw, notities = wiki_seed.herstel_feit(_geplakt())
    assert nieuw["tekst"] == "Self-reported: Full Green is 70% TENCEL and 30% PLA."
    assert nieuw["grond"]["citaat"] == "30% Mais/fibre PLA" and nieuw["grond"]["ref"] == "x.pdf"
    assert "gezien" not in nieuw                                        # tekst veranderd: opnieuw nakijken
    assert "sectie" not in nieuw                                        # niet gekoppeld, niet verplaatst
    assert any("lapses" in n for n in notities)


def test_een_afgekapt_stuk_wordt_gemarkeerd_niet_aangevuld():
    tekst = ("Animal-derived & chemical status Text: LTA declares that none of the listed substances are "
             "used. Type: link Ref: REACH letter Quote: none of the substances recalled in th")
    tekst = tekst + " " * (400 - len(tekst))                            # zoals de import afkapte: 400 tekens
    nieuw, _n = wiki_seed.herstel_feit({"id": "F2", "tekst": tekst[:400].rstrip() + "x" * (400 - len(tekst[:400].rstrip())),
                                        "grond": dict(_PDF)})
    assert "[Quote incomplete, check the source:" in nieuw["tekst"] and nieuw["tekst"].endswith("…”]")
    assert nieuw["grond"]["citaat"] == ""                               # een afgekapt citaat wordt geen citaat
    assert len(nieuw["tekst"]) <= 400


def test_een_verklaring_houdt_haar_bron_en_een_gewoon_feit_blijft_staan():
    f = _geplakt(grond={"soort": "attested", "ref": "Stefan Wobben", "op": "2026-10-05", "citaat": "", "url": ""})
    nieuw, notities = wiki_seed.herstel_feit(f)
    assert nieuw["grond"]["soort"] == "attested" and nieuw["grond"]["citaat"] == ""
    assert any("Quote not stored" in n for n in notities)
    assert wiki_seed.herstel_feit({"id": "F3", "tekst": "A normal fact.", "grond": dict(_PDF)}) == (None, [])


def test_dry_run_schrijft_niets_en_apply_is_idempotent(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="Full Green", body="x", meta={"feiten": [_geplakt()]})
    rapport = wiki_seed.feiten_herstellen(st.att, apply=False)
    assert len(rapport) == 1 and "Composition & content Text:" in wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]["tekst"]
    wiki_seed.feiten_herstellen(cockpit2._Stores(dd).att, apply=True, actor_id="t")
    assert wiki.feiten(cockpit2._Stores(dd).att.get(a.id))[0]["tekst"].startswith("Self-reported")
    assert wiki_seed.feiten_herstellen(cockpit2._Stores(dd).att, apply=False) == []
