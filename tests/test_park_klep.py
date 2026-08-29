"""De parkeer-klep en de payload-reparatiepas.

Twee defecten uit dezelfde meting:

  1. `_tend_projects` las alleen `queued`/`running`, dus een geparkeerd project werd nooit meer
     bekeken. Vier projecten stonden tot vijftien dagen stil, en omdat `reset_item_fails` bij het
     parkeren de tellers op nul zet, lázen hun items als "kan gewoon vooruit".
  2. Bij het parkeren gold `mens = alles wat geen 'fails' is`. Een payload-gebrek — de rol schreef
     zelf een onvolledige payload voor zijn eigen skill — kwam daardoor bij de mens binnen als
     "wacht op een mens of externe partij". Tien items, zeven projecten.

De klep leest de VASTGELEGDE park-reden (#287), niet de item-state: die schijn is precies wat de
reset veroorzaakt.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.park_klep import heropen, opgelost
from nooch_village.projects import ProjectLedger

_REASON = "nooch_village.llm.reason"


def _p(tmp_path, items):
    """Project met checklist; `items` = [(tekst, skill, payload_ok)]."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("rol", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title="Uitvoerplan")
    for tekst, skill, ok in items:
        led.check_add(pid, cl["id"], tekst, skill=skill, payload_ok=ok)
    return led, pid, cl["id"], led.get(pid)["checklists"][0]["items"]


# ── 1. De klep ───────────────────────────────────────────────────────────────

def test_een_mens_item_dat_afgevinkt_is_opent_het_project(tmp_path):
    led, pid, clid, items = _p(tmp_path, [("bel de fabriek", None, True)])
    led.park(pid, "human", [{"id": items[0]["id"], "text": "bel de fabriek", "reden": "human"}])
    led.block(pid, "vastgelopen op 1 item(s)")
    assert heropen(led, led.get(pid)) is None            # nog niet afgevinkt

    led.check_toggle(pid, clid, items[0]["id"])
    assert heropen(led, led.get(pid)) is not None
    assert led.get(pid)["status"] == "running"
    assert led.park_reden(pid) == {}                     # reden vervalt met de blokkade


def test_een_overgeslagen_mens_item_telt_ook_als_opgelost(tmp_path):
    led, pid, clid, items = _p(tmp_path, [("bel de fabriek", None, True)])
    led.park(pid, "human", [{"id": items[0]["id"], "text": "bel", "reden": "human"}])
    led.block(pid, "vastgelopen")
    led.set_item_skipped(pid, clid, items[0]["id"], True, "niet meer nodig")
    assert heropen(led, led.get(pid)) is not None


def test_een_herstelde_payload_opent_het_project(tmp_path):
    led, pid, clid, items = _p(tmp_path, [("scan patenten", "epo_patents", False)])
    led.park(pid, "payload", [{"id": items[0]["id"], "text": "scan", "reden": "payload"}])
    led.block(pid, "vastgelopen")
    assert heropen(led, led.get(pid)) is None

    led.set_item_payload(pid, clid, items[0]["id"], {"term": "barefoot"})
    assert heropen(led, led.get(pid)) is not None


def test_park_reden_fails_blijft_staan(tmp_path):
    """Een bron die drie keer faalde gaat het bij poging vier ook niet doen. Automatisch loslaten
    zou hier alleen de thrash-loop voeden: draaien, falen, parkeren, weer los."""
    led, pid, clid, items = _p(tmp_path, [("haal op", "epo_patents", True)])
    led.park(pid, "fails", [{"id": items[0]["id"], "text": "haal op", "reden": "fails"}])
    led.block(pid, "vastgelopen")
    klaar, waarom = opgelost(led.get(pid), led.park_reden(pid))
    assert klaar is False and "ingrijpen" in waarom
    assert heropen(led, led.get(pid)) is None


