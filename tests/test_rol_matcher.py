"""De rol-matcher: deterministisch eerst, model alleen als dat leeg is.

GEMETEN OP PROD, 29 aug 2026. Op het doel "technische specs van alle materialen" zei het scherm
"geen rol heeft een passende skill", terwijl Scientist, Library en Copywriter voor de hand liggen.

DE DIAGNOSE WAS NIET WAT HIJ LEEK. De match was niet 'te letterlijk' — er werd helemaal geen tekst
vergeleken. `roles_for` matchte op de SKILL die de planner aan een stap hing, en die was bij alle
vijf de stappen `null` (de wizard stond open voor Copywriter; geen van diens vier skills dekt dit
werk). `nodig` was dus leeg en de functie viel er meteen uit. Er viel niets te matchen.

Daaronder ligt een tweede feit dat de skill-trede structureel dun maakt: van de 23 wakkere rollen
hebben er VIJF een skill — Scientist 12, Library 10, Trends & Competition 7, Compliance 6,
Copywriter 4. De andere achttien (Creator of Shoes, Website Developer, Community and Email, …)
hebben er nul. Een skill-match kan die per definitie nooit voorstellen, hoe goed hij ook is. Betere
skill-tagging maakt trede 1 sterker maar niet volledig: purpose en accountability zijn de enige
grond die ook een skill-loze rol heeft.
"""
from __future__ import annotations

from types import SimpleNamespace as N

from nooch_village.wizard import roles_for, roles_for_tekst


def _rec(rid, naam, skills=(), purpose="", accts=()):
    return N(id=rid, parent="c", archived=False, slaapt=False,
             definition=N(name=naam, skills=list(skills), purpose=purpose,
                          accountabilities=list(accts), domains=[]))


ROLLEN = [
    _rec("sci", "Scientist", ["openalex_evidence"], "onderbouwen met wetenschap",
         ["materiaalonderzoek doen"]),
    _rec("lib", "Library", ["curate"], "kennis ontsluiten", ["bijhouden wat we al weten"]),
    _rec("cw", "Copywriter", ["content_schrijven"], "helder schrijven", ["mails opstellen"]),
    _rec("dev", "Website Developer", [], "de site laten werken", ["de website onderhouden"]),
]
ST = N(all=lambda: ROLLEN)
SKILLS = lambda rec, ai: set(getattr(rec.definition, "skills", []) or [])


# ── Trede 1: de gratis opzoeking ───────────────────────────────────────────

def test_een_stap_met_een_skill_wordt_opgezocht_zonder_model():
    gebeld = []
    uit = roles_for([{"tekst": "zoek papers", "skill": "openalex_evidence"}],
                    records=ST, ai=None, skills_of=SKILLS,
                    reason_fn=lambda *a, **k: gebeld.append(1))
    assert [r["rol"] for r in uit] == ["sci"]
    assert gebeld == [], "het model werd gebeld terwijl de gratis weg antwoord had"
    assert uit[0]["grond"] == "heeft de skill die deze stap vraagt"


# ── Trede 2: alleen op leeg ────────────────────────────────────────────────

def test_zonder_skill_valt_hij_door_naar_het_model():
    """DE FIX. Precies het gemeten geval: vijf stappen met skill=null gaven een lege lijst."""
    def _model(prompt, **k):
        assert "Website Developer" in prompt and "materiaalonderzoek doen" in prompt
        return '{"toewijzingen":[{"stap":1,"rol":"sci"},{"stap":2,"rol":"dev"}]}'
    uit = roles_for([{"tekst": "verzamel materiaalspecs", "skill": None},
                     {"tekst": "zet ze op de site", "skill": None}],
                    records=ST, ai=None, skills_of=SKILLS, reason_fn=_model)
    assert {r["rol"] for r in uit} == {"sci", "dev"}
    assert all(r["grond"] == "purpose of accountability dekt dit" for r in uit)


def test_een_skill_loze_rol_kan_alleen_via_de_tweede_trede():
    """Website Developer heeft nul skills — op prod geldt dat voor 18 van de 23 wakkere rollen."""
    uit = roles_for([{"tekst": "zet de specs op de site", "skill": None}],
                    records=ST, ai=None, skills_of=SKILLS,
                    reason_fn=lambda *a, **k: '{"toewijzingen":[{"stap":1,"rol":"dev"}]}')
    assert [r["rol"] for r in uit] == ["dev"]


def test_het_model_wordt_niet_gebeld_als_de_opzoeking_iets_vond():
    """Alleen op leeg, niet bij elke open — anders kost elk scherm een call."""
    n = []
    roles_for([{"tekst": "a", "skill": "curate"}, {"tekst": "b", "skill": None}],
              records=ST, ai=None, skills_of=SKILLS, reason_fn=lambda *a, **k: n.append(1))
    assert n == []


