"""Een checklist-stap is een handeling, geen alinea — en geen claim die wij niet mogen maken.

GEZIEN OP HET ECHTE SCHERM, 29 aug 2026. De checklist-AI leverde paragraaflange suggesties die
bovendien "recycled polymers" en "algae-based plastics" als ONZE materialen opvoerden. Dat zijn ze
niet, en 'recycled' is bij ons een gereguleerde claim.

DE OORZAAK VAN HET TWEEDE, nagegaan vóór de fix: de planner krijgt de kennislaag mee — kaartjes,
inzichten en Kroniek-records uit `openalex_evidence`, `epo_patents` en de radar — met de instructie
"bouw hierop VOORT". Nergens stond dat dat EXTERN onderzoek is en geen inventaris van wat wij
gebruiken. Een model dat 'PHA, PBAT, algae-based' leest onder het kopje 'wat we al weten', schrijft
het terug als het onze.

Twee dingen zijn daarom veranderd, en ze horen bij elkaar: de prompt zegt nu expliciet dat het blok
extern onderzoek is, en deze zeef staat eronder. Een prompt is een verzoek; een poort is een
garantie.
"""
from __future__ import annotations

from nooch_village.checklist_vorm import MAX_WOORDEN, keur, zeef


def test_een_korte_imperatieve_stap_mag_door():
    assert keur("vraag drie leveranciers om technische specs")["ok"]
    assert keur("reach out and chase")["ok"]


def test_een_alinea_wordt_geweigerd():
    """Geijkt op wat MENSEN intypen; de gemeten AI-suggesties waren 25-40 woorden."""
    lang = ("Synthetiseer de bestaande inzichten en bevestigde bevindingen om de huidige kennis "
            "over plantaardige zolen en de relevantie ervan te structureren voor het designteam")
    r = keur(lang)
    assert not r["ok"] and any("te lang" in x for x in r["redenen"])
    assert MAX_WOORDEN <= 12


def test_een_stap_die_met_een_lidwoord_begint_is_geen_opdracht():
    r = keur("de leverancier bellen")
    assert not r["ok"] and any("werkwoord" in x for x in r["redenen"])


def test_onbekende_openers_gaan_er_gewoon_door():
    """FAIL-OPEN op de woordenlijst: liever een stap te veel dan een goede stap geblokkeerd door
    een lijst die nooit compleet is."""
    assert keur("herijk de aannames van vorig kwartaal")["ok"]
    assert keur("prototype de nieuwe zool")["ok"]


def test_een_materiaaldump_tussen_haakjes_wordt_geweigerd():
    """Precies de vorm die op het scherm stond."""
    r = keur("Vergelijk materialen (PHA, PBAT, algae-based plastics) op slijtvastheid")
    assert not r["ok"] and any("haakjes" in x for x in r["redenen"])


# ── De claim-poort, gegrond op de database die er al is ─────────────────────

def test_recycled_wordt_gevangen_met_de_reden_uit_de_database():
    """GEEN eigen woordenlijst: `config/claims_database.json` is de gecureerde bron die Compliance
    ook gebruikt. Twee plekken die hetzelfde feit uitleggen lopen uit de pas — `reference, don't copy`."""
    r = keur("onderzoek recycled polymers voor de zool")
    assert not r["ok"]
    assert any("gerecycled" in x for x in r["redenen"])
    assert r["claims"] and r["claims"][0]["stoplicht"] in ("red", "orange")
    assert r["claims"][0]["waarom"], "de reden komt uit de database, niet uit deze code"


