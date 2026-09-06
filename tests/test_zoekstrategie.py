"""Sid bepaalt eerst HOE hij zoekt, en dat plan wordt de volgende lijst.

AANLEIDING, gemeten op vijf onderzoeksprojecten uit juli: 25 items, 10 af, 15 gestrand. De meest
voorkomende melding was "geen werken gevonden voor deze term" — een Nederlandse term in een
Engelstalig corpus. Een onderzoeker had die vertaald; het dorp kon dat niet, want er zat geen stap
tussen 'kies een bron' en 'roep hem aan'.

Wat hieronder vastligt, in volgorde van belang:

1. **Eén ronde.** Een strategie mag één keer een volgende lijst opleveren. Zonder die rem kan het
   dorp blijven plannen zonder ooit te zoeken.
2. **De term blijft staan.** De hele stap bestaat om de term bij het corpus te laten passen;
   het herplan-blok schrijft daarom expliciet voor dat hij niet vertaald mag worden.
3. **Er draait niets zonder akkoord.** De tweede lijst is een voorstel, net als de eerste.
4. **Fail-closed.** Geen model of onzin terug geeft een fout, geen gegokte strategie.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.projects import ProjectLedger, plan_wacht_op_akkoord, uitvoerlijst
from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.zoekstrategie import (BRONNEN, _ONTKENNING, ZoekstrategieSkill,
                                                    _als_tekst, _bevestigend)

GOED = (
    '{"strategie": "Twee bronnen, Engelse termen, breed beginnen.",'
    ' "stappen": [{"bron": "openalex_evidence", "term": "vegan shoes", "taal": "en",'
    '              "waarom": "corpus is Engelstalig"},'
    '             {"bron": "epo_patents", "term": "plant-based footwear", "taal": "en"}],'
    ' "bij_nul_treffers": "Verbreed naar plant-based footwear."}'
)


def _skill(antwoord, monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: antwoord)
    return ZoekstrategieSkill()


# ── de skill zelf ────────────────────────────────────────────────────────────

def test_levert_stappen_met_bron_term_en_taal(monkeypatch):
    uit = _skill(GOED, monkeypatch).run({"vraag": "waarom groeien vegan schoenen"}, None)
    assert uit["ok"] is True
    assert [s["bron"] for s in uit["stappen"]] == ["openalex_evidence", "epo_patents"]
    assert uit["stappen"][0]["term"] == "vegan shoes"          # Engels, niet de Nederlandse vraag
    assert uit["stappen"][0]["taal"] == "en"


def test_de_wall_tekst_leest_als_een_plan(monkeypatch):
    """Elke regel is een handeling. Ook de laatste: die noemt de volgende term, niet het
    uitblijven van resultaat."""
    uit = _skill(GOED, monkeypatch).run({"vraag": "v"}, None)
    t = uit["text"]
    assert "Twee bronnen" in t
    assert 'openalex_evidence: “vegan shoes” (en)' in t
    assert "Next term if the first runs thin:" in t
    assert "Bij nul treffers" not in t                    # Engels, zoals de hele inhoudslaag


def test_verzonnen_bron_wordt_overgeslagen(monkeypatch):
    """Een bron die niet in de catalogus staat is geen stap; hem toch plannen levert een item op dat
    bij de uitvoering alsnog sterft."""
    antwoord = ('{"strategie": "x", "stappen": ['
                '{"bron": "chatgpt_vragen", "term": "iets", "taal": "en"},'
                '{"bron": "openalex_evidence", "term": "vegan shoes", "taal": "en"}]}')
    uit = _skill(antwoord, monkeypatch).run({"vraag": "v"}, None)
    assert [s["bron"] for s in uit["stappen"]] == ["openalex_evidence"]


def test_lege_term_telt_niet_als_stap(monkeypatch):
    antwoord = ('{"strategie": "x", "stappen": ['
                '{"bron": "openalex_evidence", "term": "  ", "taal": "en"}]}')
    uit = _skill(antwoord, monkeypatch).run({"vraag": "v"}, None)
    assert "error" in uit


def test_fail_closed_bij_onzin(monkeypatch):
    """Liever geen strategie dan een gegokte: een verzonnen strategie ziet er net zo uit als een
    goede, en je merkt het pas aan de lege resultaten drie stappen later."""
    for antwoord in (None, "", "geen json", '{"strategie": "x"}'):
        uit = _skill(antwoord, monkeypatch).run({"vraag": "v"}, None)
        assert "error" in uit, f"{antwoord!r} had een fout moeten geven"


def test_fail_closed_bij_een_stukke_llm(monkeypatch):
    import nooch_village.llm as llm

    def _stuk(*a, **k):
        raise RuntimeError("geen krediet")
    monkeypatch.setattr(llm, "reason", _stuk)
    assert "error" in ZoekstrategieSkill().run({"vraag": "v"}, None)


def test_vraag_is_verplicht():
    assert "error" in ZoekstrategieSkill().run({}, None)


def test_de_catalogus_noemt_de_taal_van_elk_corpus():
    """Dat is de hele reden dat deze stap bestaat; zonder die aantekening kiest het model blind."""
    assert "ENGLISH" in BRONNEN["openalex_evidence"]
    assert all(BRONNEN[b].strip() for b in BRONNEN)


def test_de_catalogus_zegt_wat_te_doen_en_niet_wat_te_laten():
    """De catalogus gaat als voorbeeldtekst de prompt in. Stond de taalval er negatief in ("a Dutch
    term finds nothing"), dan kwam hij er ook negatief uit — het model spiegelt de vorm die het
    krijgt. Dat is precies de reden dat deze regel hier staat en niet alleen in de prompt."""
    for bron, tekst in BRONNEN.items():
        assert not _ONTKENNING.search(tekst), f"{bron} beschrijft zichzelf negatief: {tekst!r}"


def test_alle_bronnen_bestaan_echt():
    from nooch_village.registry_factory import build_skill_registry
    bekend = set(build_skill_registry().names())
    onbekend = sorted(b for b in BRONNEN if b not in bekend)
    assert not onbekend, f"catalogus noemt niet-bestaande skills: {onbekend}"


# ── het plan zegt wat hij WEL doet ───────────────────────────────────────────

def test_een_ontkennende_reden_haalt_de_uitvoer_niet(monkeypatch):
    """DE REGEL VAN DIT BLOK. Sid schrijft op wat hij gaat doen. Wat hij niet doet is oneindig lang
    en nergens interessant, en het leest als een verantwoording tegenover een criticus in plaats van
    als een plan."""
    antwoord = ('{"strategie": "x", "stappen": ['
                '{"bron": "openalex_evidence", "term": "vegan shoes", "taal": "en",'
                ' "waarom": "niet \'vegan schoenen\', het corpus is Engelstalig"}]}')
    uit = _skill(antwoord, monkeypatch).run({"vraag": "v"}, None)
    assert uit["stappen"][0]["waarom"] == ""              # weg, niet herschreven
    assert uit["stappen"][0]["term"] == "vegan shoes"     # de stap zelf blijft volledig


def test_een_bevestigende_reden_blijft_gewoon_staan(monkeypatch):
    uit = _skill(GOED, monkeypatch).run({"vraag": "v"}, None)
    assert uit["stappen"][0]["waarom"] == "corpus is Engelstalig"
    assert "corpus is Engelstalig" in uit["text"]


@pytest.mark.parametrize("negatief", [
    "not the Dutch term", "no Dutch results here", "rather than the Dutch phrasing",
    "instead of 'vegan schoenen'", "geen Nederlandse term", "vermijd de Nederlandse term",
])
def test_bevestigend_herkent_de_gebruikelijke_ontkenningen(negatief):
    assert _bevestigend(negatief) == ""


@pytest.mark.parametrize("bevestigend", [
    "English-language corpus", "European register", "the words people use themselves",
    "peer-reviewed, so a claim can lean on it", "shows volume per country",
])
def test_bevestigend_laat_een_echte_reden_met_rust(bevestigend):
    assert _bevestigend(bevestigend) == bevestigend


def test_de_prompt_vraagt_om_een_bevestigend_plan(monkeypatch):
    """De vangrail is de bodem, niet de aanpak: als de prompt om ontkenningen vraagt, gooit de
    vangrail de halve uitvoer weg en houd je een kaal plan over. Vragen om het goede komt eerst."""
    gezien = {}

    import nooch_village.llm as llm
    def _vang(prompt, **kw):
        gezien["p"] = prompt
        return GOED
    monkeypatch.setattr(llm, "reason", _vang)
    ZoekstrategieSkill().run({"vraag": "v"}, None)

    p = gezien["p"]
    assert "WRITE THE PLAN AS WHAT YOU WILL DO" in p
    assert "affirmative" in p
    assert "next if the first one comes back thin" in p or "next if the first" in p


# ── het herplannen ───────────────────────────────────────────────────────────

@pytest.fixture()
def rol(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    rec = Record(id="sid", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="onderzoek", skills=["zoekstrategie"]),
                 source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=led, rugzakken={})
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx), led


def _resultaat():
    return {"ok": True, "stappen": [{"bron": "openalex_evidence", "term": "vegan shoes",
                                     "taal": "en", "waarom": "Engels corpus"}],
            "bij_nul_treffers": "verbreed naar plant-based footwear"}


def test_herplan_maakt_een_tweede_lijst_die_op_akkoord_wacht(rol, monkeypatch):
    inw, led = rol
    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: {"items": [
                            {"text": "Search OpenAlex for 'vegan shoes'",
                             "skill": "openalex_evidence", "payload": {"term": "vegan shoes"}}]})
    pid = led.create("sid", "waarom groeien vegan schoenen", "role", status="queued")
    cl = led.checklist_add(pid, title="Strategie")
    led.check_add(pid, cl["id"], "bepaal de strategie", skill="zoekstrategie")
    item = led.get(pid)["checklists"][0]["items"][0]

    inw._herplan_na_strategie(pid, item, _resultaat(), led)

    cls = led.get(pid)["checklists"]
    assert len(cls) == 2
    nieuw = cls[1]
    assert nieuw.get("herplan_van") == item["id"]
    assert nieuw.get("akkoord") is False                  # wacht op go ahead, net als elk plan
    assert plan_wacht_op_akkoord(nieuw) is True
    assert uitvoerlijst(led.get(pid))["id"] == nieuw["id"]   # de rol werkt nu déze lijst


def test_maar_een_ronde(rol, monkeypatch):
    """DE KERNTEST. Zonder deze rem kan een strategie een lijst opleveren die weer een strategie
    bevat, en plant het dorp door zonder ooit iets te zoeken."""
    inw, led = rol
    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: {"items": [{"text": "x", "skill": "openalex_evidence",
                                                             "payload": {"term": "t"}}]})
    pid = led.create("sid", "doel", "role", status="queued")
    cl = led.checklist_add(pid, title="Strategie")
    led.check_add(pid, cl["id"], "strategie", skill="zoekstrategie")
    item = led.get(pid)["checklists"][0]["items"][0]

    inw._herplan_na_strategie(pid, item, _resultaat(), led)
    inw._herplan_na_strategie(pid, item, _resultaat(), led)
    inw._herplan_na_strategie(pid, item, _resultaat(), led)
    assert len(led.get(pid)["checklists"]) == 2, "meer dan één herplan-ronde"


def test_het_plan_krijgt_de_term_mee_met_verbod_om_te_vertalen(rol, monkeypatch):
    """De hele stap bestaat om de term bij het corpus te laten passen. Zou de planner hem alsnog
    'verbeteren', dan is de fout van juli terug."""
    inw, led = rol
    gezien = {}
    monkeypatch.setattr(Inhabitant, "_plan_checklist",
                        lambda self, goal, **kw: gezien.setdefault("d", kw.get("description")) and None
                        or {"items": [{"text": "x", "skill": "openalex_evidence", "payload": {}}]})
    pid = led.create("sid", "doel", "role", status="queued")
    cl = led.checklist_add(pid, title="Strategie")
    led.check_add(pid, cl["id"], "strategie", skill="zoekstrategie")
    inw._herplan_na_strategie(pid, led.get(pid)["checklists"][0]["items"][0], _resultaat(), led)

    d = gezien["d"]
    assert 'search term "vegan shoes"' in d
    assert "do not translate" in d
    assert "Next term if the first runs thin: verbreed naar plant-based footwear" in d


def test_zonder_stappen_gebeurt_er_niets(rol):
    """Herplannen is een dienst, geen voorwaarde: de strategie staat toch op de wall."""
    inw, led = rol
    pid = led.create("sid", "doel", "role", status="queued")
    cl = led.checklist_add(pid, title="Strategie")
    led.check_add(pid, cl["id"], "strategie", skill="zoekstrategie")
    item = led.get(pid)["checklists"][0]["items"][0]
    inw._herplan_na_strategie(pid, item, {"ok": True, "stappen": []}, led)
    assert len(led.get(pid)["checklists"]) == 1


def test_mislukt_plan_laat_het_project_heel(rol, monkeypatch):
    inw, led = rol
    monkeypatch.setattr(Inhabitant, "_plan_checklist", lambda self, goal, **kw: None)
    pid = led.create("sid", "doel", "role", status="queued")
    cl = led.checklist_add(pid, title="Strategie")
    led.check_add(pid, cl["id"], "strategie", skill="zoekstrategie")
    item = led.get(pid)["checklists"][0]["items"][0]
    inw._herplan_na_strategie(pid, item, _resultaat(), led)
    assert len(led.get(pid)["checklists"]) == 1           # geen halve lijst achtergelaten


def test_als_tekst_zonder_strategie_of_nulplan():
    assert _als_tekst("", [{"bron": "b", "term": "t", "taal": "en"}], "") == '• b: “t” (en)'