def test_gemengd_met_een_fails_erin_blijft_ook_staan(tmp_path):
    led, pid, clid, items = _p(tmp_path, [("bel", None, True), ("haal op", "epo_patents", True)])
    led.park(pid, "", [{"id": items[0]["id"], "text": "bel", "reden": "human"},
                       {"id": items[1]["id"], "text": "haal op", "reden": "fails"}])
    led.block(pid, "vastgelopen")
    led.check_toggle(pid, clid, items[0]["id"])          # mens-deel opgelost
    assert heropen(led, led.get(pid)) is None            # maar de fails-helft niet


def test_zonder_vastgelegde_reden_blijft_het_staan(tmp_path):
    """Geparkeerd vóór de klep bestond. Zonder reden is elke heropening een gok — precies de fout
    die we net hebben weggehaald."""
    led, pid, clid, items = _p(tmp_path, [("bel", None, True)])
    led.block(pid, "vastgelopen op 1 item(s)")
    klaar, waarom = opgelost(led.get(pid), led.park_reden(pid))
    assert klaar is False and "geen vastgelegde park-reden" in waarom


def test_een_nieuw_item_opent_het_project_niet(tmp_path):
    """De vraag is 'is de reden van toen verdwenen?', niet 'valt er nu iets te doen?'."""
    led, pid, clid, items = _p(tmp_path, [("bel", None, True)])
    led.park(pid, "human", [{"id": items[0]["id"], "text": "bel", "reden": "human"}])
    led.block(pid, "vastgelopen")
    led.check_add(pid, clid, "iets nieuws", skill="epo_patents")
    assert heropen(led, led.get(pid)) is None


def test_een_verwijderd_item_is_geen_blokkade_meer(tmp_path):
    led, pid, clid, items = _p(tmp_path, [("bel", None, True)])
    led.park(pid, "human", [{"id": items[0]["id"], "text": "bel", "reden": "human"}])
    led.block(pid, "vastgelopen")
    led.check_remove(pid, clid, items[0]["id"])
    assert heropen(led, led.get(pid)) is not None


def test_de_klep_raakt_niet_geparkeerde_projecten_niet_aan(tmp_path):
    led, pid, _clid, items = _p(tmp_path, [("bel", None, True)])
    assert heropen(led, led.get(pid)) is None            # status queued, geen blokkade
    assert led.get(pid)["status"] == "queued"


def test_een_kapotte_park_reden_breekt_de_puls_niet(tmp_path):
    class _Stuk:
        def park_reden(self, pid):
            raise OSError("store weg")
    assert heropen(_Stuk(), {"id": "p", "status": "blocked"}) is None


