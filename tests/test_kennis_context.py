"""Kennis-eerst: elke rol die aan een project begint raadpleegt eerst Lara's kennislaag.

Dekt: de deterministische helper (kaartjes/inzichten/signalen op woord-overlap, niets bij
geen overlap, fail-soft zonder stores), de harde cap op het promptblok, de prompt-injectie
in project_worker én in de checklist-plan-prompt van de Inhabitant, het
kennis_geraadpleegd-event op de bus (ook bij 0/0/0) en de feed-regel op de projectkaart."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.insight import Insight
from nooch_village.kennis_context import kennis_blok, kennis_voor, meld_raadpleging, totaal
from nooch_village.kennisbank import KennisbankStore
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.notes_store import NotesStore
from nooch_village.projects import ProjectLedger
from nooch_village.project_worker import work_projects
from nooch_village.radar_store import RadarStore


# ── Opbouw van een gevulde kennislaag in een tmp-data_dir ─────────────────────

def _seed_kennislaag(data_dir: str) -> dict:
    """Eén relevant kaartje, één relevant inzicht en één relevant signaal rond 'barefoot
    loopschoenen' + ruis die er níet uit mag komen. Geeft de geplante ids terug."""
    notes = NotesStore(os.path.join(data_dir, "notes.json"))
    notes.add(Insight(id="atom_bf", claim="Barefoot schoenen versterken de voetspieren",
                      source="OpenAlex", word="barefoot loopschoenen"))
    notes.add(Insight(id="atom_ruis", claim="Quantum supergeleiders zijn koud",
                      source="arxiv", word="quantum supergeleiders"))
    kb = KennisbankStore(os.path.join(data_dir, "kennisbank.json"))
    iid = kb.add("Barefoot loopschoenen versterken de voet", why="uit meerdere studies")
    kb.add("Quantum supergeleiders werken alleen gekoeld")
    radar = RadarStore(os.path.join(data_dir, "radar.json"))
    sid = radar.add(role="scout", feed="Competitor Watch", kind="markt",
                    content="Barefoot loopschoenen trend groeit in Duitsland", source="rss")
    radar.set_status(sid, "goedgekeurd")
    # goedgekeurd maar al gepromoveerd → hoort NIET in de uitkomst
    prom = radar.add(role="scout", feed="Competitor Watch", kind="markt",
                     content="Barefoot loopschoenen review verschenen", source="rss")
    radar.set_status(prom, "goedgekeurd")
    radar.mark_promoted(prom, "atom_x")
    # nog niet goedgekeurd (status 'wacht') → hoort er ook niet in
    radar.add(role="scout", feed="Competitor Watch", kind="markt",
              content="Barefoot loopschoenen subsidie aangekondigd", source="rss")
    return {"atom": "atom_bf", "inzicht": iid, "signaal": sid, "gepromoveerd": prom}


ZOEK = "onderzoek naar barefoot loopschoenen"


# ── 1. De helper: vindt op woord-overlap, niets zonder overlap, fail-soft ─────

def test_helper_vindt_kaartjes_inzichten_en_signalen(tmp_path):
    ids = _seed_kennislaag(str(tmp_path))
    k = kennis_voor(str(tmp_path), ZOEK)
    assert [x["id"] for x in k["kaartjes"]] == [ids["atom"]]
    assert [x["id"] for x in k["inzichten"]] == [ids["inzicht"]]
    assert [x["id"] for x in k["signalen"]] == [ids["signaal"]]      # gepromoveerd + wacht eruit
    assert k["samenvatting"] == "1 kaartjes, 1 inzichten, 1 signalen"
    assert k["kaartjes"][0]["bron"] == "OpenAlex"                    # per item: id + regel + bron
    assert k["inzichten"][0]["verdict"] == "dun"                     # live verdict (geen evidence)
    assert totaal(k) == 3


