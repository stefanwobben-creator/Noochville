"""Missie-critic: de poort vóór 'klaar voor review'.

De review-gate liet elk project door zodra de vakjes waren afgevinkt. Dat is een telling, geen
oordeel — een leeg rapport, een rapport dat de vraag niet beantwoordt en een rapport dat prachtig
maar off-mission is haalden alle drie precies dezelfde schone `awaiting_review`.

De guards die de opdracht vraagt staan onderaan:
  - een rapport dat de done-when niet beantwoordt of off-mission is, bereikt geen SCHONE review;
  - een leeg project wordt gevlagd.

Cross-rol-review zit hier BEWUST niet in: dat zette bij elke afwijzing drie andere rollen aan het
werk, en dat is geen review meer maar een lawine. Selectief routeren komt later, als de
critic-cijfers laten zien waar een tweede blik echt nodig is.

En de regel die eronder ligt: nooit stil doorlaten, maar ook nooit stil vastzetten. Een project
eeuwig tegenhouden is erger dan een gemarkeerd project — dan verdwijnt het uit beeld.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village import missie_critic as mc
from nooch_village.deliverable_store import DeliverableStore
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.projects import ProjectLedger
from nooch_village.skills import Skill, SkillRegistry

TODAY = "2026-08-11"
_REASON = "nooch_village.llm.reason"

# Een rapport dat de vier assen haalt: lang genoeg, koppen per taak, raakt de done-when, en zit vol
# strategie-thema's uit de grondwet (plasticvrij, vegan, transparantie).
GOED_DOC = ("# Rapport\n\n"
            "## Onderzoek plasticvrije materialen voor de zool\n"
            "We vergeleken drie plasticvrije, plantaardige materialen voor de zool. "
            "De transparantie over herkomst is bij alle drie geborgd; leer valt af. " * 6
            + "\n\n## Conclusie\nDe zool kan plasticvrij en vegan.\n")


class _Skill(Skill):
    name = "openalex_evidence"
    description = "fake"

    def __init__(self, leeg=False):
        self._leeg = leeg

    def run(self, payload, context):
        if self._leeg:
            return {"no_data": True, "reason": "niets gevonden"}
        return {"hits": [{"title": "Study"}], "total": 1}


def _stores(tmp_path):
    return (ProjectLedger(str(tmp_path / "projects.json")),
            DeliverableStore(str(tmp_path / "deliverables.json")),
            ProjectDocStore(str(tmp_path)))


def _inh(tmp_path, ledger, ds, docs, *, leeg=False):
    reg = SkillRegistry()
    reg.register(_Skill(leeg=leeg))
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          projects=ledger, deliverables=ds, project_docs=docs, personas=None,
                          records=None)
    rec = Record(id="sid", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="w", accountabilities=["research"], domains=[],
                                           skills=["openalex_evidence"]), source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _reason_mock(tekst):
    def _fake(prompt, *, return_tier=False, **kw):
        return (tekst, "mistral:x") if return_tier else tekst
    return _fake


def _cl(items):
    return {"id": "c1", "items": [{"id": f"i{n}", "text": t, "done": True, **extra}
                                  for n, (t, extra) in enumerate(items)]}


# ── De vier assen, los ───────────────────────────────────────────────────────

def test_substantieel_vangt_het_lege_rapport():
    ok, waarom = mc._substantieel("kort", ["iets"], _cl([("taak", {})]))
    assert not ok and "geen rapport" in waarom


def test_substantieel_vangt_een_rapport_zonder_enige_deliverable():
    ok, waarom = mc._substantieel("x" * 900, [], _cl([("taak", {})]))
    assert not ok and "rust nergens op" in waarom


def test_substantieel_vangt_het_project_waarin_alles_leegliep():
    """Alle taken uitgevoerd, geen enkele leverde iets op. Van buiten een afgerond project, van
    binnen een stapel kennisgaten — de duurste vorm van valse voltooiing."""
    cl = _cl([("taak a", {"leeg": True}), ("taak b", {"leeg": True})])
    ok, waarom = mc._substantieel("x" * 900, ["iets"], cl)
    assert not ok and "alleen kennisgaten" in waarom


def test_beantwoordt_eist_een_kop_per_taak():
    cl = _cl([("Onderzoek plasticvrije zolen", {}), ("Vergelijk leveranciers in Portugal", {})])
    doc = "# R\n\n## Onderzoek plasticvrije zolen\ntekst\n"          # tweede taak ontbreekt
    ok, waarom = mc._beantwoordt(doc, {}, cl)
    assert not ok and "eigen kop" in waarom


def test_beantwoordt_vangt_een_rapport_dat_de_done_when_mist():
    cl = _cl([("Onderzoek plasticvrije zolen", {})])
    doc = "# R\n\n## Onderzoek plasticvrije zolen\n" + "tekst over zolen. " * 30
    project = {"done_when": "de leveranciersvergelijking voor Portugal ligt er"}
    ok, waarom = mc._beantwoordt(doc, project, cl)
    assert not ok and "done-when" in waarom


def test_missie_vangt_het_off_mission_rapport():
    ok, waarom = mc._missie("Een verhandeling over kantoorpanden en rentestanden in Frankfurt.")
    assert not ok and "strategie-thema" in waarom


def test_missie_laat_een_op_missie_rapport_staan():
    ok, _ = mc._missie("We onderzochten plasticvrije, vegan materialen en de transparantie erover.")
    assert ok


def test_gegrond_leunt_op_de_bestaande_tegenspraak_skill():
    class _Neg:
        def run(self, payload, context=None):
            assert payload["tekst"] and "bewijs" in payload      # krijgt document + onderbouwing
            return {"ok": True, "oordeel": "moet bij", "ongegrond": ["45% CO2-besparing"],
                    "revisie": "noem de bron"}
    ok, waarom = mc._gegrond("doc", ["d1"], {}, skill=_Neg())
    assert ok is False and "45% CO2-besparing" in waarom


def test_de_critic_toetst_het_rapport_niet_het_onderzochte_materiaal():
    """Op prod zakte een compliance-rapport op de grond-as omdát het zijn werk deed: de skill las
    "'100% Planet-Safe' is ongegrond (geen LCA, geen certificering)" als een ongegronde bewering
    van de SCHRIJVER, terwijl dat de bevinding was. Het kader maakt dat onderscheid expliciet."""
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    mc._gegrond("doc", ["d1"], {}, skill=_Vangt())
    kader = gezien["kader"]
    assert "ONDERZOEKSOBJECT" in kader and "BEVINDING van het rapport" in kader


def test_het_kader_houdt_de_andere_kant_ook_dicht():
    """De regel mag geen vrijbrief worden. "Beoordeel de eigen conclusie" zonder de tegenhanger zou
    élke conclusie gegrond maken; en voorgestelde copy is iets dat het rapport AANDRAAGT, geen
    aangehaald materiaal — anders glipt een content-rapport met een overdreven kopregel erdoor."""
    assert "dekt wat de skills ophaalden het oordeel dat het rapport velt" in mc._KADER
    assert "ook als de conclusie luidt dat iets niet deugt" in mc._KADER
    assert "copy of formuleringen die het rapport voorstelt" in mc._KADER


@pytest.mark.parametrize("soort,ongegrond", [
    ("content", ["de kopregel belooft 'de duurzaamste schoen ter wereld'"]),
    ("research", ["45% CO2-besparing staat in geen enkele deliverable"]),
    ("bulletin", ["'onze klanten zijn unaniem positief' — geen bron"]),
])
def test_andere_rapportsoorten_glippen_er_niet_makkelijker_door(soort, ongegrond):
    """Het kader is soort-onafhankelijk: de critic kent geen compliance-uitzondering. Een rapport
    waarvan de EIGEN beweringen niet gedekt zijn, zakt na de wijziging nog steeds — of het nu
    content, research of een bulletin is."""
    class _Neg:
        def run(self, payload, context=None):
            return {"ok": True, "oordeel": "moet bij", "ongegrond": ongegrond}

    ok, waarom = mc._gegrond("doc", ["d1"], {"soort": soort}, skill=_Neg())
    assert ok is False and ongegrond[0][:20] in waarom


def test_moet_bij_zonder_lijst_zakt_nog_steeds():
    """De tweede afwijsroute blijft intact: 'moet bij' met een revisie maar zonder expliciete lijst
    is nog altijd geen schone grond-as."""
    class _MoetBij:
        def run(self, payload, context=None):
            return {"ok": True, "oordeel": "moet bij", "ongegrond": [], "revisie": "noem de bron"}
    ok, waarom = mc._gegrond("doc", ["d1"], {}, skill=_MoetBij())
    assert ok is False and "noem de bron" in waarom


def test_losse_tegenspraak_aanroepen_veranderen_niet():
    """Het kader is een optie van de critic, geen nieuwe regel van de skill. Een rol die tegenspraak
    los aanroept krijgt exact de prompt van voorheen."""
    from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
    prompts = []

    def _vang(prompt, **kw):
        prompts.append(prompt)
        return '{"oordeel":"houdt stand","ongegrond":[]}'

    with patch(_REASON, _vang):
        TegenspraakSkill().run({"tekst": "een deliverable"}, None)
        TegenspraakSkill().run({"tekst": "een deliverable", "kader": "TOETS ZO"}, None)
    assert "KADER VOOR DEZE TOETS" not in prompts[0]
    assert "KADER VOOR DEZE TOETS:\nTOETS ZO" in prompts[1]


def test_gegrond_zonder_llm_is_onbekend_niet_afgekeurd():
    """Een weggevallen leverancier mag geen rapporten afkeuren — maar 'onbekend' is ook geen
    'geslaagd', en dat verschil moet zichtbaar blijven."""
    class _Stuk:
        def run(self, payload, context=None):
            return {"error": "geen LLM"}
    ok, _ = mc._gegrond("doc", [], {}, skill=_Stuk())
    assert ok is None


def test_het_oordeel_krijgt_ruimte_voor_een_viervoudig_antwoord():
    """De skill-default (700) is gekalibreerd op een losse claim. Over een rapport van 6000 tekens
    brak het antwoord op prod af na 1623 tekens, midden in een zin — onparseerbare JSON, `gegrond`
    op None, en dat las als 'geen LLM' terwijl de premium-trede keurig antwoordde."""
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    mc._gegrond("doc", ["d1"], {}, skill=_Vangt())
    assert gezien["max_tokens"] == mc.MAX_OORDEEL_TOKENS >= 2000


def test_een_afgekapt_antwoord_wordt_niet_als_weggevallen_llm_gemeld():
    """De reden van de skill reist mee. Een gok ('geen LLM?') stuurt de lezer naar de leverancier
    terwijl het aan het budget lag — dezelfde verkeerde diagnose als bij het thinking-budget."""
    class _Afgekapt:
        def run(self, payload, context=None):
            return {"ok": False, "raw_lengte": 1623,
                    "error": "antwoord van 1623 tekens is geen bruikbare JSON "
                             "(afgekapt op max_tokens=3000?) — toets handmatig"}
    ok, waarom = mc._gegrond("doc", ["d1"], {}, skill=_Afgekapt())
    assert ok is None
    assert "1623 tekens" in waarom and "geen LLM" not in waarom


def test_de_skill_scheidt_een_afgekapt_antwoord_van_een_stille_leverancier():
    from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
    with patch(_REASON, lambda p, **kw: "hier begint {\"oordeel\": \"moet bij\", \"ongegr"):
        afgekapt = TegenspraakSkill().run({"tekst": "iets"}, None)
    with patch(_REASON, lambda p, **kw: None):
        stil = TegenspraakSkill().run({"tekst": "iets"}, None)
    assert "geen bruikbare JSON" in afgekapt["error"] and afgekapt["raw_lengte"] > 0
    assert "LLM weg" in stil["error"]


def test_het_budget_van_de_skill_is_instelbaar_maar_blijft_700_zonder_opgave():
    from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
    gezien = []

    def _vang(prompt, **kw):
        gezien.append(kw.get("max_tokens"))
        return '{"oordeel":"houdt stand","ongegrond":[]}'

    with patch(_REASON, _vang):
        TegenspraakSkill().run({"tekst": "iets"}, None)
        TegenspraakSkill().run({"tekst": "iets", "max_tokens": 3000}, None)
        TegenspraakSkill().run({"tekst": "iets", "max_tokens": "onzin"}, None)
    assert gezien == [700, 3000, 700]


# ── Het samengestelde oordeel ────────────────────────────────────────────────

class _Positief:
    def run(self, payload, context=None):
        return {"ok": True, "oordeel": "houdt stand", "ongegrond": [], "samenvatting": "prima"}


def test_geslaagd_oordeel_op_een_goed_rapport():
    cl = _cl([("Onderzoek plasticvrije materialen voor de zool", {})])
    oordeel = mc.beoordeel(project={"done_when": "de zool kan plasticvrij"}, document=GOED_DOC,
                           deliverables=["bewijs"], checklist=cl, skill=_Positief())
    assert oordeel["geslaagd"] is True
    assert all(oordeel["oordelen"][a] is True for a in mc.ASSEN)


def test_dure_toets_draait_niet_als_de_goedkope_al_zakten():
    """Een leeg rapport hoeft geen premium LLM-call om afgekeurd te worden."""
    class _Telt:
        n = 0

        def run(self, payload, context=None):
            _Telt.n += 1
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}
    oordeel = mc.beoordeel(project={}, document="kort", deliverables=[], checklist=None,
                           skill=_Telt())
    assert oordeel["geslaagd"] is False
    assert _Telt.n == 0
    assert oordeel["oordelen"]["gegrond"] is None


def test_onbekende_as_telt_niet_als_geslaagd():
    class _Stuk:
        def run(self, payload, context=None):
            return {"error": "geen LLM"}
    cl = _cl([("Onderzoek plasticvrije materialen voor de zool", {})])
    oordeel = mc.beoordeel(project={}, document=GOED_DOC, deliverables=["b"], checklist=cl,
                           skill=_Stuk())
    assert oordeel["geslaagd"] is False
    assert "gegrond" in oordeel["onbekend"]
    assert "niet getoetst: gegrond" in oordeel["samenvatting"]


# ── De labels ────────────────────────────────────────────────────────────────

def test_critic_labels_zijn_append_only(tmp_path):
    dd = str(tmp_path)
    mc.leg_vast(dd, project_id="p1", rol="sid", fase="eerste",
                oordeel={"geslaagd": False, "oordelen": {"missie": False}, "redenen": ["off-mission"]})
    mc.leg_vast(dd, project_id="p1", rol="sid", fase="herkansing",
                oordeel={"geslaagd": True, "oordelen": {}, "redenen": []})
    rijen = mc.alle(dd)
    assert [r["fase"] for r in rijen] == ["eerste", "herkansing"]
    assert [r["geslaagd"] for r in rijen] == [False, True]
    assert os.path.exists(mc.pad(dd))


def test_ook_geslaagde_oordelen_worden_vastgelegd(tmp_path):
    """Zonder de geslaagde regels weet je alleen hoeveel er zakten, niet welk aandeel — en dan is
    'de critic wijst veel af' niet van 'het dorp levert veel slechte rapporten' te onderscheiden."""
    mc.leg_vast(str(tmp_path), project_id="p", rol="r", fase="eerste",
                oordeel={"geslaagd": True, "oordelen": {}, "redenen": []})
    assert mc.alle(str(tmp_path))[0]["geslaagd"] is True


# ── GUARDS: de review-gate end-to-end ────────────────────────────────────────

def test_guard_off_mission_rapport_bereikt_geen_schone_review(tmp_path):
    """DE guard. Het project komt wél in de review-kolom (eeuwig tegenhouden verbergt het), maar
    NIET schoon: het oordeel staat op het project, op de kaart en in het event."""
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    events = []
    inh.bus.subscribe("critic_rejected", lambda e: events.append(e.data))
    pid = ledger.create("sid", "Onderzoek iets", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Onderzoek iets", skill="openalex_evidence", query="x")
    off_mission = "# R\n\n## Onderzoek iets\n" + "Een verhandeling over kantoorpanden. " * 30
    with patch(_REASON, side_effect=_reason_mock(off_mission)):
        inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review"
    assert p.get("critic_verdict") == "afgewezen"                 # niet schoon
    assert any("Missie-critic" in e.get("text", "") for e in p.get("log", []))
    assert events and events[-1]["oordelen"]["missie"] is False
    assert mc.alle(str(tmp_path))                                 # afwijzing gelogd


def test_guard_leeg_project_wordt_gevlagd(tmp_path):
    """DE tweede guard. Alle taken draaiden, geen enkele leverde iets op."""
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs, leeg=True)              # de skill geeft no_data
    pid = ledger.create("sid", "Onderzoek iets", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Onderzoek iets", skill="openalex_evidence", query="x")
    with patch(_REASON, side_effect=_reason_mock(GOED_DOC)):
        inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    item = p["checklists"][0]["items"][0]
    assert item["done"] is True and item["leeg"] is True          # afgevinkt, maar geen antwoord
    from nooch_village.projects import not_answered_note
    assert "uitgevoerd zonder resultaat" in not_answered_note(p["checklists"][0])
    assert p.get("critic_verdict") == "afgewezen"
    labels = mc.alle(str(tmp_path))
    assert labels and labels[0]["oordelen"]["substantieel"] is False


def test_leeg_item_vinkt_niet_meer_schoon_af(tmp_path):
    """De reparatie: een uitgevoerd-maar-leeg item wordt afgevinkt (anders haalt het project de
    review-gate nooit) maar draagt `leeg`, zodat 4/4 niet als 'alles beantwoord' leest."""
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs, leeg=True)
    pid = ledger.create("sid", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "taak", skill="openalex_evidence", query="x")
    with patch(_REASON, side_effect=_reason_mock("doc")):
        inh._execute_checklist(ledger.get(pid), TODAY)
    item = ledger.get(pid)["checklists"][0]["items"][0]
    assert item["done"] and item["leeg"] and item["leeg_reden"] == "niets gevonden"


def test_goed_rapport_haalt_wel_een_schone_review(tmp_path):
    """De tegenhanger: zonder deze test weet je niet of de critic iets doorlaat of alles tegenhoudt."""
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued",
                        done_when="de zool kan plasticvrij en vegan")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "Onderzoek plasticvrije materialen voor de zool",
                     skill="openalex_evidence", query="x")
    with patch(_REASON, side_effect=_reason_mock(GOED_DOC)), \
         patch("nooch_village.skills_impl.tegenspraak.TegenspraakSkill", lambda: _Positief()):
        inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review"
    assert p.get("critic_verdict") is None                        # SCHOON
    assert not any("Missie-critic" in e.get("text", "") for e in p.get("log", []))


def test_herkans_pas_gebeurt_in_dezelfde_puls(tmp_path):
    """Een puls is een dag. Het project een dag laten wachten op een tweede synthese kost een dag
    en levert niets op wat nu al kan."""
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    pid = ledger.create("sid", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "taak", skill="openalex_evidence", query="x")
    with patch(_REASON, side_effect=_reason_mock("te kort")) as m:
        inh._execute_checklist(ledger.get(pid), TODAY)
    assert m.call_count == 2                                      # synthese + herkansing
    p = ledger.get(pid)
    assert p.get("critic_herkansing") is True
    assert p["status"] == "blocked"                               # niet blijven hangen
    fasen = [r["fase"] for r in mc.alle(str(tmp_path))]
    assert fasen == ["eerste", "herkansing"]


def test_kapotte_critic_blokkeert_de_oplevering_niet(tmp_path, monkeypatch):
    """De poort mag de oplevering niet gijzelen."""
    ledger, ds, docs = _stores(tmp_path)
    inh = _inh(tmp_path, ledger, ds, docs)
    monkeypatch.setattr(mc, "beoordeel", lambda **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    pid = ledger.create("sid", "doel", "human", status="queued")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "taak", skill="openalex_evidence", query="x")
    with patch(_REASON, side_effect=_reason_mock("doc")):
        inh._execute_checklist(ledger.get(pid), TODAY)
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review"
    assert p.get("critic_verdict") is None
