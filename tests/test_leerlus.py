"""De leerlus heeft twee kanten, en de schrijfkant ontbrak overal.

HET GEVAL, 8 september 2026. Project "Top 3 European Savon de Potasse Suppliers" concludeerde dat
er geen Europese leverancier bestaat. Stefan zocht op "Savon de Potasse buy" en kreeg een lijst.
Twee fouten, en de tweede is de structurele:

  1. De zoekterm was een SPECIFICATIE, geen zoekopdracht: "Savon de Potasse fabricant fournisseur
     Europe savon liquide potassique industriel" — negen woorden, zes eisen tegelijk. Zo vind je
     de pagina's die op de formulering matchen, niet die op de behoefte.
  2. Het rapport schreef ZELF op wat het anders had moeten doen ("verbreed voorbij het Frans",
     "gebruik B2B-registers in plaats van algemeen webzoeken") en niets las dat ooit terug.

Dat tweede is exact dezelfde vorm als bij de kans-reflex: `Inhabitant._house_constraints` leest bij
elke reflectie huis-regels uit `data/constraints.json` en zet ze in de prompt als "respecteer
ALTIJD", terwijl `Constraints.add` alleen bereikbaar was via `decide_opportunity` — een functie
zonder productie-aanroeper. Het dorp vroeg om een oordeel en kon het niet bewaren.

Deze testen bewaken de LUS, niet de inhoud: schrijven landt, lezen pikt het op, en de brede stap is
een eigenschap van de strategie in plaats van een promptbelofte.
"""
from __future__ import annotations

import json
import os

from nooch_village.constraints import KANSEN, ZOEKEN, Constraints


# ── 1. De store: één mechanisme, twee domeinen ───────────────────────────────

def test_een_regel_landt_en_is_terug_te_lezen(tmp_path):
    c = Constraints(str(tmp_path / "constraints.json"))
    assert c.add("we bieden geen kinderschoenen", domein=KANSEN) is True
    assert c.add("verbreed voorbij het Frans", domein=ZOEKEN) is True
    assert Constraints(str(tmp_path / "constraints.json")).texts(KANSEN) == \
        ["we bieden geen kinderschoenen"]


def test_de_domeinen_lekken_niet_in_elkaar(tmp_path):
    """DE REDEN DAT HET DOMEIN BESTAAT. Een zoekles ("gebruik B2B-registers") is geen
    organisatie-regel; zou hij in de kans-prompt landen, dan stuurt hij voorstellen op een
    uitspraak die daar niet over gaat."""
    c = Constraints(str(tmp_path / "c.json"))
    c.add("kansregel", domein=KANSEN)
    c.add("zoekles", domein=ZOEKEN)
    assert c.texts(KANSEN) == ["kansregel"]
    assert c.texts(ZOEKEN) == ["zoekles"]
    assert set(c.texts()) == {"kansregel", "zoekles"}      # zonder filter: allebei


def test_oude_regels_zonder_domein_tellen_als_kansen(tmp_path):
    """Alles van vóór 8 september heeft geen `domein`-veld. Zonder deze regel zou de bestaande
    lezer ze stil kwijtraken, en dat is een leerlus die vergeet in plaats van leert."""
    pad = tmp_path / "c.json"
    pad.write_text(json.dumps([{"text": "oude regel", "by": "human", "date": "2026-07-01"}]))
    c = Constraints(str(pad))
    assert c.texts(KANSEN) == ["oude regel"]
    assert c.texts(ZOEKEN) == []


def test_dedup_is_per_domein(tmp_path):
    c = Constraints(str(tmp_path / "c.json"))
    assert c.add("begin breed", domein=ZOEKEN) is True
    assert c.add("BEGIN BREED", domein=ZOEKEN) is False     # zelfde regel, zelfde domein
    assert c.add("begin breed", domein=KANSEN) is True      # ander domein, andere lezer


def test_een_regel_is_in_te_trekken(tmp_path):
    """Een oordeel dat niet meer klopt moet weg kunnen, anders wordt de leerlus een gevangenis."""
    c = Constraints(str(tmp_path / "c.json"))
    c.add("tijdelijke regel", domein=ZOEKEN)
    assert c.remove("tijdelijke regel", domein=ZOEKEN) is True
    assert c.remove("tijdelijke regel", domein=ZOEKEN) is False
    assert c.texts(ZOEKEN) == []


def test_de_store_zit_onder_het_slot():
    """Hij is levend geworden: het cockpit/de CLI schrijft, de daemon leest. Twee processen op één
    bestand is precies waar `JsonStore` voor bestaat."""
    from nooch_village.util import JsonStore
    assert issubclass(Constraints, JsonStore)
    assert set(Constraints._WRITE_METHODS) == {"add", "remove"}


# ── 2. De leeskant: pikt de zoekstrategie de les op? ─────────────────────────

class _Ctx:
    def __init__(self, dd):
        self.data_dir = dd
        self.settings = {}


















