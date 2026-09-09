"""De leerlus in het pad dat de projecten écht plant, en een payload-poort die iets tegenhoudt.

HET GEVAL, 8 september 2026, tweede ronde. Na de eerste reparatie liep hetzelfde onderzoek opnieuw
vast, en de reden was dat ik de verkeerde component had verbeterd:

  `skills_impl/zoekstrategie`   ← daar zette ik breed-voor-smal en het lezen van de lessen in
  `Inhabitant._plan_checklist`  ← DIT schrijft de zoekopdrachten van een project, en riep die
                                   skill niet eens aan

Het tweede plan stapelde dus opnieuw: `kaliumzeep fabrikant Europages Kompass site:europages.nl OR
site:kompass.com` — vrije tekst plus twee site-filters plus een OR. Dat kwam LEEG terug, en juist
die stap moest de registers met telefoonnummers opleveren. Op het bord stond hij doorgestreept
naast twee die wél iets vonden, niet te onderscheiden.

En stap vier droeg `{"url": "PLACEHOLDER — to be filled with each candidate URL found in prior
steps"}`. De planner wist dat hij de URL niet kon weten (die komt uit een eerdere stap, en het
planformaat kent die afhankelijkheid niet) en verzon een plaatshouder. Beide poorten lieten dat
door: `_missing_required` kijkt of het VELD er is, en `validate_payload` bestaat wel als methode
maar geeft in de basisklasse `[]` terug — van de vijftig skills implementeerden er DRIE een eigen
versie. Er stond iemand bij de deur die nooit iets tegenhield.
"""
from __future__ import annotations

import re

from nooch_village.zoektermen import (BREED_MAX_WOORDEN, gestapeld, verbreed,
                                      verbreed_planitems)


# ── 1. Eén huis voor de breed-eerst-regel ────────────────────────────────────

def test_de_regel_woont_op_een_plek():
    """`zoekstrategie` mag geen eigen kopie meer hebben: die divergentie IS de bug van vandaag."""
    from nooch_village.skills_impl import zoekstrategie as zs
    assert zs.verbreed is verbreed, "zoekstrategie hoort af te leiden, niet over te typen"


def test_de_twee_echte_mislukte_termen():
    """Niet verzonnen voorbeelden: dit zijn de termen die in productie hebben gefaald."""
    eerste = verbreed("Savon de Potasse fabricant fournisseur Europe savon liquide potassique "
                      "industriel")
    assert eerste and len(eerste.split()) <= BREED_MAX_WOORDEN - 1
    assert "potasse" in eerste.lower()
    for eis in ("fabricant", "fournisseur", "Europe", "industriel"):
        assert eis.lower() not in eerste.lower(), eis

    tweede = verbreed("kaliumzeep fabrikant Europages Kompass site:europages.nl OR site:kompass.com")
    assert "kaliumzeep" in tweede.lower()
    assert "kompass" in tweede.lower(), "de registernaam is juist het NUTTIGE deel"
    assert "site:" not in tweede and " or " not in f" {tweede.lower()} "
    assert "europages.nl" not in tweede, ("een kaal domein is het restant van een filter; hij "
                                          "stond dan twee keer in de term")


def test_een_goede_term_blijft_ongemoeid():
    """Anders verbreedt hij een werkende zoekopdracht kapot, en dat is de tegenovergestelde fout."""
    for goed in ("Savon de Potasse buy", "vegan sneakers", "kaliumzeep kopen", ""):
        assert verbreed(goed) == "", goed


# ── 2. En hij bereikt nu het planner-pad ─────────────────────────────────────

def _item(term, skill="web_zoek"):
    return {"text": "iets zoeken", "skill": skill, "payload": {"term": term, "aantal": 15}}


def test_de_brede_stap_komt_voor_de_smalle_in_een_PLAN():
    """DE KERNTEST OP DE HERHALING. De vorige versie deed dit alleen voor `zoekstrategie`-stappen,
    en dat pad wordt bij het plannen van een project niet gebruikt."""
    smal = _item("kaliumzeep fabrikant Europages Kompass site:europages.nl OR site:kompass.com")
    uit = verbreed_planitems([smal])
    assert len(uit) == 2
    assert uit[0]["skill"] == "web_zoek"
    assert len(uit[0]["payload"]["term"].split()) <= BREED_MAX_WOORDEN - 1
    assert uit[0]["verbreed_van"] == smal["payload"]["term"]
    assert uit[0]["payload"]["aantal"] == 15, "de rest van de payload gaat mee"
    assert uit[1] is smal, "de smalle stap blijft: hij was niet fout, hij was te vroeg"


def test_hooguit_een_brede_stap_per_plan():
    uit = verbreed_planitems([_item(f"iets {i} fabrikant Europa industrieel bulk") for i in range(3)])
    assert sum(1 for x in uit if x.get("verbreed_van")) == 1


def test_een_corpus_skill_wordt_niet_verbreed():
    """OpenAlex en de patentregisters hebben juist baat bij een precieze technische term."""
    stappen = [_item("potassium soap manufacturer supplier Europe industrial", "openalex_evidence")]
    assert verbreed_planitems(stappen) == stappen


