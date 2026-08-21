"""Wiki brok 4 + 5 — het zaad uit bestaande bronnen, en de check op geciteerde bronnen.

Brok 4 bewaakt vooral wat het zaad NIET doet: geen verzonnen feiten, geen pagina op een rol die niet
bestaat, geen overschrijving van wat de eigenaar sindsdien schreef.

Brok 5 bewaakt de belofte van de bron-check: een fout is geen oordeel (fail-closed), de waarneming
is gedateerd, en de check laat géén spoor in de versiehistorie — er verandert immers niets aan de
pagina.
"""
from __future__ import annotations

from nooch_village import cert_register, cockpit2, wiki, wiki_bronnen, wiki_seed
from nooch_village.data_bom import NOOCH_SCHOEN_BOM

OWNER = "mother_earth__nooch__creator_of_shoes"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


# ── brok 4: materiaal-pagina's ──────────────────────────────────────────────

def test_materiaal_pagina_zegt_alleen_wat_de_stuklijst_zegt():
    ps = {p["titel"]: p for p in wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM)}
    hypha = ps["HyphaLite"]
    for deel in ("Vamp", "Tongue", "Heel counter"):
        assert f"- {deel}" in hypha["body"]
    assert "hemp fabric" in hypha["body"]                  # het alternatief uit de comment-kolom
    assert hypha["feiten"] == []                           # géén verzonnen duurzaamheidsfeit


def test_materiaal_zonder_dubbele_titels():
    # Twee pagina's met dezelfde titel lossen als [[link]] bewust niet op — dan zouden ze allebei
    # onbereikbaar zijn. 'Cotton thread' en 'Cotton Thread' horen dus één pagina te zijn.
    titels = [p["titel"].lower() for p in wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM)]
    assert len(titels) == len(set(titels))
    assert "cotton thread" in titels


def test_onzeker_materiaal_wordt_een_open_punt_geen_eigen_pagina():
    ps = {p["titel"]: p for p in wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM)}
    assert "BIOREL (?)" not in ps and "BIOREL" in ps
    assert "nog onzeker" in ps["BIOREL"]["body"]
    assert "Eyestay Reinforcement" in ps["BIOREL"]["body"]


def test_vrije_check_opmerking_gaat_niet_verloren():
    ps = {p["titel"]: p for p in wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM)}
    assert "linen thread" in ps["Cotton thread"]["body"]


# ── brok 4: claim-pagina's ──────────────────────────────────────────────────

def _db():
    return {"meta": {"versie": "test"},
            "termen": [],
            "werklijst": [{"claim": "“100% Vegan” — homepage", "oordeel": "orange",
                           "herformulering": "materiaal-voor-materiaal", "status": "open"}]}


def test_claim_zonder_certificaat_krijgt_geen_feit_maar_een_wachtlijstregel(tmp_path):
    st = _stores(tmp_path)
    p = wiki_seed.claim_paginas(_db(), st.evidence)[0]
    assert p["feiten"] == []                               # nooit een ongegronde bewering dragen
    assert "Nog niet onderbouwd" in p["body"] and "Wat er nodig is" in p["body"]
    assert "oranje" in p["body"] and "materiaal-voor-materiaal" in p["body"]


def test_claim_met_geldig_certificaat_krijgt_dat_certificaat_als_grond(tmp_path):
    st = _stores(tmp_path)
    claim = "“100% Vegan” — homepage"
    r = st.evidence.record(role_id="compliance", skill=cert_register.SKILL, query=claim,
                           source=cert_register.EXTERN, status="bevestigd",
                           meta={"feit": claim, "instantie": "PETA", "geldig_tot": "2030-01-01",
                                 "claims": [claim]})
    p = wiki_seed.claim_paginas(_db(), st.evidence, vandaag="2026-08-20")[0]
    assert len(p["feiten"]) == 1
    assert p["feiten"][0]["grond"] == {"soort": "cert", "ref": r["id"], "citaat": "", "url": ""}
    assert "Nog niet onderbouwd" not in p["body"]


def test_verlopen_certificaat_onderbouwt_de_claim_niet(tmp_path):
    st = _stores(tmp_path)
    claim = "“100% Vegan” — homepage"
    st.evidence.record(role_id="compliance", skill=cert_register.SKILL, query=claim,
                       source=cert_register.EXTERN, status="bevestigd",
                       meta={"feit": claim, "instantie": "PETA", "geldig_tot": "2024-01-01",
                             "claims": [claim]})
    p = wiki_seed.claim_paginas(_db(), st.evidence, vandaag="2026-08-20")[0]
    assert p["feiten"] == [] and "Nog niet onderbouwd" in p["body"]


