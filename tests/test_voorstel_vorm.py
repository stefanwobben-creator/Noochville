"""De vaste voorstel-vorm, de pre-check en de degradatie.

Dit staat er vóór de onderzoekspas zelf, met opzet. De hele week draaide om één les: een systeem dat
iets niet kan onderbouwen moet dat zéggen. Een zelfverzekerde aanbeveling die nergens op rust is
erger dan geen aanbeveling — de founder kan de twee niet uit elkaar houden en beslist er wel op.

Twee poorten, allebei vóór de founder:
  1. pre-check: een menu verpakt als voorstel gaat terug voor nog een onderzoekspas;
  2. degradatie: zakt de gegrond-as, dan vervalt de AANBEVELING, niet de bevindingen.
"""
from __future__ import annotations

import pytest

from nooch_village import voorstel_vorm as vv

GEGROND = {
    "soort": vv.SOORT_VOORSTEL,
    "actie": "Vervang 'conscious' op de FAQ-pagina door 'wij kiezen materialen op herkomst en "
             "afbreekbaarheid' en noem daarbij de twee leveranciers.",
    "bewijs": [{"bron": "claims_check", "citaat": "term 'conscious' → stoplicht orange, categorie Generiek",
                "kroniek": "abc123"}],
    "risico": "De herformulering is langer en past mogelijk niet in de bestaande kop.",
    "nodig_van_jou": "",
    "onzeker": "Of de tweede leverancier genoemd mag worden — dat contract kan ik niet inzien.",
}


# ── 1. De pre-check: een menu is geen voorstel ──────────────────────────────

def test_een_gegrond_voorstel_gaat_door():
    assert vv.keur(GEGROND) == (True, "")


@pytest.mark.parametrize("actie,fragment", [
    ("Wil je dat ik de claim vervang of laat staan?", "vraag"),
    ("Zullen we 'conscious' herformuleren of eerst juridisch laten toetsen?", "vraag"),
    ("Zullen we 'conscious' herformuleren, of eerst juridisch laten toetsen.", "beslissing"),
    ("Graag je input op de drie varianten hieronder.", "beslissing"),
    ("Herformuleren.", "geen concrete actie"),
])
def test_een_menu_verpakt_als_voorstel_wordt_afgewezen(actie, fragment):
    """Precies de route die we vervangen: de founder kreeg een menu en moest zelf het werk doen."""
    ok, waarom = vv.keur({**GEGROND, "actie": actie})
    assert ok is False and fragment in waarom


def test_een_voorstel_zonder_bron_is_een_mening():
    ok, waarom = vv.keur({**GEGROND, "bewijs": []})
    assert ok is False and "mening" in waarom


def test_bewijs_zonder_bronveld_telt_niet():
    assert vv.heeft_bewijs({"bewijs": [{"citaat": "iets"}]}) is False
    assert vv.heeft_bewijs({"bewijs": [{"bron": "claims_check", "citaat": "x"}]}) is True


# ── 2. De kale vraag: alleen met een concreet gebrek ────────────────────────

def test_een_kale_vraag_mag_alleen_met_het_concrete_gebrek():
    """Zelfde discipline als de payload-reparatie: eerst zelf proberen, pas escaleren met wát er
    precies ontbreekt — niet 'ik heb je input nodig'."""
    vraag = vv.als_vraag(GEGROND, "het leverancierscontract staat niet in een bron die ik kan lezen")
    assert vraag["soort"] == vv.SOORT_VRAAG
    assert vv.keur(vraag) == (True, "")

    leeg = vv.als_vraag(GEGROND, "")
    ok, waarom = vv.keur(leeg)
    assert ok is False and "menu" in waarom


# ── 3. De degradatie: bevindingen blijven, de aanbeveling vervalt ───────────

def test_degradatie_haalt_de_aanbeveling_weg_en_houdt_het_bewijs():
    """DE regel. Wat de skills ophaalden is echt en hoort de founder te bereiken; de aanbeveling is
    wat de critic niet gedekt vond, dus die vervalt."""
    uit = vv.degradeer(GEGROND, "geen bron dekt de claim dat afbreekbaarheid is vastgesteld")
    assert uit["soort"] == vv.SOORT_BEVINDING
    assert "Geen aanbeveling" in uit["actie"]
    assert uit["bewijs"] == GEGROND["bewijs"]                 # bevindingen ongemoeid
    assert uit["risico"] == GEGROND["risico"]


def test_degradatie_bewaart_wat_er_stond_zodat_het_leerbaar_blijft():
    uit = vv.degradeer(GEGROND, "reden")
    assert uit["gedegradeerd_van"].startswith("Vervang 'conscious'")
    assert uit["waarom_gedegradeerd"] == "reden"


def test_degradatie_maakt_de_open_vraag_expliciet():
    """Niet 'wat wil je', maar 'wat ontbreekt om dit wél te kunnen zeggen'."""
    uit = vv.degradeer(GEGROND, "geen LCA of certificering gevonden")
    assert "Wat ontbreekt om dit te onderbouwen: geen LCA" in uit["onzeker"]
    assert GEGROND["onzeker"] in uit["onzeker"]                # de eigen onzekerheid blijft staan


def test_een_gedegradeerd_voorstel_is_zichtbaar_gedegradeerd():
    """De founder moet in één oogopslag zien dat dit geen aanbeveling is."""
    tekst = vv.render(vv.degradeer(GEGROND, "reden"))
    assert tekst.startswith("⚠️ GEDEGRADEERD")


def test_degradatie_raakt_het_origineel_niet_aan():
    origineel = dict(GEGROND)
    vv.degradeer(GEGROND, "reden")
    assert GEGROND == origineel


# ── 4. De vaste vorm ────────────────────────────────────────────────────────

def test_de_vorm_heeft_vijf_velden_in_leesvolgorde():
    assert vv.VELDEN == ("actie", "bewijs", "risico", "nodig_van_jou", "onzeker")


def test_render_toont_de_bron_en_de_kroniek_verwijzing():
    tekst = vv.render(GEGROND)
    assert "claims_check: term 'conscious' → stoplicht orange" in tekst
    assert "[kroniek:abc123]" in tekst


def test_een_leeg_nodig_van_jou_valt_weg():
    """Een voorstel dat altijd iets van de founder vraagt is weer een menu."""
    assert "Wat ik van je nodig heb" not in vv.render(GEGROND)
    met = vv.render({**GEGROND, "nodig_van_jou": "toegang tot het leverancierscontract"})
    assert "Wat ik van je nodig heb" in met