def test_helper_niets_bij_geen_overlap(tmp_path):
    _seed_kennislaag(str(tmp_path))
    k = kennis_voor(str(tmp_path), "vergaderruimte reserveren kantoortuin")
    assert k["kaartjes"] == [] and k["inzichten"] == [] and k["signalen"] == []
    assert k["samenvatting"] == "0 kaartjes, 0 inzichten, 0 signalen"


def test_helper_failsoft_zonder_stores_en_met_contextobject(tmp_path):
    leeg = kennis_voor(str(tmp_path / "bestaat_niet"), ZOEK)         # geen enkele store → leeg, geen crash
    assert totaal(leeg) == 0
    _seed_kennislaag(str(tmp_path))
    via_ctx = kennis_voor(SimpleNamespace(data_dir=str(tmp_path)), ZOEK)   # Context-achtig object werkt ook
    assert totaal(via_ctx) == 3
    assert totaal(kennis_voor(None, ZOEK)) == 0                      # geen data_dir → leeg
    assert totaal(kennis_voor(str(tmp_path), "")) == 0               # lege tekst → leeg


# ── 2. Het promptblok: kop, inhoud en harde cap ───────────────────────────────

def test_kennis_blok_rendert_en_capt(tmp_path):
    _seed_kennislaag(str(tmp_path))
    blok = kennis_blok(kennis_voor(str(tmp_path), ZOEK))
    assert blok.startswith("REEDS BEKEND (kennisbank — vul aan, herhaal niet):")
    assert "Barefoot schoenen versterken de voetspieren" in blok
    assert len(blok) <= 1500
    assert kennis_blok({"kaartjes": [], "inzichten": [], "signalen": []}) == ""   # niets → geen blok


def test_kennis_blok_harde_cap():
    veel = {"kaartjes": [{"id": f"a{i}", "tekst": "x" * 150, "bron": "b"} for i in range(30)],
            "inzichten": [], "signalen": []}
    assert len(kennis_blok(veel)) <= 1500                            # default-cap houdt stand
    assert len(kennis_blok(veel, max_chars=80)) <= 80                # ook een krappe cap is hard


# ── 3. project_worker: injectie in de prompt + event + feed-regel ─────────────

def _project_setup(tmp_path, scope):
    _seed_kennislaag(str(tmp_path))
    led = ProjectLedger(str(tmp_path / "projects.json"))
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="scout", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="speur")))
    pid = led.create("scout", scope, "human", status="queued")
    return led, recs, pid


def test_work_projects_injecteert_reeds_bekend(tmp_path):
    led, recs, pid = _project_setup(tmp_path, ZOEK)
    seen, events = {}, []
    bus = EventBus(name="test")
    bus.subscribe("kennis_geraadpleegd", events.append)
    work_projects(led, recs, llm_reason=lambda pr: seen.update(p=pr) or "LEVER: gedaan",
                  data_dir=str(tmp_path), bus=bus)
    assert "REEDS BEKEND (kennisbank — vul aan, herhaal niet):" in seen["p"]
    assert "Barefoot schoenen versterken de voetspieren" in seen["p"]
    # event op de bus: project, rol, tellingen én ids
    assert len(events) == 1
    e = events[0]
    assert e.name == "kennis_geraadpleegd" and e.data["project_id"] == pid
    assert e.data["rol"] == "scout"
    assert e.data["gevonden"] == {"kaartjes": 1, "inzichten": 1, "signalen": 1}
    assert "atom_bf" in e.data["ids"]
    # feed-regel op de projectkaart (bestaand add_feed_entry, kind=system)
    feed = [n for n in led.get(pid)["log"] if "📚 raadpleegde de kennisbank" in n.get("text", "")]
    assert len(feed) == 1 and feed[0]["kind"] == "system"
    assert "1 kaartjes, 1 inzichten, 1 signalen" in feed[0]["text"]