# ── brok 4: zaaien ──────────────────────────────────────────────────────────

def test_dry_run_schrijft_niets(tmp_path):
    st = _stores(tmp_path)
    rapport = wiki_seed.zaai(st.att, st.records,
                             paginas=wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM),
                             eigenaar=OWNER, soort="materiaal", apply=False)
    assert rapport and all(r["actie"] == "zou aanmaken" for r in rapport)
    assert cockpit2._Stores(st.dd).att.list(OWNER, "note") == []


def test_apply_maakt_de_paginas_en_is_idempotent(tmp_path):
    st = _stores(tmp_path)
    paginas = wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM)
    r1 = wiki_seed.zaai(st.att, st.records, paginas=paginas, eigenaar=OWNER,
                        soort="materiaal", apply=True)
    assert all(r["actie"] == "aangemaakt" for r in r1)
    st2 = cockpit2._Stores(st.dd)
    assert len(st2.att.list(OWNER, "note")) == len(paginas)

    r2 = wiki_seed.zaai(st2.att, st2.records, paginas=paginas, eigenaar=OWNER,
                        soort="materiaal", apply=True)
    assert all(r["actie"] == "bestaat al" for r in r2)
    assert len(cockpit2._Stores(st.dd).att.list(OWNER, "note")) == len(paginas)


def test_zaad_overschrijft_niet_wat_de_eigenaar_zelf_schreef(tmp_path):
    st = _stores(tmp_path)
    eigen = st.att.add(OWNER, "note", title="Pliant", body="Wat de eigenaar zelf schreef.")
    st2 = cockpit2._Stores(st.dd)
    wiki_seed.zaai(st2.att, st2.records, paginas=wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM),
                   eigenaar=OWNER, soort="materiaal", apply=True)
    assert cockpit2._Stores(st.dd).att.get(eigen.id).body == "Wat de eigenaar zelf schreef."


def test_ontbrekende_eigenaar_rol_zaait_niets(tmp_path):
    # De compliance-rol bestaat niet in elke dataset. Fail-closed: niets aanmaken, wél zeggen waarom.
    st = _stores(tmp_path)
    rapport = wiki_seed.zaai(st.att, st.records, paginas=[{"titel": "x", "body": "y", "feiten": []}],
                             eigenaar="compliance", soort="claim", apply=True)
    assert rapport[0]["actie"] == "overgeslagen" and "bestaat niet" in rapport[0]["reden"]
    assert cockpit2._Stores(st.dd).att.by_kind("note") == []


def test_zaai_alles_slaat_de_ene_helft_over_en_doet_de_andere(tmp_path):
    st = _stores(tmp_path)
    rapport = wiki_seed.zaai_alles(st.att, st.records, st.evidence,
                                   eigenaar_materiaal=OWNER, eigenaar_claims="compliance",
                                   apply=True)
    materiaal = [r for r in rapport if r["soort"] == "materiaal"]
    claims = [r for r in rapport if r["soort"] == "claim"]
    assert materiaal and all(r["actie"] == "aangemaakt" for r in materiaal)
    assert claims and claims[0]["actie"] == "overgeslagen"
    st2 = cockpit2._Stores(st.dd)
    assert len(st2.att.list(OWNER, "note")) == len(materiaal)


def test_gezaaide_pagina_is_meteen_een_echte_pagina(tmp_path):
    st = _stores(tmp_path)
    wiki_seed.zaai(st.att, st.records, paginas=wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM),
                   eigenaar=OWNER, soort="materiaal", apply=True)
    st2 = cockpit2._Stores(st.dd)
    pags = wiki.paginas(st2.att)
    assert wiki.resolve("HyphaLite", pags) is not None      # linkbaar via [[HyphaLite]]
    from nooch_village.views.wiki import render_pagina
    html = render_pagina(st2, wiki.resolve("Pliant", pags).id, csrf_token="tok", username="guest")
    assert "Outsole" in html and "stuklijst" in html


# ── brok 5: zegt de bron dit nog? ───────────────────────────────────────────

def _pagina_met_citaat(st, *, citaat="a leather alternative grown from mycelium"):
    a = st.att.add(OWNER, "note", title="HyphaLite")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit(
        "Leverancier noemt het een leer-alternatief", soort="bron",
        url="https://voorbeeld.nl/hypha", citaat=citaat)]})
    return cockpit2._Stores(st.dd).att.get(a.id)


