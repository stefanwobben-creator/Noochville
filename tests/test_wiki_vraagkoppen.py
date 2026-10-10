"""Eén kopje per vraag op de materiaal- en leverancierpagina's (10 oktober 2026).

`wiki_seed.vraagkoppen_body` is puur; `vraagkoppen` loopt de pagina's van /bom af en schrijft met
`apply` één versie per pagina.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki, wiki_seed

OUD = wiki.OUD_DIERLIJK_CHEMISCH
OWNER = "mother_earth__nooch__creator_of_shoes"


def _zaad_body() -> str:
    """Zoals de 13 gezaaide materiaalpagina's er op prod uitzien."""
    return "\n".join(["From the bill of materials.", "", "## CO2 & Water", "Uitleg.", "",
                      OUD[0], OUD[1], "", "## Open items", "- Animal-derived status: not yet verified"])


def test_het_lege_gedeelde_kopje_maakt_plaats_voor_een_kopje_per_vraag():
    body, toegevoegd, oud = wiki_seed.vraagkoppen_body(_zaad_body(), "materiaal")
    assert OUD[0] not in body and oud == "removed the empty shared heading"
    assert toegevoegd == ["Contains plastic", "Biobased", "Animal-derived", "Dyes & chemicals",
                          "Certification"]
    # vóór Open items, en de open punten blijven staan
    assert body.index("## Certification") < body.index("## Open items")
    assert "- Animal-derived status: not yet verified" in body


def test_tekst_of_feiten_onder_het_gedeelde_kopje_blijven_waar_ze_staan():
    bron = _zaad_body().replace(OUD[1], OUD[1] + "\n{{fact:a}}")
    body, toegevoegd, oud = wiki_seed.vraagkoppen_body(bron, "materiaal")
    assert OUD[0] in body and "{{fact:a}}" in body
    assert oud.startswith("kept") and "by hand" in oud
    assert "Animal-derived" in toegevoegd            # het nieuwe kopje komt er wél bij
    # het feit staat nog onder het OUDE kopje, niet ineens onder een nieuw
    assert body.index(OUD[0]) < body.index("{{fact:a}}") < body.index("## Open items")


def test_een_bestaand_kopje_of_alias_krijgt_geen_tweede():
    bron = "# Certifications\nx\n## Contains plastic\n{{fact:a}}"
    body, toegevoegd, _ = wiki_seed.vraagkoppen_body(bron, "materiaal")
    assert "Certification" not in toegevoegd and "Contains plastic" not in toegevoegd
    assert body.count("Contains plastic") == 1


def test_zonder_open_items_komt_het_aan_het_eind():
    body, toegevoegd, _ = wiki_seed.vraagkoppen_body("Tekst.\n", "leverancier")
    assert body.startswith("Tekst.\n\n## Location & contact")
    assert toegevoegd[-1] == "Ownership & health" and not body.endswith("\n")


def test_idempotent():
    eens, _t, _o = wiki_seed.vraagkoppen_body(_zaad_body(), "materiaal")
    twee, toegevoegd, oud = wiki_seed.vraagkoppen_body(eens, "materiaal")
    assert twee == eens and toegevoegd == [] and oud == ""


def test_een_kop_in_een_codeblok_telt_niet():
    _b, toegevoegd, _o = wiki_seed.vraagkoppen_body("```\n## Biobased\n```", "materiaal")
    assert "Biobased" in toegevoegd


def test_de_keten_dry_run_dan_apply_op_de_paginas_van_bom(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mat = st.att.add(OWNER, "note", title="Pliant", body=_zaad_body())
    lev = st.att.add(OWNER, "note", title="NFW", body="## Labor & compliance\nx")
    los = st.att.add(OWNER, "note", title="Iets anders", body=_zaad_body())
    st.bom_leveranciers.zet("Pliant", "NFW")

    def run(apply):
        s = cockpit2._Stores(dd)
        return wiki_seed.vraagkoppen(s.att, s.bom_materialen, s.bom_varianten, s.bom_leveranciers,
                                     apply=apply)

    droog = run(False)
    assert {r["id"]: r["soort"] for r in droog} == {mat.id: "materiaal", lev.id: "leverancier"}
    assert cockpit2._Stores(dd).att.get(mat.id).body == _zaad_body()      # dry-run schrijft niets
    run(True)
    st = cockpit2._Stores(dd)
    assert "## Dyes & chemicals" in st.att.get(mat.id).body
    assert "## Ownership & health" in st.att.get(lev.id).body
    assert st.att.get(los.id).body == _zaad_body()                         # niet op /bom
    assert run(False) == []                                               # idempotent


def test_een_nieuw_kopje_krijgt_het_niveau_van_open_items():
    body, _t, _o = wiki_seed.vraagkoppen_body("# Labor & compliance\nx\n# Open items\n- y", "leverancier")
    assert "\n# Ownership & health\n" in body and "## Ownership" not in body