def _roept_aan(fn, naam: str) -> bool:
    """Wordt `naam` ECHT aangeroepen in deze functie?

    Bewust AST en geen `in bron`. Bij het schrijven van deze test bewees ik hem door de aanroep uit
    te commentariëren, en hij bleef groen: de naam staat dan nog steeds in de brontekst. Een test
    die code niet van commentaar kan onderscheiden meet niets — precies de fout die deze ochtend
    twee ratchets kostte, nu in de test die de reparatie moest bewaken."""
    import ast
    import inspect
    import textwrap
    boom = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    return any(isinstance(n, ast.Call)
               and (getattr(n.func, "id", None) == naam or getattr(n.func, "attr", None) == naam)
               for n in ast.walk(boom))


def test_de_planner_leest_de_lessen_en_verbreedt():
    """Zonder deze twee schakels is een les vastleggen zinloos voor het pad dat er echt toe doet:
    `_plan_checklist` schrijft de zoekopdrachten van een project, en kende de leerlus niet."""
    import inspect

    from nooch_village.inhabitant import Inhabitant
    assert "lessen_section" in inspect.getsource(Inhabitant._plan_checklist), \
        "de planner-prompt mist het lessen-blok"
    assert _roept_aan(Inhabitant._plan_checklist, "_lessen"), \
        "de planner haalt de lessen niet op"
    assert _roept_aan(Inhabitant.prepare_project, "verbreed_planitems"), \
        "de planner past de verbreding niet toe op zijn eigen items"


# ── 3. De poort houdt nu iets tegen ──────────────────────────────────────────

class _Ctx:
    data_dir = "."
    settings: dict = {}


def test_een_placeholder_is_geen_url():
    """DE BUG. Deze exacte string stond in productie en werd uitvoerbaar bevonden."""
    from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill
    redenen = HaalPaginaSkill().validate_payload(
        {"url": "PLACEHOLDER — to be filled with each candidate URL found in prior steps"}, _Ctx())
    assert redenen, "een plaatshouder hoort een reden op te leveren"
    assert "geen adres" in redenen[0]


def test_een_echte_url_komt_er_gewoon_door():
    from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill
    sk = HaalPaginaSkill()
    for goed in ("https://europages.nl/x", "http://voorbeeld.nl"):
        assert sk.validate_payload({"url": goed}, _Ctx()) == [], goed
    # Een ONTBREKENDE url is niet deze poort zijn werk: dat dekt `required_payload` al, en twee
    # poorten die hetzelfde melden geven twee redenen voor één probleem.
    assert sk.validate_payload({}, _Ctx()) == []


def test_gestapelde_site_filters_worden_geweigerd():
    """De term die leeg terugkwam op precies de stap die telefoonnummers moest opleveren."""
    from nooch_village.skills_impl.web_zoek import WebZoekSkill
    redenen = WebZoekSkill().validate_payload(
        {"term": "kaliumzeep fabrikant Europages Kompass site:europages.nl OR site:kompass.com"},
        _Ctx())
    assert redenen and "site:" in redenen[0]


def test_een_enkel_site_filter_mag():
    """Eén `site:` is een precisie-instrument. Zou de poort dat ook weigeren, dan verliest hij een
    legitiem gereedschap en leert iemand hem negeren."""
    from nooch_village.skills_impl.web_zoek import WebZoekSkill
    sk = WebZoekSkill()
    assert sk.validate_payload({"term": "kaliumzeep site:kompass.com"}, _Ctx()) == []
    assert sk.validate_payload({"term": "kaliumzeep kopen"}, _Ctx()) == []


# ── 4. De ratchet: een verwijzend verplicht veld eist een echte poort ────────

#: Verplichte payload-velden die naar iets BUITEN de payload wijzen: een adres, een id, een rol.
#: Precies de velden waar een planner een plaatshouder voor kan verzinnen.
#:
#: `kaart` stond hier eerst ook in, en dat was een VALS ALARM: `onderzoeksvraag` verwacht daar een
#: dict `{"word": ..., "claim": ...}` met inline data, geen verwijzing naar iets dat elders bestaat.
#: De naam klonk als een referentie; de code zegt van niet. Gemeten in plaats van aangenomen.
_VERWIJZEND = re.compile(r"^(url|urls|link|links|id|.*_id|ref|refs|rol|.*_rol|role)$", re.I)

#: Bewuste uitzonderingen, mét reden. Leeg houden is het doel.
_MAG_ZONDER_POORT: dict[str, str] = {}


def _velden(req) -> list[str]:
    uit = []
    for f in (req or ()):
        uit.extend(f if isinstance(f, (list, tuple)) else [f])
    return [str(x) for x in uit]