def test_citaat_nog_aanwezig_maakt_het_feit_gegrond(tmp_path):
    st = _stores(tmp_path)
    a = _pagina_met_citaat(st)
    st2 = cockpit2._Stores(st.dd)
    rapport = wiki_bronnen.check_pagina(
        st2.att, a, ophaler=lambda u: "Intro. A leather alternative grown from mycelium. Slot.",
        nu="2026-08-20", apply=True)
    assert rapport[0]["gevonden"] is True
    vers = cockpit2._Stores(st.dd).att.get(a.id)
    g = wiki.grond_status(wiki.feiten(vers)[0])
    assert g["status"] == wiki.GEGROND and "2026-08-20" in g["detail"]


def test_citaat_weg_maakt_het_feit_vervallen(tmp_path):
    st = _stores(tmp_path)
    a = _pagina_met_citaat(st)
    st2 = cockpit2._Stores(st.dd)
    wiki_bronnen.check_pagina(st2.att, a, ophaler=lambda u: "De pagina is herschreven.",
                              nu="2026-08-20", apply=True)
    g = wiki.grond_status(wiki.feiten(cockpit2._Stores(st.dd).att.get(a.id))[0])
    assert g["status"] == wiki.VERVALLEN and "no longer found" in g["label"]


def test_een_fout_is_geen_oordeel_over_de_bron(tmp_path):
    # Fail-closed: netwerk stuk ≠ de bron zegt het niet meer.
    st = _stores(tmp_path)
    a = _pagina_met_citaat(st)
    st2 = cockpit2._Stores(st.dd)

    def _stuk(url):
        raise RuntimeError("timeout")

    rapport = wiki_bronnen.check_pagina(st2.att, a, ophaler=_stuk, nu="2026-08-20", apply=True)
    assert rapport[0]["gevonden"] is None
    g = wiki.grond_status(wiki.feiten(cockpit2._Stores(st.dd).att.get(a.id))[0])
    assert g["status"] == wiki.ONGECONTROLEERD and "could not check" in g["detail"]


def test_check_laat_geen_spoor_in_de_versiehistorie(tmp_path):
    st = _stores(tmp_path)
    a = _pagina_met_citaat(st)
    voor = cockpit2._Stores(st.dd).att.get(a.id)
    st2 = cockpit2._Stores(st.dd)
    wiki_bronnen.check_pagina(st2.att, voor, ophaler=lambda u: "niets",
                              nu="2026-08-20", apply=True)
    na = cockpit2._Stores(st.dd).att.get(a.id)
    assert len(na.versions) == len(voor.versions)          # geen versie voor een niet-wijziging
    assert na.updated_at == voor.updated_at                # en de pagina staat niet 'bewerkt'


def test_lui_een_verse_check_wordt_niet_herhaald(tmp_path):
    st = _stores(tmp_path)
    a = _pagina_met_citaat(st)
    st2 = cockpit2._Stores(st.dd)
    wiki_bronnen.check_pagina(st2.att, a, ophaler=lambda u: "niets", nu="2026-08-20", apply=True)
    vers = cockpit2._Stores(st.dd).att.get(a.id)
    assert wiki_bronnen.te_checken(vers, nu="2026-08-25") == []      # binnen het venster: rust
    assert wiki_bronnen.te_checken(vers, nu="2026-09-10") == [0]     # daarna weer aan de beurt


def test_dry_run_van_de_check_schrijft_niets(tmp_path):
    st = _stores(tmp_path)
    a = _pagina_met_citaat(st)
    st2 = cockpit2._Stores(st.dd)
    rapport = wiki_bronnen.check_alles(st2.att, ophaler=lambda u: "niets", nu="2026-08-20")
    assert rapport and rapport[0]["gevonden"] is False
    na = wiki.feiten(cockpit2._Stores(st.dd).att.get(a.id))[0]
    assert not (na["grond"].get("check") or {})            # niets opgeslagen zonder --apply


def test_kort_of_ontbrekend_citaat_wordt_niet_getoetst():
    # Een feit met alleen een URL zou zichzelf anders tot bewijs promoveren.
    zonder = wiki.maak_feit("x", soort="bron", url="https://voorbeeld.nl")
    assert wiki.controleer_citaat(zonder, "van alles")["gevonden"] is None
    kort = wiki.maak_feit("x", soort="bron", url="https://voorbeeld.nl", citaat="vegan")
    assert wiki.controleer_citaat(kort, "vegan schoenen")["gevonden"] is None


def test_typografische_verschillen_breken_de_check_niet():
    feit = wiki.maak_feit("x", soort="bron", url="https://voorbeeld.nl",
                          citaat="grown from mycelium — not from animals")
    tekst = "It is grown from mycelium – not from animals."
    assert wiki.controleer_citaat(feit, tekst)["gevonden"] is True