def test_work_projects_niets_gevonden_wel_event_geen_injectie(tmp_path):
    led, recs, pid = _project_setup(tmp_path, "vergaderruimte reserveren kantoortuin")
    seen, events = {}, []
    bus = EventBus(name="test")
    bus.subscribe("kennis_geraadpleegd", events.append)
    work_projects(led, recs, llm_reason=lambda pr: seen.update(p=pr) or "LEVER: gedaan",
                  data_dir=str(tmp_path), bus=bus)
    assert "REEDS BEKEND" not in seen["p"]                           # niets → geen prompt-injectie
    assert len(events) == 1                                          # maar wél een event (0/0/0)
    assert events[0].data["gevonden"] == {"kaartjes": 0, "inzichten": 0, "signalen": 0}
    assert not [n for n in led.get(pid)["log"] if "📚" in n.get("text", "")]   # geen lege feed-regel


def test_work_projects_zonder_data_dir_ongewijzigd(tmp_path):
    led, recs, pid = _project_setup(tmp_path, ZOEK)
    seen = {}
    res = work_projects(led, recs, llm_reason=lambda pr: seen.update(p=pr) or "LEVER: gedaan")
    assert res["worked"] == 1 and "REEDS BEKEND" not in seen["p"]    # bestaand gedrag intact


# ── 4. Inhabitant: raadpleging vóór de planning + injectie in de plan-prompt ──

def _inhabitant(tmp_path, ledger, bus):
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.skills import SkillRegistry
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"},
                          data_dir=str(tmp_path), projects=ledger, records=None)
    rec = Record(id="scout", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="speur", accountabilities=["research"],
                                           domains=[], skills=[]), source="sensed")
    return Inhabitant(rec, bus, SkillRegistry(), ctx)


def test_prepare_project_raadpleegt_en_injecteert(tmp_path):
    _seed_kennislaag(str(tmp_path))
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid = ledger.create("scout", ZOEK, "human", status="future")
    bus = EventBus(name="test")
    events = []
    bus.subscribe("kennis_geraadpleegd", events.append)
    inh = _inhabitant(tmp_path, ledger, bus)
    cap = {}
    def fake_reason(prompt, **k):
        cap["prompt"] = prompt
        return (None, "mock") if k.get("return_tier") else None     # plan faalt; raadpleging is dan al gebeurd
    with patch("nooch_village.llm.reason", side_effect=fake_reason):
        inh.prepare_project(pid)
    assert "REEDS BEKEND (kennisbank — vul aan, herhaal niet):" in cap["prompt"]
    assert "Barefoot schoenen versterken de voetspieren" in cap["prompt"]
    assert len(events) == 1 and events[0].data == {
        "project_id": pid, "rol": "scout",
        "gevonden": {"kaartjes": 1, "inzichten": 1, "signalen": 1}, "ids": events[0].data["ids"]}
    assert [n for n in ledger.get(pid)["log"] if "📚 raadpleegde de kennisbank" in n.get("text", "")]


def test_prepare_project_zonder_kennislaag_failsoft(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))          # géén notes/kennisbank/radar
    pid = ledger.create("scout", ZOEK, "human", status="future")
    bus = EventBus(name="test")
    events = []
    bus.subscribe("kennis_geraadpleegd", events.append)
    inh = _inhabitant(tmp_path, ledger, bus)
    cap = {}
    def fake_reason(prompt, **k):
        cap["prompt"] = prompt
        return (None, "mock") if k.get("return_tier") else None
    with patch("nooch_village.llm.reason", side_effect=fake_reason):
        inh.prepare_project(pid)                                     # mag niet crashen
    assert "REEDS BEKEND" not in cap["prompt"]
    assert len(events) == 1                                          # ook 'niets gevonden' is een event
    assert events[0].data["gevonden"] == {"kaartjes": 0, "inzichten": 0, "signalen": 0}


# ── 5. meld_raadpleging: fail-soft zonder bus ─────────────────────────────────

def test_meld_raadpleging_zonder_bus_crasht_niet():
    meld_raadpleging(None, project_id="p1", rol="scout", kennis=None)   # alleen de logregel
