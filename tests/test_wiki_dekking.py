"""Dekking op /bom: welke vragen een materiaal- of leverancierpagina beantwoordt (10 oktober 2026).

Pure functies, geen netwerk en geen schijf: een pagina is hier een eenvoudig object met body en
meta, precies de twee velden die de dekking leest.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village import cert_register, wiki
from nooch_village import wiki_dekking as wd

VANDAAG = "2026-10-10"
GEZIEN = {"door": "Stefan", "op": "2026-10-06"}


def _pagina(pid: str, body: str = "", feiten: list | None = None):
    return SimpleNamespace(id=pid, title=pid, body=body, meta={"feiten": feiten or []},
                           kind="note", status="active")


def _feit(fid: str, tekst: str = "iets", *, soort: str = "bron", url: str = "https://x.org",
          gezien: dict | None = None, sectie: str = "", waarde: dict | None = None,
          ref: str = "") -> dict:
    f = {"id": fid, "tekst": tekst,
         "grond": {"soort": soort, "url": url, "ref": ref, "citaat": ""} if soort else {}}
    if gezien:
        f["gezien"] = gezien
    if sectie:
        f["sectie"] = sectie
    if waarde:
        f["waarde"] = waarde
    return f


def _bom(*rijen):
    """Rijen zoals `bom_reken.bereken` ze teruggeeft — alleen de velden die de dekking leest."""
    return {"rijen": [{"part": p, "materiaal": m, "mat": mp, "supplier": s, "lev": lp}
                      for p, m, mp, s, lp in rijen]}


def _cel(pagina, vraag: str, soort: str = "materiaal", **ctx):
    bom = (_bom(("Outsole", "Pliant", pagina, "", None)) if soort == "materiaal"
           else _bom(("Outsole", "Pliant", None, "NFW", pagina)))
    dek = wd.dekking(bom, vandaag=VANDAAG, **ctx)
    rij = dek["materialen" if soort == "materiaal" else "leveranciers"][0]
    return rij["cellen"][vraag]


# ── Celstatus ───────────────────────────────────────────────────────────────

def test_gevuld_en_gecheckt():
    p = _pagina("P", "## Contains plastic\n{{fact:a}}", [_feit("a", gezien=GEZIEN)])
    c = _cel(p, "plastic")
    assert c["status"] == wd.GECHECKT and c["feiten"] == ["a"] and c["kop"] == "Contains plastic"


def test_gevuld_maar_niet_gecheckt():
    p = _pagina("P", "## Contains plastic\n{{fact:a}}", [_feit("a")])
    assert _cel(p, "plastic")["status"] == wd.ONGECHECKT


def test_een_feit_zonder_bron_telt_als_antwoord_maar_niet_als_gecheckt():
    p = _pagina("P", "## Biobased\n{{fact:a}}", [_feit("a", soort="")])
    assert _cel(p, "biobased")["status"] == wd.ONGECHECKT


def test_een_verlopen_hercheck_is_niet_meer_gecheckt():
    f = _feit("a", gezien=GEZIEN)
    f["hercheck"] = "2026-10-01"
    p = _pagina("P", "## Biobased\n{{fact:a}}", [f])
    assert _cel(p, "biobased")["status"] == wd.ONGECHECKT


def test_leeg_als_er_geen_feit_onder_de_vraag_staat():
    p = _pagina("P", "## Contains plastic\nNog uitzoeken.", [])
    c = _cel(p, "plastic")
    assert c["status"] == wd.LEEG and c["feiten"] == []


def test_een_nee_is_een_antwoord():
    """"Unknown" is niet "no": een expliciet "contains no plastic" vult de cel."""
    p = _pagina("P", "## Contains plastic\n{{fact:a}}",
                [_feit("a", "Contains no plastic.", gezien=GEZIEN)])
    assert _cel(p, "plastic")["status"] == wd.GECHECKT


def test_een_feit_onder_een_ander_kopje_beantwoordt_de_vraag_niet():
    p = _pagina("P", "## Environmental impact\n{{fact:a}}",
                [_feit("a", "Contains plastic: yes", gezien=GEZIEN)])
    assert _cel(p, "plastic")["status"] == wd.LEEG


def test_het_gedeelde_zaadkopje_beantwoordt_geen_van_beide_vragen():
    """Eén kopje voor twee vragen: welke het feit beantwoordt, staat er niet — dus geen gok."""
    p = _pagina("P", "## Animal-derived & chemical status\n{{fact:a}}", [_feit("a", gezien=GEZIEN)])
    assert _cel(p, "animal")["status"] == wd.LEEG
    assert _cel(p, "chem")["status"] == wd.LEEG


def test_een_subkopje_telt_voor_het_kopje_erboven():
    p = _pagina("P", "## Certification\n### Lab report\n{{fact:a}}\n## Other\nx",
                [_feit("a", gezien=GEZIEN)])
    assert _cel(p, "cert")["status"] == wd.GECHECKT


def test_kopnaam_is_hoofdletter_ongevoelig_en_een_h1_telt_ook():
    p = _pagina("P", "# LOCATION & CONTACT\n{{fact:a}}", [_feit("a", gezien=GEZIEN)])
    assert _cel(p, "loc", "leverancier")["status"] == wd.GECHECKT


def test_een_ongeplaatst_feit_telt_via_zijn_for_regel():
    p = _pagina("P", "## Labor & compliance\nTekst.", [_feit("a", sectie="Labor & compliance")])
    assert _cel(p, "labor", "leverancier")["status"] == wd.ONGECHECKT


def test_de_plek_in_de_tekst_wint_van_de_for_regel():
    p = _pagina("P", "## Other\n{{fact:a}}", [_feit("a", sectie="Labor & compliance")])
    assert _cel(p, "labor", "leverancier")["status"] == wd.LEEG


def test_een_kop_in_een_codeblok_telt_niet():
    p = _pagina("P", "```\n## Contains plastic\n```\n{{fact:a}}", [_feit("a", gezien=GEZIEN)])
    assert _cel(p, "plastic")["status"] == wd.LEEG


# ── Getal-vragen ────────────────────────────────────────────────────────────

def test_een_getal_vraag_leest_de_grootheid_waar_het_feit_ook_staat():
    f = _feit("a", gezien=GEZIEN, waarde={"grootheid": "co2e_per_kg", "getal": 2.4})
    p = _pagina("P", "## Whatever\n{{fact:a}}", [f])
    assert _cel(p, "co2")["status"] == wd.GECHECKT
    assert _cel(p, "water")["status"] == wd.LEEG


def test_twee_verschillende_getallen_zijn_een_conflict():
    p = _pagina("P", "", [
        _feit("a", gezien=GEZIEN, waarde={"grootheid": "prijs_per_kg", "getal": 10}),
        _feit("b", gezien=GEZIEN, waarde={"grootheid": "prijs_per_kg", "getal": 12}),
    ])
    c = _cel(p, "price", "leverancier")
    assert c["status"] == wd.CONFLICT and "more than one value" in c["reden"]


def test_twee_gelijke_getallen_zijn_geen_conflict():
    p = _pagina("P", "", [
        _feit("a", gezien=GEZIEN, waarde={"grootheid": "water_per_kg", "getal": 5}),
        _feit("b", waarde={"grootheid": "water_per_kg", "getal": 5}),
    ])
    assert _cel(p, "water")["status"] == wd.GECHECKT


# ── Certificaten ────────────────────────────────────────────────────────────

class _Ledger:
    def __init__(self, tot: str):
        self.tot = tot

    def all_records(self):
        return [{"id": "K1", "source": cert_register.EXTERN,
                 "meta": {"instantie": "FSC", "geldig_tot": self.tot}}]


def test_een_geldig_certificaat_is_gecheckt():
    p = _pagina("P", "## Certification\n{{fact:a}}", [_feit("a", soort="cert", ref="K1", url="")])
    assert _cel(p, "cert", ledger=_Ledger("2027-01-01"))["status"] == wd.GECHECKT


def test_een_verlopen_certificaat_is_een_conflict_ook_na_nakijken():
    p = _pagina("P", "## Certification\n{{fact:a}}",
                [_feit("a", soort="cert", ref="K1", url="", gezien=GEZIEN)])
    c = _cel(p, "cert", ledger=_Ledger("2025-12-14"))
    assert c["status"] == wd.CONFLICT and "expired" in c["reden"]


def test_een_conflict_valt_niet_weg_achter_een_gecheckt_feit():
    p = _pagina("P", "## Certification\n{{fact:a}}\n{{fact:b}}",
                [_feit("a", gezien=GEZIEN), _feit("b", soort="cert", ref="K1", url="")])
    assert _cel(p, "cert", ledger=_Ledger("2025-12-14"))["status"] == wd.CONFLICT


# ── Rijen ───────────────────────────────────────────────────────────────────

def test_een_rij_zonder_pagina_heeft_alleen_lege_cellen():
    dek = wd.dekking(_bom(("Laces", "Organic cotton laces", None, "", None)))
    rij = dek["materialen"][0]
    assert rij["pagina"] is None
    assert {c["status"] for c in rij["cellen"].values()} == {wd.LEEG}
    assert set(rij["cellen"]) == {v["k"] for v in wd.vragen("materiaal")}


def test_elk_materiaal_en_elke_leverancier_een_keer_in_stuklijstvolgorde():
    hl = _pagina("HL")
    dek = wd.dekking(_bom(("Vamp", "HyphaLite", hl, "ISA", None),
                          ("Outsole", "Pliant", None, "NFW", None),
                          ("Tongue", "HyphaLite", hl, "ISA", None)))
    assert [m["naam"] for m in dek["materialen"]] == ["HyphaLite", "Pliant"]
    assert dek["materialen"][0]["onderdelen"] == ["Vamp", "Tongue"]
    assert [l["naam"] for l in dek["leveranciers"]] == ["ISA", "NFW"]
    assert dek["leveranciers"][0]["materialen"] == ["HyphaLite"]


def test_een_materiaal_zonder_leverancier_geeft_geen_leveranciersrij():
    dek = wd.dekking(_bom(("Laces", "Cotton", None, "", None)))
    assert dek["leveranciers"] == []


# ── Rollup ──────────────────────────────────────────────────────────────────

def _volle_vs_pagina():
    """Een materiaal met alle Vegan Society-vragen (animal, chem, cert) gecheckt."""
    return _pagina("V", "## Animal-derived\n{{fact:a}}\n## Dyes & chemicals\n{{fact:b}}\n"
                        "## Certificate\n{{fact:c}}",
                   [_feit(i, gezien=GEZIEN) for i in "abc"])


def test_rollup_telt_volledige_materialen_per_doel():
    dek = wd.dekking(_bom(("Vamp", "HyphaLite", _volle_vs_pagina(), "", None),
                          ("Outsole", "Pliant", _pagina("P"), "", None)), vandaag=VANDAAG)
    r = wd.rollup(dek)
    assert r["vs"]["materialen"] == (1, 2)
    assert r["pp"]["materialen"] == (0, 2)     # plastic, biobased, co2, water ontbreken


def test_rollup_vraagt_cfj_niets_aan_een_materiaal():
    r = wd.rollup(wd.dekking(_bom(("Vamp", "HyphaLite", None, "ISA", None))))
    assert "materialen" not in r["cfj"] and r["cfj"]["leveranciers"] == (0, 1)


def test_een_half_gecheckt_materiaal_is_niet_volledig():
    p = _volle_vs_pagina()
    p.meta["feiten"][2] = _feit("c")              # certificaat niet nagekeken
    dek = wd.dekking(_bom(("Vamp", "HyphaLite", p, "", None)), vandaag=VANDAAG)
    assert wd.rollup(dek)["vs"]["materialen"] == (0, 1)


def test_de_vragen_staan_op_een_plek_en_hebben_bekende_doelen():
    for soort in ("materiaal", "leverancier"):
        for v in wd.vragen(soort):
            assert set(v["doelen"]) <= set(wd.DOELEN)
            assert bool(v["koppen"]) != bool(v["grootheid"])
            if v["grootheid"]:
                assert v["grootheid"] in wiki.GROOTHEDEN
    assert [v["k"] for v in wd.vragen("materiaal", "vs")] == ["animal", "chem", "cert"]


def test_een_lege_cel_wijst_naar_het_kopje_waar_het_antwoord_hoort():
    p = _pagina("P", "## Contains plastic\nNog uitzoeken.\n## Biobased", [])
    assert _cel(p, "plastic")["kop"] == "Contains plastic"
    assert _cel(p, "cert")["kop"] == ""          # geen kopje → de pagina zelf
