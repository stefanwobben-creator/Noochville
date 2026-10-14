"""W1b (14 oktober 2026): het eenmalige opschoonscript (`village wiki_opschoon_w1b`) en het
leesrapport (`village wiki_feit_rapport`). Standaard een dry-run: er verandert niets."""
from __future__ import annotations

import json
import os

from nooch_village import cockpit2, wiki, wiki_opschoon

from tests.test_cn3_substantiated import OWNER, _dd

BRON = {"soort": "bron", "url": "https://x.example/a", "citaat": "molded in Vietnam", "ref": ""}


def _nfw(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    feiten = [
        {"id": "hlos", "tekst": "Production site: Vietnam.", "grond": dict(BRON)},
        {"id": "hplek", "tekst": "Production site (placed): Vietnam.", "grond": dict(BRON), "sectie": "Labor"},
        {"id": "hrisk1", "tekst": "RISK: wind-down", "grond": {"soort": "bron", "url": "https://t", "citaat": "q1"}},
        {"id": "hrisk2", "tekst": "RISK:  wind-down", "grond": {"soort": "bron", "url": "https://t"},
         "sectie": "Risk signal"},
        {"id": "h06e6b5b718", "tekst": "An ISO/IEC 17025-accredited lab (University of Ge",
         "grond": {"soort": "bron", "url": "https://u"}},
        {"id": "heigen", "tekst": "Something else entirely", "grond": {"soort": "bron", "url": "https://t"}},
    ]
    a = st.att.add(OWNER, "note", title="NFW", body="## Labor & compliance\n{{fact:hplek}}",
                   meta={"feiten": feiten})
    lta = st.att.add(OWNER, "note", title="LTA", body="## Location & contact\n{{fact:l1}}",
                     meta={"feiten": [{"id": "l1", "tekst": "Plant", "grond": {"soort": "bron", "url": "https://l"}},
                                      {"id": "l2", "tekst": "Loose", "grond": {"soort": "bron", "url": "https://l2"}}]})
    return dd, a.id, lta.id


def test_dry_run_meldt_dubbelen_en_fragment_en_verandert_niets(tmp_path):
    dd, aid, lta = _nfw(tmp_path)
    st = cockpit2._Stores(dd)
    voor = open(st.att.path, encoding="utf-8").read()
    rapport = wiki_opschoon.plan(st.att)
    nfw = next(r for r in rapport if r["id"] == aid)
    weg = {w["fid"]: w for w in nfw["weg"]}
    assert set(weg) == {"hlos", "hrisk1", "h06e6b5b718"}
    assert weg["hlos"]["blijft"] == "hplek" and weg["hlos"]["waarom"] == "same quote and URL"   # geplaatst blijft
    assert weg["hrisk1"]["blijft"] == "hrisk2" and weg["hrisk1"]["waarom"] == "same text"      # For: blijft
    assert weg["hrisk1"]["quote_naar"] == {"fid": "hrisk2", "citaat": "q1", "check_vervalt": False}
    assert open(st.att.path, encoding="utf-8").read() == voor                                # dry-run
    tekst = wiki_opschoon.plan_tekst(rapport)
    assert "remove hlos (same quote and URL — keeps hplek)" in tekst
    assert "copy quote literally to hrisk2: “q1”" in tekst


def test_niet_geplaatste_feiten_op_lta_worden_alleen_gemeld(tmp_path):
    dd, _aid, lta = _nfw(tmp_path)
    st = cockpit2._Stores(dd)
    r = next(r for r in wiki_opschoon.plan(st.att) if r["id"] == lta)
    assert r["weg"] == [] and [o["fid"] for o in r["ongeplaatst"]] == ["l2"]


def test_een_fragment_alleen_op_id_en_begin(tmp_path):
    dd, aid, _lta = _nfw(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.get(aid)
    meta = dict(a.meta)
    meta["feiten"] = [dict(f, tekst="Iets anders") if f["id"] == "h06e6b5b718" else f for f in meta["feiten"]]
    st.att.update(aid, meta=meta)
    nfw = next(r for r in wiki_opschoon.plan(st.att) if r["id"] == aid)
    assert "h06e6b5b718" not in {w["fid"] for w in nfw["weg"]}


def test_toepassen_maakt_eerst_een_back_up_en_een_nieuwe_versie(tmp_path):
    dd, aid, _lta = _nfw(tmp_path)
    st = cockpit2._Stores(dd)
    rapport = wiki_opschoon.plan(st.att)
    pad = wiki_opschoon.back_up(st.att)
    assert os.path.basename(pad).startswith(os.path.basename(st.att.path) + ".bak-w1b-opschoon-")
    voor_versies = len(st.att.get(aid).versions or [])
    assert wiki_opschoon.toepassen(st.att, rapport, actor_id="cli") == 3
    a = cockpit2._Stores(dd).att.get(aid)
    assert {f["id"] for f in wiki.feiten(a)} == {"hplek", "hrisk2", "heigen"}
    blijft = next(f for f in wiki.feiten(a) if f["id"] == "hrisk2")
    assert blijft["grond"]["citaat"] == "q1" and blijft["grond"]["url"] == "https://t"      # letterlijk
    assert len(a.versions or []) == voor_versies + 1                                          # historie blijft
    assert any(f["id"] == "hlos" for f in json.load(open(pad, encoding="utf-8"))[aid]["meta"]["feiten"])


def test_leesrapport_vindt_het_pliant_getal_en_de_dode_feiten(tmp_path):
    from tests.test_w1_antwoorden import _pagina
    gezien = {"door": "Stefan", "op": "2026-10-05"}
    dd, aid = _pagina(tmp_path, [
        {"id": "W", "tekst": "Outsole weight 509 g per pair", "grond": {"soort": "bron", "url": "https://a"},
         "waarde": {"grootheid": "water_per_kg", "getal": 0.0}, "gezien": gezien},
        {"id": "P", "tekst": "Contains plastic: yes. 30% PLA", "grond": {"soort": "bron", "url": "https://b"},
         "gezien": gezien},
        {"id": "A", "tekst": "Background", "grond": {"soort": "bron", "url": "https://c"},
         "gezien": {**gezien, "achtergrond": True}},
    ])
    st = cockpit2._Stores(dd)
    r = wiki_opschoon.leesrapport(st.att, st.bom_leveranciers, st.bom_materialen)
    assert [(x["fid"], x["geldig"]) for x in r["getal"]] == [("W", False)]
    dood = {x["fid"]: x["voorstel"] for x in r["dood"]}
    assert set(dood) == {"W", "P"}                                       # A koos bewust "background only"
    assert dood["P"]["vraag"] == "Contains plastic?" and dood["P"]["waarde"] == "yes"
    assert dood["W"]["vraag"] == ""                                       # geen vraag past: background only
    # het rapport stelt voor, het slaat niets op
    assert not wiki.antwoorden(next(f for f in wiki.feiten(st.att.get(aid)) if f["id"] == "P"))


def test_een_dubbel_over_paginas_heen_gaat_weg_als_aparte_regel(tmp_path):
    """Besluit 14 oktober: LTA 3a3719e4c0 weg, Full Green ab169b9f5f blijft. Alleen met dezelfde tekst."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    tekst = "Self-reported: at end of life its components follow the shoe."
    st.att.add(OWNER, "note", title="Full Green FG S20", body="x",
               meta={"feiten": [{"id": "ab169b9f5f", "tekst": tekst, "grond": {"soort": "bron", "url": "https://a"}}]})
    lta = st.att.add(OWNER, "note", title="LTA", body="x",
                     meta={"feiten": [{"id": "3a3719e4c0", "tekst": tekst, "grond": {"soort": "bron", "url": "https://a"}}]})
    r = next(r for r in wiki_opschoon.plan(st.att) if r["id"] == lta.id)
    assert [w["fid"] for w in r["weg"]] == ["3a3719e4c0"] and r["ongeplaatst"] == []
    assert "same text as ab169b9f5f on Full Green FG S20, which stays" in wiki_opschoon.plan_tekst([r])
    # een andere tekst onder die id: blijft staan
    a = st.att.get(lta.id)
    st.att.update(lta.id, meta={"feiten": [dict(wiki.feiten(a)[0], tekst="Iets anders")]})
    assert all(w["fid"] != "3a3719e4c0" for r in wiki_opschoon.plan(st.att) for w in r["weg"])


def test_bevestigde_dode_feiten_worden_background_only_en_de_check_blijft(tmp_path):
    from tests.test_w1_antwoorden import _cel, _pagina
    gezien = {"door": "Stefan Wobben", "op": "2026-10-06"}
    dd, aid = _pagina(tmp_path, [
        {"id": "ab169b9f5f", "tekst": "End of life", "grond": {"soort": "bron", "url": "https://a"}, "gezien": gezien},
        {"id": "d558e4dbe0", "tekst": "Contains plastic: yes", "grond": {"soort": "bron", "url": "https://b"},
         "gezien": gezien},                                                      # bewust niet in de lijst
        {"id": "7f19dd4247", "tekst": "Carding line", "grond": {"soort": "bron", "url": "https://c"}},   # ongecheckt
    ])
    st = cockpit2._Stores(dd)
    voor = open(st.att.path, encoding="utf-8").read()
    plan_ = wiki_opschoon.achtergrond_plan(st.att)
    acties = {p["fid"]: p["actie"] for p in plan_}
    assert acties["ab169b9f5f"] == "mark" and acties["7f19dd4247"] == "skip"
    assert "d558e4dbe0" not in acties and "504a99532c" not in acties
    assert "7f94b0a52a" not in wiki_opschoon.ACHTERGROND_BEVESTIGD and "504a99532c" not in wiki_opschoon.ACHTERGROND_BEVESTIGD
    assert open(st.att.path, encoding="utf-8").read() == voor                      # dry-run
    assert wiki_opschoon.achtergrond_toepassen(st.att, plan_, actor_id="cli") == 1
    f = next(f for f in wiki.feiten(cockpit2._Stores(dd).att.get(aid)) if f["id"] == "ab169b9f5f")
    assert wiki.achtergrond(f) and wiki.nagekeken(f)["door"] == "Stefan Wobben"   # check blijft
    assert "1 fact(s) to mark background only" in wiki_opschoon.achtergrond_tekst(plan_)
