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


def test_de_zoekstrategie_leest_de_lessen(tmp_path):
    """DE KERNTEST OP DE LUS. Schrijf een les, en hij moet in de prompt terechtkomen die de
    volgende strategie bepaalt. Zonder deze schakel is schrijven zinloos."""
    from nooch_village.skills_impl import zoekstrategie as zs
    dd = str(tmp_path)
    Constraints(os.path.join(dd, "constraints.json")).add(
        "gebruik B2B-registers (Kompass, Europages) voor leveranciers", domein=ZOEKEN)
    assert "Kompass" in " ".join(zs._lessen(_Ctx(dd)))


def test_de_zoekstrategie_leest_de_kansregels_juist_NIET(tmp_path):
    """De tegenhanger van de domeinscheiding, op de lezer in plaats van op de store."""
    from nooch_village.skills_impl import zoekstrategie as zs
    dd = str(tmp_path)
    Constraints(os.path.join(dd, "constraints.json")).add("geen kinderschoenen", domein=KANSEN)
    assert zs._lessen(_Ctx(dd)) == []


def test_de_kans_reflex_leest_de_zoeklessen_juist_NIET(tmp_path):
    """En dezelfde scheiding aan de andere kant, op de échte lezer in `inhabitant.py`."""
    from nooch_village.inhabitant import Inhabitant
    dd = str(tmp_path)
    Constraints(os.path.join(dd, "constraints.json")).add("verbreed eerst", domein=ZOEKEN)
    Constraints(os.path.join(dd, "constraints.json")).add("geen kinderschoenen", domein=KANSEN)

    class _Nep:
        context = _Ctx(dd)
        log = __import__("logging").getLogger("test")
    assert Inhabitant._house_constraints(_Nep()) == ["geen kinderschoenen"]


def test_een_kapotte_store_stopt_de_puls_niet(tmp_path):
    """Fail-soft mét spoor: een onleesbaar bestand mag de reflectie nooit breken."""
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.skills_impl import zoekstrategie as zs
    dd = str(tmp_path)
    (tmp_path / "constraints.json").write_text("{dit is geen json")

    class _Nep:
        context = _Ctx(dd)
        log = __import__("logging").getLogger("test")
    assert Inhabitant._house_constraints(_Nep()) == []
    assert zs._lessen(_Ctx(dd)) == []


# ── 3. Breed voor smal, deterministisch ──────────────────────────────────────

def test_de_echte_mislukte_term_wordt_verbreed():
    """De term uit het geval zelf. Negen woorden met zes eisen erin; de kern is drie woorden."""
    from nooch_village.skills_impl.zoekstrategie import verbreed
    kort = verbreed("Savon de Potasse fabricant fournisseur Europe savon liquide potassique "
                    "industriel")
    assert kort and len(kort.split()) <= 4
    assert "savon" in kort.lower() and "potasse" in kort.lower()
    for eis in ("fabricant", "fournisseur", "Europe", "industriel"):
        assert eis.lower() not in kort.lower(), eis


def test_een_term_die_al_breed_is_blijft_met_rust():
    """Anders verbreedt hij een goede zoekopdracht kapot, en dat is de tegenovergestelde fout."""
    from nooch_village.skills_impl.zoekstrategie import verbreed
    assert verbreed("Savon de Potasse buy") == ""
    assert verbreed("vegan sneakers") == ""
    assert verbreed("") == ""


def test_de_brede_stap_komt_voor_de_smalle_te_staan():
    """DE REDEN DAT DIT IN CODE ZIT EN NIET IN DE PROMPT. Een promptregel is een belofte: hij
    houdt zich er meestal aan, en precies de keer dat hij dat niet doet mislukt het onderzoek
    zonder dat iemand het merkt."""
    from nooch_village.skills_impl.zoekstrategie import _breed_voor_smal
    smal = {"bron": "web_zoek", "taal": "fr", "waarom": "x",
            "term": "Savon de Potasse fabricant fournisseur Europe savon liquide industriel"}
    uit = _breed_voor_smal([smal])
    assert len(uit) == 2
    assert uit[0]["bron"] == "web_zoek" and len(uit[0]["term"].split()) <= 4
    assert uit[0]["verbreed_van"] == smal["term"]
    assert uit[1] is smal, "de smalle stap blijft: hij was niet fout, hij was te vroeg"


def test_hooguit_een_brede_stap_erbij():
    """Twee brede stappen is dubbel werk, en de cap op het aantal stappen is er niet voor niets."""
    from nooch_village.skills_impl.zoekstrategie import _breed_voor_smal
    stappen = [{"bron": "web_zoek", "term": f"iets {i} fabricant fournisseur Europe industriel",
                "taal": "en", "waarom": "x"} for i in range(3)]
    uit = _breed_voor_smal(stappen)
    assert sum(1 for s in uit if s.get("verbreed_van")) == 1


def test_een_corpus_bron_wordt_niet_verbreed():
    """OpenAlex en de patentregisters hebben juist baat bij een precieze technische term. De
    breed-eerst-regel geldt voor het OPEN web, niet voor een corpus."""
    from nooch_village.skills_impl.zoekstrategie import _breed_voor_smal
    stappen = [{"bron": "openalex_evidence", "taal": "en", "waarom": "x",
                "term": "potassium soap manufacturer supplier Europe industrial"}]
    assert _breed_voor_smal(stappen) == stappen