# ── Fail-open en fail-closed ───────────────────────────────────────────────

def test_geen_model_geeft_een_lege_lijst_en_geen_gok():
    assert roles_for([{"tekst": "iets", "skill": None}], records=ST, ai=None, skills_of=SKILLS,
                     reason_fn=lambda *a, **k: None) == []


def test_een_verzonnen_rol_wordt_geweigerd():
    """Fail-closed op de inhoud: het antwoord wordt teruggecontroleerd tegen de kandidatenlijst."""
    uit = roles_for([{"tekst": "iets", "skill": None}], records=ST, ai=None, skills_of=SKILLS,
                    reason_fn=lambda *a, **k: '{"toewijzingen":[{"stap":1,"rol":"afdeling_x"}]}')
    assert uit == []


def test_een_slapende_rol_staat_niet_op_de_lijst():
    slaper = _rec("slaap", "Slaper", ["curate"])
    slaper.slaapt = True
    st = N(all=lambda: [*ROLLEN, slaper])
    gezien = {}

    def _m(prompt, **k):
        gezien["p"] = prompt
        return "{}"
    roles_for([{"tekst": "x", "skill": None}], records=st, ai=None, skills_of=SKILLS, reason_fn=_m)
    assert "Slaper" not in gezien["p"]


# ── Punt 3 later: dezelfde matcher, één niveau hoger ───────────────────────

def test_dezelfde_matcher_werkt_op_een_losse_spanning():
    """'Bij wie hoort deze spanning?' wordt geen tweede matcher: een spanning is hier een plan van
    één stap zonder skill, en valt dus meteen door naar de purpose-trede."""
    gezien = {}

    def _m(prompt, **k):
        gezien["p"] = prompt
        return '{"toewijzingen":[{"stap":1,"rol":"lib"}]}'
    uit = roles_for_tekst("wie weet wat we al hebben over zolen?",
                          records=ST, ai=None, skills_of=SKILLS, reason_fn=_m)
    assert [r["rol"] for r in uit] == ["lib"]
    assert "wie weet wat we al hebben over zolen?" in gezien["p"]


def test_de_rol_match_staat_op_de_goedkope_trede():
    """Triage: kleine gesloten kandidatenlijst, machinaal teruggecontroleerd, en een misser kost één
    klik. Anders dan `escalation_mens`, waar een verkeerde ontvanger via het spoor blijft plakken."""
    from nooch_village import llm_keuze as lk
    assert "rol_match" in lk.GOEDKOOP and "rol_match" not in lk.HOOG_INZET


def test_een_skill_die_iedereen_heeft_stelt_niet_iedereen_voor():
    """OP HET ECHTE SCHERM GEZIEN. De stap "escaleer onbevestigde claims naar compliance" stelde
    alle vijf de rollen-met-skills voor, want `escaleer` zit in élke skillset.

    Vijf suggesties waarvan er geen enkele iets zegt is erger dan geen suggestie: de lezer moet
    alsnog zelf kiezen, maar nu uit een lijst die zekerheid uitstraalt."""
    breed = [_rec("a", "A", ["escaleer", "curate"]), _rec("b", "B", ["escaleer"]),
             _rec("c", "C", ["escaleer"])]
    st = N(all=lambda: breed)
    # `escaleer` onderscheidt niets → door naar de purpose-trede
    uit = roles_for([{"tekst": "escaleer dit", "skill": "escaleer"}],
                    records=st, ai=None, skills_of=SKILLS,
                    reason_fn=lambda *a, **k: '{"toewijzingen":[{"stap":1,"rol":"a"}]}')
    assert [r["rol"] for r in uit] == ["a"]
    assert uit[0]["grond"] == "purpose of accountability dekt dit"
    # een skill die NIET iedereen heeft doet het gewoon deterministisch
    n = []
    uit2 = roles_for([{"tekst": "cureer dit", "skill": "curate"}],
                     records=st, ai=None, skills_of=SKILLS, reason_fn=lambda *a, **k: n.append(1))
    assert [r["rol"] for r in uit2] == ["a"] and n == []


def test_met_één_kandidaat_geldt_de_iedereen_regel_niet():
    """Met één rol is elke skill per definitie 'universeel' — dan zou de regel de enige echte match
    wegfilteren. Een testfixture met precies één skill-dragende rol wees dat aan."""
    st = N(all=lambda: [_rec("solo", "Solo", ["site_health"]), _rec("leeg", "Leeg", [])])
    n = []
    uit = roles_for([{"tekst": "site nakijken", "skill": "site_health"}],
                    records=st, ai=None, skills_of=SKILLS, reason_fn=lambda *a, **k: n.append(1))
    assert [r["rol"] for r in uit] == ["solo"] and n == []