def test_een_skill_met_een_verwijzend_verplicht_veld_heeft_een_eigen_poort():
    """WAAROM DEZE RATCHET BESTAAT. `validate_payload` staat op de basisklasse en geeft daar `[]`
    terug. `hasattr` is dus altijd waar en meet niets — dat was letterlijk de meetfout in mijn
    eigen diagnose-script. Van de vijftig skills implementeerden er drie een eigen versie, en
    `haal_pagina` (die een URL verplicht stelt) hoorde daar niet bij.

    De regel: stel je een veld verplicht dat naar iets BUITEN de payload wijst, dan moet je ook
    kunnen zeggen wanneer die verwijzing onzin is. Anders is het een poort die openstaat."""
    from nooch_village.registry_factory import build_skill_registry
    from nooch_village.skills import Skill

    open_poorten = []
    for sk in build_skill_registry().all():
        verwijzend = [f for f in _velden(getattr(sk, "required_payload", ())) if _VERWIJZEND.match(f)]
        if not verwijzend or sk.name in _MAG_ZONDER_POORT:
            continue
        if type(sk).validate_payload is Skill.validate_payload:
            open_poorten.append(f"{sk.name} (verplicht: {', '.join(verwijzend)})")
    assert not open_poorten, (
        "deze skills stellen een verwijzend veld verplicht maar erven de lege `validate_payload`, "
        "dus een verzonnen verwijzing wordt 'uitvoerbaar' bevonden en sterft pas live: "
        + ", ".join(sorted(open_poorten)) +
        ". Schrijf een eigen validate_payload, of zet hem in _MAG_ZONDER_POORT met een reden.")


def test_de_ratchet_ziet_een_echte_overtreder():
    """Bewijs dat hij bijt: een verzonnen skill met een verplichte `url` en zonder eigen poort."""
    from nooch_village.skills import Skill

    class _Slordig(Skill):
        name = "slordig"
        description = "verzonnen, alleen voor deze test"
        required_payload = ("url",)

        def run(self, payload, context=None):
            return {}

    sk = _Slordig()
    verwijzend = [f for f in _velden(sk.required_payload) if _VERWIJZEND.match(f)]
    assert verwijzend == ["url"]
    assert type(sk).validate_payload is Skill.validate_payload, "hij erft de lege basis"


# ── 5. Afgevinkt is niet hetzelfde als beantwoord ────────────────────────────

def test_een_leeg_item_zegt_op_het_scherm_dat_het_geen_antwoord_is():
    """De uitvoerlaag legt dit zorgvuldig vast (`set_item_leeg`, mét reden en bron) en de weergave
    gooide het weg: `if state == "done": return ""`. Op het bord stond de leeg-teruggekomen
    zoekopdracht doorgestreept naast twee die wél iets vonden."""
    from nooch_village.views.checklists import _cl_item_meta
    leeg = {"id": "a", "done": True, "leeg": True, "leeg_bron": "gemeld",
            "leeg_reden": "geen organische treffers"}
    html = _cl_item_meta("done", "web_zoek", leeg)
    assert "no answer" in html and "geen organische treffers" in html
    assert "📭" in html, "'gemeld' is een ANTWOORD (de bron zei zelf: niets gevonden)"

    gat = {**leeg, "leeg_bron": "geen_inhoud"}
    assert "🕳" in _cl_item_meta("done", "web_zoek", gat), "'geen_inhoud' is een GAT, geen antwoord"


def test_een_gewoon_afgerond_item_blijft_stil():
    """Zou elk afgevinkt item een regel krijgen, dan is de melding ruis en leert niemand hem lezen."""
    from nooch_village.views.checklists import _cl_item_meta
    assert _cl_item_meta("done", "web_zoek", {"id": "a", "done": True}) == ""


def test_een_verzonnen_ontvanger_wordt_geweigerd():
    """De tweede vondst van de ratchet, op zijn eerste run. `projectverzoek` stelt `naar_rol`
    verplicht en controleerde niet of die rol bestaat: werk naar een verzonnen ontvanger faalt dan
    live, het item blijft open, en het bord blijft "de rol werkt eraan" tonen."""
    from nooch_village.skills_impl.projectverzoek import ProjectverzoekSkill

    class _Recs:
        def __init__(self, bestaat):
            self._bestaat = bestaat

        def get(self, rid):
            return object() if rid in self._bestaat else None

    class _C:
        records = _Recs({"compliance"})

    sk = ProjectverzoekSkill()
    redenen = sk.validate_payload({"naar_rol": "rol_die_niet_bestaat", "titel": "x"}, _C())
    # Toets op wat de reden moet DOEN (de verzonnen id noemen), niet op de exacte formulering:
    # een test die de zin overtypt breekt bij elke herformulering en zegt dan niets over gedrag.
    assert redenen and "rol_die_niet_bestaat" in redenen[0]
    assert sk.validate_payload({"naar_rol": "compliance", "titel": "x"}, _C()) == []

    # Geen store = geen oordeel. Niet-weten is geen bezwaar, anders blokkeert een ontbrekende
    # injectie elk projectverzoek.
    class _Leeg:
        records = None
    assert sk.validate_payload({"naar_rol": "wat dan ook"}, _Leeg()) == []
