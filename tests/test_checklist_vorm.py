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
