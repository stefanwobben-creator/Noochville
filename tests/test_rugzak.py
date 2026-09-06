"""Rugzakken: cirkelbrede capaciteit, zonder dat bevoegdheid meeverhuist.

De belofte van dit bestand in één zin: een rugzak verruimt wat een rol MAG PAKKEN, en verandert
niets aan waar een rol OVER GAAT. Drie dingen bewaken dat, en alle drie staan hieronder als test:

1. De domeinpoort blijft absoluut. Een beslis-skill in een rugzak is nog steeds geweigerd voor
   iedereen behalve de domeinhouder — de poort draait ná de rugzak, niet ervoor.
2. De puls verandert niet. `capabilities()` (wat een rol uit eigen beweging draait) blijft op het
   DNA staan. Zou een rugzak dat verruimen, dan ging elke rol de claims-scan draaien.
3. Zonder bestand gedraagt het dorp zich exact als voorheen. Het DNA is de vloer.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import rugzak
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.skills import Skill, SkillRegistry


# ── gereedschap ──────────────────────────────────────────────────────────────

class _Skill(Skill):
    cost = "free"

    def __init__(self, naam, desc="", insch=""):
        self.name = naam
        self.description = desc
        self.input_schema = insch

    def run(self, payload, context):
        return {"ok": True}


def _registry(*namen):
    reg = SkillRegistry()
    for n in namen:
        reg.register(_Skill(n, desc=f"doet {n}", insch=f"{n}_veld: str"))
    return reg


RUGZAKKEN = {
    "buiten": {"stagiair": "Sid", "wat": "wat er buiten gebeurt",
               "skills": ["community_listening", "haal_pagina"]},
    "basis": {"stagiair": "", "wat": "leidingwerk",
              "skills": ["weten_we_dit_al", "escaleer"]},
}


def _inwoner(*, dna_skills=(), domains=(), rugzakken=None, reg=None, rid="rol_a"):
    rec = Record(id=rid, type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test", skills=list(dna_skills),
                                           domains=list(domains)),
                 source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"},
                          rugzakken=rugzakken if rugzakken is not None else {})
    return Inhabitant(rec, EventBus(name="test"), reg or _registry(), ctx)


# ── 1. laden ─────────────────────────────────────────────────────────────────

def test_laad_zonder_bestand_is_leeg(tmp_path):
    assert rugzak.laad(str(tmp_path)) == {}


def test_laad_slaat_commentaarsleutels_over(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "rugzakken.json").write_text(json.dumps({
        "_wat": "uitleg die naast de data staat",
        "_hoe": ["meer uitleg"],
        "buiten": {"stagiair": "Sid", "wat": "x", "skills": ["a", "b"]},
    }), encoding="utf-8")
    uit = rugzak.laad(str(tmp_path))
    assert set(uit) == {"buiten"}
    assert uit["buiten"]["skills"] == ["a", "b"]
    assert uit["buiten"]["stagiair"] == "Sid"


def test_laad_is_failsoft_bij_stuk_bestand(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "rugzakken.json").write_text("{ dit is geen json", encoding="utf-8")
    assert rugzak.laad(str(tmp_path)) == {}          # geen exception, dorp draait door


def test_echte_rugzakken_json_laadt_en_verwijst_alleen_naar_bestaande_skills():
    """De meegeleverde config moet kloppen: elke genoemde skill bestaat echt in de registry.

    Zonder deze test is een typefout in het JSON-bestand een middel dat stil nooit wordt
    aangeboden — precies de ghost-klasse die `grants.py` voor rol-DNA al afvangt."""
    import os
    from nooch_village.registry_factory import build_skill_registry
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zakken = rugzak.laad(root)
    assert zakken, "config/rugzakken.json ontbreekt of is leeg"
    bekend = set(build_skill_registry().names())
    onbekend = sorted(rugzak.alle_skills(zakken) - bekend)
    assert not onbekend, f"rugzakken.json noemt skills die niet in de registry staan: {onbekend}"


def test_echte_rugzakken_bevatten_geen_beslis_skill():
    """Een skill die in een domein BESLIST hoort niet in gedeelde capaciteit.

    De domeinpoort weigert hem daarna alsnog (dat bewijst een test verderop), maar hem aanbieden
    en dan weigeren is een omweg die de mens als 'er gebeurt niets' ziet."""
    import os
    from nooch_village import skill_meta
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fout = sorted(s for s in rugzak.alle_skills(rugzak.laad(root))
                  if skill_meta.schrijft_in_domein(s))
    assert not fout, f"beslis-skills horen niet in een rugzak: {fout}"


# ── 2. de effectieve set ─────────────────────────────────────────────────────

def test_zonder_rugzakken_verandert_er_niets():
    inw = _inwoner(dna_skills=["site_health"], rugzakken={})
    assert inw.effective_skills() == {"site_health"}


def test_rugzak_verruimt_de_effectieve_set():
    inw = _inwoner(dna_skills=["site_health"], rugzakken=RUGZAKKEN)
    assert inw.effective_skills() == {
        "site_health", "community_listening", "haal_pagina", "weten_we_dit_al", "escaleer"}


def test_dna_is_de_vloer_een_rugzak_neemt_nooit_iets_af():
    """Een skill in het DNA die in geen rugzak zit blijft van deze rol."""
    inw = _inwoner(dna_skills=["gsc_report"], rugzakken=RUGZAKKEN)
    assert "gsc_report" in inw.effective_skills()


def test_context_zonder_rugzakken_attribuut_werkt(monkeypatch):
    """Elke oudere caller (en de meeste tests) geeft een context zonder dit veld mee."""
    rec = Record(id="rol_x", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["site_health"]), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"})     # géén rugzakken
    inw = Inhabitant(rec, EventBus(name="test"), _registry(), ctx)
    assert inw.effective_skills() == {"site_health"}


# ── 3. de domeinpoort blijft absoluut ────────────────────────────────────────

def test_rugzak_omzeilt_de_domeinpoort_niet(monkeypatch):
    """DE KERNTEST. Zet een beslis-skill in een rugzak en probeer hem te voeren als een rol die
    het domein niet houdt. De poort hoort hem alsnog te weigeren.

    Dit is het verschil tussen capaciteit (deelbaar) en bevoegdheid (niet deelbaar). Valt deze
    test om, dan heeft de rugzak-laag stilletjes mandaat verplaatst."""
    from nooch_village import skill_meta
    monkeypatch.setitem(skill_meta.META, "beslis_skill",
                        {"schrijft_in_domein": "bibliotheek", "zwaar": True})
    zakken = {"fout": {"stagiair": "", "wat": "per ongeluk", "skills": ["beslis_skill"]}}

    buiten = _inwoner(domains=["website"], rugzakken=zakken, reg=_registry("beslis_skill"))
    assert "beslis_skill" in buiten.effective_skills()          # bereikbaar…
    fout = buiten._weiger("beslis_skill")
    assert fout and "bibliotheek" in fout                       # …maar geweigerd

    houder = _inwoner(domains=["bibliotheek"], rugzakken=zakken,
                      reg=_registry("beslis_skill"), rid="rol_bib")
    assert houder._weiger("beslis_skill") is None               # de houder mag wel


def test_planner_catalogus_toont_geen_geweigerde_skill(monkeypatch):
    """Wat de poort weigert komt niet in de prompt: niet plannen is beter dan plannen en sterven."""
    from nooch_village import skill_meta
    monkeypatch.setitem(skill_meta.META, "beslis_skill",
                        {"schrijft_in_domein": "bibliotheek", "zwaar": True})
    zakken = {"fout": {"stagiair": "", "wat": "per ongeluk",
                       "skills": ["beslis_skill", "haal_pagina"]}}
    inw = _inwoner(domains=["website"], rugzakken=zakken,
                   reg=_registry("beslis_skill", "haal_pagina"))
    toegestaan = sorted(s for s in inw.effective_skills() if not inw._domein_weigering(s))
    tekst = rugzak.catalogus(zakken, toegestaan, inw.registry)
    assert "haal_pagina" in tekst
    assert "beslis_skill" not in tekst


# ── 4. de puls verandert NIET ────────────────────────────────────────────────

def test_rugzak_verruimt_de_puls_niet():
    """`capabilities()` stuurt wat een rol uit EIGEN BEWEGING op de dagpuls draait. Zou een rugzak
    dat verruimen, dan draaide elke rol de claims-scan — precies waar `_run_pulse_skills` in zijn
    eigen commentaar voor waarschuwt ('de Copywriter hóórt geen claims-scan te draaien')."""
    inw = _inwoner(dna_skills=["site_health"], rugzakken=RUGZAKKEN)
    assert inw.capabilities() == ["site_health"]
    assert "community_listening" not in inw.capabilities()


def test_pulse_skill_uit_een_rugzak_draait_niet_vanzelf():
    """Zelfde regel, nu langs het pad dat er echt toe doet: de puls-lus zelf."""
    zakken = {"x": {"stagiair": "", "wat": "", "skills": ["claims_site_scan"]}}
    inw = _inwoner(dna_skills=[], rugzakken=zakken, reg=_registry("claims_site_scan"))
    inw.context.settings["pulse_skills"] = "claims_site_scan"
    gedraaid = []
    inw.use_skill = lambda naam, payload: gedraaid.append(naam) or {"ok": True}
    inw._run_pulse_skills(None)
    assert gedraaid == [], "een rugzak-skill mag niet uit zichzelf op de puls gaan draaien"


# ── 5. de catalogus ──────────────────────────────────────────────────────────

def test_catalogus_groepeert_per_rugzak():
    reg = _registry("community_listening", "haal_pagina", "weten_we_dit_al", "escaleer")
    tekst = rugzak.catalogus(RUGZAKKEN, ["community_listening", "weten_we_dit_al"], reg)
    assert "[buiten] wat er buiten gebeurt" in tekst
    assert "[basis] leidingwerk" in tekst
    assert "community_listening" in tekst and "weten_we_dit_al" in tekst
    # alleen wat is meegegeven; niet de rest van de rugzak
    assert "haal_pagina" not in tekst


def test_catalogus_zet_dna_only_skills_onder_eigen_gereedschap():
    """Een middel dat in geen rugzak zit moet kiesbaar blijven, anders verliest een rol bij het
    invoeren van rugzakken juist zijn eigen gegrante gereedschap."""
    reg = _registry("community_listening", "materiaal_shortlist")
    tekst = rugzak.catalogus(RUGZAKKEN, ["community_listening", "materiaal_shortlist"], reg)
    assert "[eigen gereedschap]" in tekst
    assert "materiaal_shortlist" in tekst


def test_catalogus_zonder_skills():
    assert rugzak.catalogus(RUGZAKKEN, [], _registry()) == "(no skills)"


def test_catalogus_toont_input_schema():
    reg = _registry("haal_pagina")
    tekst = rugzak.catalogus(RUGZAKKEN, ["haal_pagina"], reg)
    assert "input: haal_pagina_veld: str" in tekst


def test_rugzak_van():
    assert rugzak.rugzak_van(RUGZAKKEN, "haal_pagina") == "buiten"
    assert rugzak.rugzak_van(RUGZAKKEN, "escaleer") == "basis"
    assert rugzak.rugzak_van(RUGZAKKEN, "bestaat_niet") == ""
