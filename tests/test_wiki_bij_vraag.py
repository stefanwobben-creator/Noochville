"""`bij_vraag` (besluit Stefan, 16 oktober 2026): wie bij een vraag op "+ Add fact" klikt, ziet het
feit daaronder — ook ongecheckt, met de Check-knop. Het telt daar niet als bewijs: de koppeling geldt
alleen zolang niemand het nakeek, en een treffer via `bij_vraag` maakt de cel hooguit "Unchecked".
Na een check beslist het gekozen antwoord; na "Undo check" staat het weer onder de oorspronkelijke
vraag. `telt_voor` slaat ongecheckte treffers over: de chip zegt dan "Not checked yet"."""
from __future__ import annotations

from nooch_village import cockpit2, wiki, wiki_dekking as wd, wiki_opschoon, wiki_seed
from nooch_village.views.wiki import render_pagina

from tests.test_w1_antwoorden import BRON, _cel, _check, _feit, _pagina


def _html(dd, aid):
    return render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")


def _blok(h, k):
    return h.split(f"id='vraag-{k}'", 1)[1].split(" id='vraag-", 1)[0]


def _add(dd, aid, k, tekst="Supplier says no plastic", **extra):
    """"+ Add fact" bij vraag `k`, ZONDER het vinkje "I checked this". Geeft het nieuwe feit-id."""
    form = {"aid": [aid], "vraag": [k], "tekst": [tekst], "soort": ["bron"], "url": [BRON["url"]],
            "next": ["/"], **{n: [w] for n, w in extra.items()}}
    melding = cockpit2.dispatch(dd, "pagina_feit_add", form, username="guest")[1]
    assert melding.startswith("➕ fact added") and "checked" not in melding
    return wiki.feiten(cockpit2._Stores(dd).att.get(aid))[-1]["id"]


def _feit_van(dd, aid, fid):
    return next(f for f in wiki.feiten(cockpit2._Stores(dd).att.get(aid)) if f["id"] == fid)


def _rij(dd):
    st = cockpit2._Stores(dd)
    d, _ctx = wd.uit_stores(st.att, st.bom_leveranciers, st.bom_materialen)
    return next(r for r in d["materialen"] if r.get("pagina") is not None)