def test_de_toets_faalt_open_op_een_kapotte_database(monkeypatch):
    """Een onleesbare database mag het plannen niet stilzetten: dan keurt hij op vorm alleen, en
    ziet de compliance-rol zo'n stap alsnog."""
    import nooch_village.claims_db as cdb
    monkeypatch.setattr(cdb, "check_tekst",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    r = keur("onderzoek recycled polymers")
    assert r["ok"] is True and r["claims"] == []


# ── De zeef ────────────────────────────────────────────────────────────────

def test_de_zeef_houdt_het_goede_en_meldt_wat_er_weg_ging():
    """Een stille drop zou betekenen dat je niet kunt zien dat de planner iets onbruikbaars maakte —
    en dan is de kwaliteit van het model niet te meten."""
    goed, weg = zeef([
        {"tekst": "vraag drie leveranciers om specs", "skill": None},
        {"tekst": "onderzoek recycled polymers voor de zool", "skill": None},
        {"tekst": "de leverancier bellen", "skill": None},
    ])
    assert [g["tekst"] for g in goed] == ["vraag drie leveranciers om specs"]
    assert len(weg) == 2 and all(w["redenen"] for w in weg)


def test_de_planner_laat_geen_geweigerde_stap_door():
    """De zeef zit ín `plan_items`, niet ernaast: elke aanroeper krijgt hem dus mee."""
    from nooch_village.wizard import plan_items
    ruw = ('{"items":[{"tekst":"vraag drie leveranciers om specs","skill":null,"payload":{}},'
           '{"tekst":"Vergelijk materialen (PHA, PBAT, algae-based plastics) op slijtvastheid",'
           '"skill":null,"payload":{}}]}')
    uit = plan_items("doel", [], reason_fn=lambda p, **k: ruw)
    assert [i["tekst"] for i in uit] == ["vraag drie leveranciers om specs"]


def test_de_prompt_zegt_dat_het_kennisblok_extern_onderzoek_is():
    """Het vangnet is de zeef; dit is de oorzaak zelf. Zonder deze zin leest het model de
    onderzoekskennis als onze inventaris."""
    gezien = {}

    def _vang(p, **k):
        gezien["p"] = p
        return '{"items":[]}'
    from nooch_village.wizard import plan_items
    plan_items("doel", [], reason_fn=_vang, kennis="REEDS BEKEND: PHA, PBAT, algae-based")
    assert "EXTERN ONDERZOEK" in gezien["p"]
    assert "GEEN lijst van" in gezien["p"]
    assert str(MAX_WOORDEN) in gezien["p"]        # de vormregel staat er ook in


# ── Werkt de suggestie eigenlijk? ──────────────────────────────────────────

def test_de_teller_is_dom_en_telt_één_regel_per_project(tmp_path):
    """Geen analytics-rig: per aangemaakt project één regel. Genoeg om over een week op een GETAL
    te beslissen, te weinig om zelf onderhoud te worden."""
    from nooch_village.checklist_vorm import acceptatie, noteer_acceptatie
    d = str(tmp_path)
    assert acceptatie(d) == {"projecten": 0, "aangeboden": 0, "overgenomen": 0, "eigen": 0,
                             "aandeel": None}
    noteer_acceptatie(d, aangeboden=4, overgenomen=1, eigen=2, pid="p1")
    noteer_acceptatie(d, aangeboden=3, overgenomen=3, eigen=0, pid="p2")
    uit = acceptatie(d)
    assert uit["projecten"] == 2 and uit["aangeboden"] == 7 and uit["overgenomen"] == 4
    assert uit["aandeel"] == round(4 / 7, 3)


def test_nooit_aangeboden_is_geen_nul_procent(tmp_path):
    """`no_data ≠ nul`: een deling die 0% suggereert waar de vraag niet gesteld is, leest als
    'genegeerd' terwijl er niets te negeren viel."""
    from nooch_village.checklist_vorm import acceptatie, noteer_acceptatie
    d = str(tmp_path)
    noteer_acceptatie(d, aangeboden=0, overgenomen=0, eigen=3, pid="p")
    assert acceptatie(d)["aandeel"] is None


def test_de_eigen_stappen_zijn_de_eerlijke_noemer(tmp_path):
    """Nul overgenomen bij nul eigen stappen betekent 'geen checklist gemaakt', niet 'suggesties
    genegeerd'. Zonder dat getal is het cijfer niet te lezen."""
    from nooch_village.checklist_vorm import acceptatie, noteer_acceptatie
    d = str(tmp_path)
    noteer_acceptatie(d, aangeboden=5, overgenomen=0, eigen=0, pid="p")
    assert acceptatie(d)["eigen"] == 0 and acceptatie(d)["overgenomen"] == 0


def test_meten_blokkeert_nooit_een_aanmaak(tmp_path):
    from nooch_village.checklist_vorm import noteer_acceptatie
    assert noteer_acceptatie("/bestaat/niet/echt", aangeboden=1, overgenomen=1) is False


def test_de_wizard_telt_aangeboden_overgenomen_en_eigen(tmp_path):
    """De drie tellers zitten in de JS én reizen mee naar /wizard/create."""
    from nooch_village.views.wizard import render_wizard
    from nooch_village import cockpit2
    cockpit2._bootstrap(str(tmp_path))
    h = render_wizard(cockpit2._Stores(str(tmp_path)), "t")
    assert "S.sugAan=(S.sugAan||0)+S.suggesties.length" in h     # getoond
    assert "S.sugOver=(S.sugOver||0)+1" in h                      # aangetikt
    assert "S.sugEigen=(S.sugEigen||0)+1" in h                    # zelf getypt
    assert "sug_aan:String(S.sugAan||0)" in h                     # en meegestuurd


def test_de_aanmaak_schrijft_het_spoor(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.checklist_vorm import acceptatie
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    rol = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "wizard_noop", {}, username="guest")   # store-init
    st = cockpit2._Stores(dd)
    assert st.records.get(rol) is not None
    from nooch_village.checklist_vorm import noteer_acceptatie
    noteer_acceptatie(dd, aangeboden=2, overgenomen=1, eigen=1, pid="x")
    assert acceptatie(dd)["projecten"] == 1
