"""W1b-2, variant B (14 oktober 2026): op een pagina van /bom staan de feiten PER VRAAG.

- per vraag de feiten die volgens de dekking voor die vraag tellen, met status; wat nergens telt
  staat onder "Other facts"; geen "Not placed yet" en geen greep;
- `{{fact:<id>}}` in de tekst wordt op zo'n pagina niet getoond; Conclusion en TODO blijven tekst;
- een cel die alleen op zelfgerapporteerde feiten rust zegt "self-reported" (de telling niet);
- onder "What counts" staat "To change this answer: …";
- `village wiki_feit_losmaken` haalt de regels uit de opslag (dry-run, back-up, versie).
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki, wiki_opschoon
from nooch_village import wiki_dekking as dek
from nooch_village.views.wiki import render_pagina

from tests.test_cn3_substantiated import OWNER, _dd
from tests.test_w1_antwoorden import _cel, _check, _feit, _pagina

BODY = ("## Conclusion\n\nPLA counts as plastic.\n\n## Composition\n{{fact:F1}}\n\n"
        "## General\n- Dye disclosure: not provided\n{{fact:F2}}\n\n## TODO\n1. Ask LTA.")


def _dorp(tmp_path):
    return _pagina(tmp_path, [_feit("F1", "Self-reported: 30% PLA fibre"),
                              _feit("F2", "Weight 540 g/m2"),
                              _feit("F3", "Contains plastic: yes, per EU guidance")], body=BODY)


def _html(dd, aid, wie="guest"):
    return render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username=wie)


def _blok(h, k):
    return h.split(f"id='vraag-{k}'", 1)[1].split("<div class='wiki-inline' id='vraag-", 1)[0]


def test_feiten_staan_per_vraag_en_de_rest_onder_other_facts(tmp_path):
    dd, aid = _dorp(tmp_path)
    _check(dd, aid, "F1", plastic="yes", biobased="yes")
    h = _html(dd, aid)
    assert "id='feit-F1'" in _blok(h, "plastic")
    # telt voor twee vragen: voluit bij de eerste, bij de tweede een verwijzing (één anker)
    assert h.count("id='feit-F1'") == 1
    assert "Same fact as under Contains plastic?: <a href='#feit-F1'>" in _blok(h, "biobased")
    overig = h.split("id='vraag-overig'", 1)[1]
    assert "id='feit-F2'" in overig and "id='feit-F3'" in overig
    assert "Not placed yet" not in h and "wb-greep-knop" not in h and "place at end of text" not in h


def test_de_tekst_blijft_tekst_zonder_feiten_erin(tmp_path):
    dd, aid = _dorp(tmp_path)
    h = _html(dd, aid)
    tekst = h.split("id='wiki-body'", 1)[1].split("id='vragen'", 1)[0]
    assert "PLA counts as plastic." in tekst and "Ask LTA." in tekst and "Dye disclosure" in tekst
    assert "data-blok='fact'" not in tekst and "{{fact:" not in tekst


def test_self_reported_staat_bij_de_cel_en_de_telling_verandert_niet(tmp_path):
    dd, aid = _dorp(tmp_path)
    _check(dd, aid, "F1", plastic="yes")
    assert _cel(dd, "plastic")["status"] == dek.GECHECKT and _cel(dd, "plastic")["zelf_gerapporteerd"]
    assert "Checked: yes, self-reported</span>" in _blok(_html(dd, aid), "plastic")
    # een onafhankelijk feit erbij: niet meer alleen self-reported
    _check(dd, aid, "F3", plastic="yes")
    assert _cel(dd, "plastic")["status"] == dek.GECHECKT and not _cel(dd, "plastic")["zelf_gerapporteerd"]
    assert "Checked: yes</span>" in _blok(_html(dd, aid), "plastic")


def test_hoe_het_werkt_staat_een_keer_bovenaan_en_what_counts_achter_een_knop(tmp_path):
    """15 oktober 2026: "To change this answer" per vraag is één ingeklapte "How this works" bovenaan
    geworden; "What counts" zit achter een knop in de statusregel én in het "+ Add fact"-paneel."""
    dd, aid = _dorp(tmp_path)
    _check(dd, aid, "F1", plastic="yes")
    h = _html(dd, aid)
    assert h.count("<summary>How this works</summary>") == 1 and "To change this answer" not in h
    hoe = h.split("<summary>How this works</summary>", 1)[1].split("</details>", 1)[0]
    for status in ("Checked:", "Unchecked:", "Open:", "Conflict:", "Deferred:"):
        assert status in hoe, status
    b = _blok(h, "plastic")
    knop = b.split("<summary class='flink'>What counts</summary>", 1)[1].split("</details>", 1)[0]
    assert "Under EU guidance PLA counts as plastic" in knop
    paneel = h.split("id='vraag-plastic'", 1)[1].split("<summary class='flink'>+ Add fact</summary>", 1)[1]
    assert paneel.split("</form>", 1)[0].count("What counts: As a fact, grounded in the technical") == 1


def test_conflict_en_uitstel_houden_een_eigen_regel(tmp_path):
    dd, aid = _dorp(tmp_path)
    _check(dd, aid, "F1", biobased="yes")
    _check(dd, aid, "F3", biobased="no")
    assert "Remove the wrong fact, or re-check it with the right answer." in _blok(_html(dd, aid), "biobased")
    form = {"aid": [aid], "soort": ["materiaal"], "k": ["co2"], "tot": ["2099-01-01"], "next": ["/"]}
    cockpit2.dispatch(dd, "vraag_uitstel", form, username="guest")
    assert "Add a fact before the date, or undo the deferral." in _blok(_html(dd, aid), "co2")


def test_open_zonder_feiten_staat_op_een_regel(tmp_path):
    dd, aid = _dorp(tmp_path)
    b = _blok(_html(dd, aid), "co2")
    regel = b.split("<span class='qadd-row'>", 1)[1]
    assert regel.startswith("<span class='nu-status nu-status--open'>Open</span><span class='muted'>no fact yet</span>")
    assert "+ Add fact</summary>" in regel and "value='vraag_uitstel'" in regel
    assert "No fact on this page carries this number yet." not in b


def test_een_pagina_buiten_bom_houdt_de_feiten_in_de_tekst(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(OWNER, "note", title="Meeting notes", body="## Notes\n{{fact:F1}}",
                   meta={"feiten": [_feit("F1", "x"), _feit("F2", "y")]})
    h = _html(dd, a.id)
    assert "data-blok='fact'" in h and "Not placed yet" in h and "id='vragen'" not in h


def test_losmaken_dry_run_en_toepassen(tmp_path):
    dd, aid = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    ids = wiki_opschoon.bom_pagina_ids(st.att, st.bom_leveranciers, st.bom_materialen)
    assert aid in ids
    voor = open(st.att.path, encoding="utf-8").read()
    plan_ = wiki_opschoon.losmaken_plan(st.att, ids)
    assert open(st.att.path, encoding="utf-8").read() == voor                       # dry-run
    koppen = {k["kop"]: k for k in plan_[0]["koppen"]}
    assert koppen["Composition"]["kop_weg"] and not koppen["Composition"]["midden"]
    assert koppen["General"]["midden"] and not koppen["General"]["kop_weg"]
    assert "2 fact(s) in the text; 1 of them between other text" in wiki_opschoon.losmaken_tekst(plan_)
    n_versies = len(st.att.get(aid).versions)
    wiki_opschoon.losmaken_toepassen(st.att, plan_, actor_id="cli")
    a = cockpit2._Stores(dd).att.get(aid)
    assert "{{fact:" not in a.body and "## Composition" not in a.body
    assert "## Conclusion\n\nPLA counts as plastic." in a.body and "- Dye disclosure: not provided" in a.body
    assert "## TODO\n1. Ask LTA." in a.body
    assert len(a.versions) == n_versies + 1 and wiki.feiten(a)                    # feiten blijven


def test_ook_op_bom_staat_self_reported_bij_de_cel(tmp_path):
    from nooch_village.views.bom import render_bom
    dd, aid = _dorp(tmp_path)
    _check(dd, aid, "F1", plastic="yes")
    h = render_bom(cockpit2._Stores(dd), username="guest")
    assert "aria-label='Contains plastic?: Checked — self-reported'" in h
    assert "#vraag-plastic' aria-label='Contains plastic?: Checked — self-reported' title='Contains plastic?: Checked — self-reported'>Checked</a><div class='muted'>self-reported</div>" in h