def test_1_toegevoegd_zonder_vinkje_staat_onder_de_vraag_en_telt_niet(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    fid = _add(dd, aid, "plastic")
    assert _feit_van(dd, aid, fid)["bij_vraag"] == "plastic"
    c = _cel(dd, "plastic")
    assert c["status"] == wd.ONGECHECKT and c["feiten"] == [fid] and "antwoord" not in c
    assert c["reden_kort"] == "1 found, none checked"
    # geen bewijs: niet volledig, geen "Counts for", geen antwoord
    assert not wd.gestaafd(_rij(dd))
    assert wd.telt_voor(_rij(dd)) == {}
    b = _blok(_html(dd, aid), "plastic")
    kop = b.split("</summary>", 1)[0]
    assert "Unchecked" in kop and "<span class='muted'>unchecked</span>" in kop and "1 fact</span>" in kop
    assert f"id='feit-{fid}'" in b
    assert "<summary class='btn sm'>Check</summary>" in b                       # de Check-knop
    assert ">Not checked yet</span>" in b and "Counts for Contains plastic" not in b
    # en niet onder Other facts
    assert "id='vraag-overig'" not in _html(dd, aid)


def test_1b_ook_een_bron_die_zichzelf_bewijst_maakt_er_geen_antwoord_van(tmp_path):
    """Een teruggevonden citaat is gegrond zonder mens. Via `bij_vraag` blijft de cel toch Unchecked."""
    dd, aid = _pagina(tmp_path, [])
    fid = _add(dd, aid, "plastic", citaat="no plastic")
    st = cockpit2._Stores(dd)
    a = st.att.get(aid)
    meta = dict(a.meta)
    meta["feiten"] = [dict(f, grond=dict(f["grond"], check={"gevonden": True, "op": "2026-10-16"}))
                      for f in meta["feiten"]]
    st.att.update(aid, meta=meta)
    assert wiki.grond_status(_feit_van(dd, aid, fid))["status"] == wiki.GEGROND
    c = _cel(dd, "plastic")
    assert c["status"] == wd.ONGECHECKT and "antwoord" not in c and c["ongecheckt"] == [fid]
    assert wd.telt_voor(_rij(dd)) == {}
    kop = _blok(_html(dd, aid), "plastic").split("</summary>", 1)[0]
    assert "<span class='muted'>unchecked</span>" in kop


def test_2_na_een_check_voor_een_andere_vraag_telt_het_niet_meer_bij_de_eerste(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    fid = _add(dd, aid, "plastic")
    _check(dd, aid, fid, biobased="yes")
    assert _cel(dd, "plastic")["status"] == wd.LEEG and _cel(dd, "plastic")["feiten"] == []
    assert _cel(dd, "biobased")["antwoord"] == "yes"
    assert wd.telt_voor(_rij(dd)) == {fid: [("biobased", "yes")]}
    assert f"id='feit-{fid}'" not in _blok(_html(dd, aid), "plastic")


def test_3_undo_check_brengt_het_terug_onder_de_oorspronkelijke_vraag(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    fid = _add(dd, aid, "plastic")
    _check(dd, aid, fid, biobased="yes")
    cockpit2.dispatch(dd, "pagina_feit_gezien", {"aid": [aid], "fid": [fid], "uit": ["1"], "next": ["/"]},
                      username="guest")
    assert not wiki.nagekeken(_feit_van(dd, aid, fid))
    assert _cel(dd, "plastic")["feiten"] == [fid] and _cel(dd, "plastic")["status"] == wd.ONGECHECKT
    assert _cel(dd, "biobased")["status"] == wd.LEEG
    assert f"id='feit-{fid}'" in _blok(_html(dd, aid), "plastic")


def test_4_een_tekstbewerking_en_de_herstelroute_laten_bij_vraag_intact(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    fid = _add(dd, aid, "plastic")
    form = {"aid": [aid], "fid": [fid], "next": ["/"], "tekst": ["Supplier says: no plastic at all"],
            "soort": ["bron"], "url": [BRON["url"]], "citaat": [""]}
    cockpit2.dispatch(dd, "pagina_feit_edit", form, username="guest")
    f = _feit_van(dd, aid, fid)
    assert f["tekst"] == "Supplier says: no plastic at all" and f["bij_vraag"] == "plastic"
    assert _cel(dd, "plastic")["feiten"] == [fid]
    # de herstelroute (`village wiki_feit_herstel`) maakt het feit opnieuw met `maak_feit`
    geplakt = {**f, "tekst": "Contains plastic Text: No plastic. Type: link Ref: TDS"}
    nieuw, _notities = wiki_seed.herstel_feit(geplakt)
    assert nieuw["tekst"] == "No plastic." and nieuw["bij_vraag"] == "plastic"


def test_5_wiki_feit_losmaken_raakt_het_veld_niet(tmp_path):
    body = "## Composition\n\n{{fact:F1}}\n\n## Conclusion\n\nSome text."
    dd, aid = _pagina(tmp_path, [_feit("F1", "Self-reported: 30% PLA fibre")], body=body)
    fid = _add(dd, aid, "plastic")
    st = cockpit2._Stores(dd)
    plan_ = wiki_opschoon.losmaken_plan(st.att, [aid])
    assert plan_ and "{{fact:F1}}" not in plan_[0]["na"]
    wiki_opschoon.losmaken_toepassen(st.att, plan_, actor_id="cli")
    a = cockpit2._Stores(dd).att.get(aid)
    assert "{{fact:" not in a.body
    assert _feit_van(dd, aid, fid)["bij_vraag"] == "plastic" and "bij_vraag" not in _feit_van(dd, aid, "F1")
    assert _cel(dd, "plastic")["feiten"] == [fid]


def test_6_deferred_gaat_naar_unchecked(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    cockpit2.dispatch(dd, "vraag_uitstel", {"aid": [aid], "soort": ["materiaal"], "k": ["chem"],
                                            "tot": ["2099-12-01"], "next": ["/"]}, username="guest")
    assert _cel(dd, "chem")["status"] == wd.UITGESTELD
    fid = _add(dd, aid, "chem", tekst="Dyes per supplier: reactive dyes")
    c = _cel(dd, "chem")
    assert c["status"] == wd.ONGECHECKT and c["feiten"] == [fid]
    assert " open>" in _html(dd, aid).split("id='vraag-chem'", 1)[1][:10]


def test_een_ongecheckt_feit_onder_zijn_kopje_zegt_not_checked_yet(tmp_path):
    """De `telt_voor`-fix raakt ook de bestaande kop-route: geen "Counts for …: answer not chosen"
    meer bij een feit dat niemand nakeek. Een los ongecheckt feit houdt "No question yet"."""
    dd, aid = _pagina(tmp_path, [_feit("F1", "Certified by GOTS", sectie="Certificate"),
                                 _feit("F2", "Loose note")])
    assert _cel(dd, "cert")["feiten"] == ["F1"] and _cel(dd, "cert")["status"] == wd.ONGECHECKT
    assert wd.telt_voor(_rij(dd)) == {}
    h = _html(dd, aid)
    f1 = h.split("id='feit-F1'", 1)[1].split("id='feit-", 1)[0]
    f2 = h.split("id='feit-F2'", 1)[1].split(" id='vraag-", 1)[0]
    assert ">Not checked yet</span>" in f1 and "answer not chosen" not in f1
    assert ">No question yet</span>" in f2 and "Not checked yet" not in f2
