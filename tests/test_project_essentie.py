"""De essentie-ladder: herkennen, niet genereren.

Elke trede heeft een eigen reden om te bestaan, en elke reden komt uit de meting op de 307
documenten op productie. De tests hieronder bevriezen die redenen, niet de implementatie.
"""
from __future__ import annotations

import pytest

from nooch_village.project_essentie import Essentie, essentie_van, ontfence
from nooch_village.projects import is_seed_document, seed_document


# ── trede 0: de fence ────────────────────────────────────────────────────────
def test_ontfence_haalt_omhullende_fence_weg():
    assert ontfence("```markdown\n# Kop\n\nEen zin.\n```") == "# Kop\n\nEen zin."


def test_ontfence_ook_zonder_sluitende_fence():
    """7 van de 46 gefencete documenten op prod sluiten niet af; die tellen net zo goed."""
    assert ontfence("```markdown\n# Kop\n\nEen zin.") == "# Kop\n\nEen zin."


def test_ontfence_laat_code_MIDDEN_in_het_document_staan():
    md = "Een zin.\n\n```python\nprint(1)\n```\n\nNog een zin."
    assert ontfence(md) == md


def test_fence_blokkeert_de_essentie_niet():
    """Trede 0 bestaat hiervóór: zonder ontfencen ziet de parser alleen een codeblok."""
    md = "```markdown\n# Kop\n\nDit rapport bevat een echte eerste zin met genoeg lengte.\n```"
    e = essentie_van(md, {})
    assert e.soort == "eerste_zin" and e.tekst.startswith("Dit rapport bevat")


# ── trede 1: de seed ─────────────────────────────────────────────────────────
def test_seed_geeft_geen_essentie():
    """Een essentie tonen bij een seed zou zeggen dat er een rapport is. Dat is niet waar."""
    p = {"done_when": "De shortlist is af"}
    e = essentie_van(seed_document("De shortlist is af"), p)
    assert e.soort == "seed" and not e.heeft_tekst


def test_seed_wordt_herkend_ook_als_done_when_leeg_is_op_het_record():
    """84 van de 107 seeds op prod hebben een LEEG done_when terwijl het document wél geseed is.

    Die vielen door de directe vergelijking heen, waardoor de sjabloonzin als samenvatting op de
    kaart kwam — precies het liegen dat deze trede moet voorkomen."""
    doc = seed_document("Meta & Google tracking volledig geïmplementeerd.")
    assert is_seed_document({"done_when": ""}, doc) is True
    assert essentie_van(doc, {"done_when": ""}).soort == "seed"


def test_seed_plus_antwoord_is_geen_seed_meer():
    doc = seed_document("De shortlist is af") + "\n\nDrie leveranciers benaderd, twee reageerden."
    p = {"done_when": "De shortlist is af"}
    assert is_seed_document(p, doc) is False
    assert essentie_van(doc, p).soort == "eerste_zin"


def test_leeg_document_is_geen_seed():
    """'Nog de opdracht' en 'nog niets' zijn op het scherm verschillende zinnen."""
    assert is_seed_document({"done_when": "x"}, "") is False
    assert essentie_van("", {}).soort == "geen"


# ── trede 2: de doelregel ────────────────────────────────────────────────────
@pytest.mark.parametrize("regel", [
    "Projectdoel: Vaststellen of composteerbare elastaan-alternatieven bestaan.",
    "## Goal — Determine whether bio-based alternatives for socks exist today.",
    "TL;DR: De claim is niet houdbaar zonder een certificaat op eindproduct-niveau.",
])
def test_doelregel_wint_van_de_eerste_zin(regel):
    md = f"# Kop\n\n{regel}\n\nDaaronder staat nog een hele alinea met andere inhoud erin."
    assert essentie_van(md, {}).soort == "doelregel"


def test_doelregel_eist_een_scheidingsteken():
    """Anders vangt hij elke zin die toevallig met 'Doel' begint."""
    md = "# Kop\n\nDoelgericht werken is belangrijk voor dit project en zijn uitkomst.\n"
    assert essentie_van(md, {}).soort == "eerste_zin"


# ── trede 3: de eerste zin ───────────────────────────────────────────────────
@pytest.mark.parametrize("fragment,waarom", [
    ("Klaar wanneer", "te kort (115x op prod)"),
    ("Bevindingen:", "label dat op ':' eindigt (18x)"),
    ("Een regel zonder enig zinseinde eraan die toch lang genoeg is", "geen zinseinde (11x)"),
    ("Bevindingen: - URL: nooch.earth - Status code: 200 - Grootte: 270779 bytes.",
     "opsomming platgeslagen op één regel (21x)"),
])
def test_fragmenten_zijn_geen_essentie(fragment, waarom):
    md = f"# Kop\n\n{fragment}\n"
    assert essentie_van(md, {}).soort == "geen", waarom


def test_koppen_lijsten_en_tabellen_zijn_geen_kandidaat():
    md = "# Kop\n\n- punt een\n- punt twee\n\n| a | b |\n|---|---|\n\n> citaat\n"
    assert essentie_van(md, {}).soort == "geen"


def test_eerste_echte_zin_wint():
    md = ("# Kop\n\n- eerst een lijst\n\n"
          "Het onderzoek laat zien dat er geen harde onderbouwing is voor de claim.\n")
    e = essentie_van(md, {})
    assert e.soort == "eerste_zin"
    assert e.tekst == "Het onderzoek laat zien dat er geen harde onderbouwing is voor de claim."


# ── kappen ───────────────────────────────────────────────────────────────────
def test_lange_essentie_wordt_op_een_zinsgrens_gekapt():
    lang = ("Dit is de eerste zin van het rapport en hij is lang genoeg om te tellen. "
            + "Daarna volgt nog veel meer tekst die niet meer op de kaart hoeft te passen. " * 4)
    e = essentie_van(f"# Kop\n\n{lang}\n", {})
    assert e.gekapt is True
    assert len(e.tekst) <= 240
    assert e.tekst.endswith((".", "…"))


def test_korte_essentie_wordt_niet_gekapt():
    md = "# Kop\n\nHet onderzoek laat zien dat er geen harde onderbouwing is voor de claim.\n"
    assert essentie_van(md, {}).gekapt is False


def test_kappen_breekt_nooit_midden_in_een_woord():
    lang = "Woord " * 200
    e = essentie_van(f"# Kop\n\n{lang.strip()}.\n", {})
    assert not e.tekst.rstrip("…").endswith("Woor")


# ── de vorm van het antwoord ─────────────────────────────────────────────────
def test_essentie_is_altijd_een_van_vier_soorten():
    for doc in ("", "```markdown\n```", "# Alleen een kop\n", seed_document("x"),
                "# Kop\n\nEen zin die lang genoeg is om als essentie te dienen.\n"):
        assert essentie_van(doc, {"done_when": "x"}).soort in {
            "seed", "doelregel", "eerste_zin", "geen"}


def test_essentie_is_onveranderlijk():
    """De essentie is een waarneming, geen werkobject: hij wordt gelezen, niet bijgesteld."""
    e = Essentie("eerste_zin", "tekst")
    with pytest.raises(Exception):
        e.tekst = "iets anders"                                     # type: ignore[misc]