def test_de_puls_leest_geparkeerde_projecten():
    """Guard op de bedrading: zonder deze lus is de klep dood code."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    i = src.index("def _tend_projects")
    body = src[i:i + 3000]
    assert 'ledger.by_status("blocked")' in body and "heropen(ledger, p)" in body


# ── 2. De reparatiepas ───────────────────────────────────────────────────────

class _Skill:
    name = "epo_patents"
    description = "patenten"
    input_schema = "term: str (verplicht)"
    required_payload = ("term",)

    def run(self, payload, context=None):
        return {"rows": [1]}


def _inhabitant(tmp_path, led):
    from nooch_village.event_bus import EventBus
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RecordType, RoleDefinition
    from nooch_village.skills import SkillRegistry
    reg = SkillRegistry()
    reg.register(_Skill())
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path), projects=led, personas=None,
                          deliverables=None, records=None)
    rec = Record(id="rol", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p", accountabilities=[], domains=[],
                                           skills=["epo_patents"]), source="seed")
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


def test_een_onvolledige_payload_repareert_de_rol_zelf(tmp_path):
    """Geen mens-werk: de rol schreef zelf een onvolledige payload voor zijn eigen skill. Lukt het
    herstel, dan ziet de mens dit nooit."""
    led, pid, clid, items = _p(tmp_path, [("Scan PHA-patenten voor footwear", "epo_patents", False)])
    inh = _inhabitant(tmp_path, led)
    with patch(_REASON, lambda p, **kw: '{"term": "PHA footwear"}'):
        gelukt = inh._herstel_payloads(pid, clid, [led.get(pid)["checklists"][0]["items"][0]])
    assert gelukt == {items[0]["id"]}
    it = led.get(pid)["checklists"][0]["items"][0]
    assert it["payload"] == {"term": "PHA footwear"} and "payload_ok" not in it


def test_een_herstel_dat_de_poort_niet_haalt_telt_niet(tmp_path):
    """Fail-closed op de uitkomst: dezelfde validatie als bij de eerste poging. Een LLM die iets
    verzint komt er dus niet mee weg — daarom mag deze call op de goedkope ladder."""
    led, pid, clid, items = _p(tmp_path, [("Scan patenten", "epo_patents", False)])
    inh = _inhabitant(tmp_path, led)
    with patch(_REASON, lambda p, **kw: '{"iets_anders": "x"}'):   # 'term' ontbreekt nog steeds
        assert inh._herstel_payloads(pid, clid, [led.get(pid)["checklists"][0]["items"][0]]) == set()
    assert led.get(pid)["checklists"][0]["items"][0].get("payload_ok") is False


@pytest.mark.parametrize("antwoord", [None, "", "geen json", '{"kapot": '])
def test_een_onbruikbaar_antwoord_laat_het_item_met_rust(tmp_path, antwoord):
    led, pid, clid, items = _p(tmp_path, [("Scan patenten", "epo_patents", False)])
    inh = _inhabitant(tmp_path, led)
    with patch(_REASON, lambda p, **kw: antwoord):
        assert inh._herstel_payloads(pid, clid, [led.get(pid)["checklists"][0]["items"][0]]) == set()


def test_de_prompt_verbiedt_het_raden_van_identifiers(tmp_path):
    """Een gerepareerde payload met een verzonnen merknaam of URL is erger dan een geparkeerd item."""
    led, pid, clid, items = _p(tmp_path, [("Scan patenten", "epo_patents", False)])
    inh = _inhabitant(tmp_path, led)
    gezien = []
    with patch(_REASON, lambda p, **kw: gezien.append(p) or '{"term": "x"}'):
        inh._herstel_payloads(pid, clid, [led.get(pid)["checklists"][0]["items"][0]])
    assert "Verzin GEEN identifiers" in gezien[0]
    assert "liever leeg dan het te raden" in gezien[0]


def test_de_drie_redenen_blijven_gescheiden_in_de_melding():
    """`mens = [... != "fails"]` lumpte payload bij het mens-werk, en dan komt een planfout van de
    rol bij de mens binnen als 'wacht op een externe partij'."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert 'mens = [it for it in stuck if blokkades[it["id"]] == "human"]' in src
    assert 'payload = [it for it in stuck if blokkades[it["id"]] == "payload"]' in src
    assert "if mens and not faal and not payload:" in src
    assert "payload onvolledig na herstelpoging" in src


# ── De founder-ping: alleen als de park-reden hem nodig heeft ───────────────

def test_alleen_een_mens_blokkade_pingt_de_founder():
    """Dit vuurde ongeacht de reden: 79 van de 98 founder-notificaties waren "Project van X
    vastgelopen". Een payload- of fails-blokkade is rolwerk — de rol herstelt zijn payload of de
    bron moet gefixt worden, en het project draagt sinds #287 zijn eigen park-reden waarmee de klep
    het afhandelt. Zonder deze poort is de inbox een logbestand met een badge erop.

    Sinds 29 aug 2026 staat er een vierde voorwaarde bij: `not geland`. Landde de stap al
    wélgevormd bij een mens (de laatste meter, escalation_router.naar_mens), dan zou deze ping een
    TWEEDE melding over dezelfde gebeurtenis zijn — en dan overschreeuwt de vage ("vastgelopen op N
    mens-/extern item(s)") de concrete vraag die er net naast kwam te liggen."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    i = src.index("ledger.block(pid, f\"vastgelopen op")
    blok = src[i:i + 1800]
    assert "if mens and not payload and not faal and not geland:" in blok
    assert "_notify_founder" in blok
    assert "geparkeerd zonder founder-ping" in blok        # de andere tak is zichtbaar, niet stil
    assert "wélgevormd bij een" in blok                    # en de derde tak ook
