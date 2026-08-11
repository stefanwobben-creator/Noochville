"""De duurzame park-reden: waaróm staat dit project stil?

Tot nu toe was dat alleen af te leiden uit de fail-teller van de items — en juist bij het parkeren
zet `reset_item_fails` die op nul, zodat een reactivering een verse reeks pogingen krijgt. Gevolg:
een item dat drie keer faalde en toen gereset werd is daarna niet te onderscheiden van een item dat
nooit gedraaid heeft. Op productie stonden 16 open items op "kan gewoon vooruit" terwijl hun project
al dagen geparkeerd was; welke van die twee dat waren, was niet meer te zeggen.

Zolang dat verschil weg is, is elke heropening en elke melding aan de mens een gok. Daarom een FEIT
op het project — wie, wanneer, welke reden, welke items — dat geen enkele item-operatie aanraakt.
"""
from __future__ import annotations

import pytest

from nooch_village.projects import ProjectLedger


def _project(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("rol", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title="Uitvoerplan")
    led.check_add(pid, cl["id"], "haal de patenten op", skill="epo_patents")
    led.check_add(pid, cl["id"], "bel de fabriek")
    items = led.get(pid)["checklists"][0]["items"]
    return led, pid, cl["id"], items


# ── Het feit zelf ────────────────────────────────────────────────────────────

def test_de_park_reden_overleeft_het_resetten_van_de_fail_tellers(tmp_path):
    """DE reden dat dit een projectveld is en geen afleiding: `reset_item_fails` draait bij élke
    parkering, en wist precies het bewijs waar je de reden uit zou willen halen."""
    led, pid, clid, items = _project(tmp_path)
    for _ in range(3):
        led.note_item_fail(pid, clid, items[0]["id"])
    led.park(pid, "fails", [{"id": items[0]["id"], "text": "haal de patenten op", "reden": "fails"}])
    led.reset_item_fails(pid, clid, [items[0]["id"]])

    assert led.get(pid)["checklists"][0]["items"][0]["fails"] == 0     # bewijs weg uit het item…
    park = led.park_reden(pid)
    assert park["reden"] == "fails"                                    # …maar niet uit het project
    assert park["items"][0]["reden"] == "fails"
    assert park["at"] > 0


def test_de_reden_wordt_afgeleid_als_de_aanroeper_er_geen_geeft(tmp_path):
    led, pid, clid, items = _project(tmp_path)
    led.park(pid, "", [{"id": "a", "text": "x", "reden": "payload"},
                       {"id": "b", "text": "y", "reden": "payload"}])
    assert led.park_reden(pid)["reden"] == "payload"


def test_meer_dan_een_soort_heet_gemengd(tmp_path):
    """Niet de zwaarste of de eerste: 'gemengd'. Anders verdwijnt de payload-helft achter een
    human-etiket, en dat is precies de verwisseling die dit veld moet stoppen."""
    led, pid, clid, items = _project(tmp_path)
    led.park(pid, "", [{"id": "a", "text": "x", "reden": "human"},
                       {"id": "b", "text": "y", "reden": "payload"}])
    assert led.park_reden(pid)["reden"] == "gemengd"


@pytest.mark.parametrize("reden", ["human", "payload", "fails", "gemengd"])
def test_alle_vier_de_redenen_worden_bewaard(tmp_path, reden):
    led, pid, _clid, _items = _project(tmp_path)
    assert led.park(pid, reden, [{"id": "a", "text": "x", "reden": reden}]) is True
    assert led.park_reden(pid)["reden"] == reden


def test_een_onbekende_reden_wordt_niet_klakkeloos_bewaard(tmp_path):
    led, pid, _clid, _items = _project(tmp_path)
    led.park(pid, "verzonnen", [{"id": "a", "text": "x", "reden": "human"}])
    assert led.park_reden(pid)["reden"] == "human"       # afgeleid uit de items, niet overgenomen


def test_park_noteert_wie_parkeerde_en_welke_items(tmp_path):
    led, pid, _clid, items = _project(tmp_path)
    led.park(pid, "human", [{"id": items[1]["id"], "text": "bel de fabriek", "reden": "human"}],
             door="harry_hemp")
    park = led.park_reden(pid)
    assert park["door"] == "harry_hemp"
    assert park["items"] == [{"id": items[1]["id"], "text": "bel de fabriek", "reden": "human"}]


def test_de_laatste_parkering_geldt(tmp_path):
    led, pid, _clid, _items = _project(tmp_path)
    led.park(pid, "human", [{"id": "a", "text": "x", "reden": "human"}])
    led.park(pid, "payload", [{"id": "b", "text": "y", "reden": "payload"}])
    assert led.park_reden(pid)["reden"] == "payload"
    assert len(led.park_reden(pid)["items"]) == 1


# ── Levensduur ───────────────────────────────────────────────────────────────

def test_zonder_parkering_is_er_geen_reden(tmp_path):
    led, pid, _clid, _items = _project(tmp_path)
    assert led.park_reden(pid) == {}
    assert led.park_reden("bestaat-niet") == {}


def test_deblokkeren_laat_de_reden_vervallen(tmp_path):
    """De reden hoort bij de blokkade. Blijft hij staan na deblokkeren, dan leest een volgende
    parkering als 'stond er al' en weet niemand meer welke van de twee actueel is."""
    led, pid, _clid, _items = _project(tmp_path)
    led.park(pid, "human", [{"id": "a", "text": "x", "reden": "human"}])
    led.block(pid, "vastgelopen op 1 item(s)")
    assert led.park_reden(pid)["reden"] == "human"
    led.unblock(pid)
    assert led.park_reden(pid) == {}


def test_blokkeren_wist_de_reden_niet(tmp_path):
    """Volgorde in de puls: eerst `park`, dan `block`. Zou `block` de reden wissen, dan was hij
    precies bij het parkeren weg."""
    led, pid, _clid, _items = _project(tmp_path)
    led.park(pid, "payload", [{"id": "a", "text": "x", "reden": "payload"}])
    led.block(pid, "vastgelopen op 1 item(s) — wacht op antwoord")
    assert led.park_reden(pid)["reden"] == "payload"


def test_park_is_een_schrijfmethode_onder_het_slot():
    """Zelfde eis als elke andere schrijver op deze store (flock + verse read)."""
    from nooch_village.projects import _WRITE_METHODS
    assert "park" in _WRITE_METHODS


def test_de_puls_legt_de_reden_vast_voordat_hij_reset():
    """Volgorde-guard op de bron: staat `reset_item_fails` vóór `park`, dan legt de puls een reden
    vast die al gewist is."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert src.index("ledger.park(pid,") < src.index("ledger.reset_item_fails(pid, clid,")


# ── Halve mens-taken: markeren i.p.v. het hele project verplaatsen ───────────

def test_een_item_kan_alsnog_als_mens_werk_gemarkeerd_worden(tmp_path):
    """`check_add` kon dit alleen bij het aanmaken, en de planner ziet het niet altijd goed. Een
    checklist met "ontwerp een testprotocol" naast "voer 5 testrondes uit" is half rol-werk, half
    labwerk. Zonder deze setter is de enige uitweg het hele project naar de backlog schuiven — en
    dan verdwijnt ook het deel dat een rol wél kan oppakken."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("rol", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title="Uitvoerplan")
    led.check_add(pid, cl["id"], "ontwerp een testprotocol")
    led.check_add(pid, cl["id"], "voer 5 testrondes uit")
    items = led.get(pid)["checklists"][0]["items"]

    assert led.set_item_human(pid, cl["id"], items[1]["id"]) is True
    vers = led.get(pid)["checklists"][0]["items"]
    assert vers[1]["human_task"] is True
    assert "human_task" not in vers[0]                  # het rol-deel blijft gewoon werk

    assert led.set_item_human(pid, cl["id"], items[1]["id"], human=False) is True
    assert "human_task" not in led.get(pid)["checklists"][0]["items"][1]
    assert led.set_item_human(pid, cl["id"], "bestaat-niet") is False


def test_een_mens_taak_telt_niet_mee_in_de_klaar_telling(tmp_path):
    """Anders houdt hij het project eeuwig onaf — precies de zombie die de klep moet voorkomen."""
    from nooch_village.projects import checklist_progress
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("rol", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title="Uitvoerplan")
    led.check_add(pid, cl["id"], "rol-werk", skill="x")
    led.check_add(pid, cl["id"], "labwerk")
    items = led.get(pid)["checklists"][0]["items"]
    led.check_toggle(pid, cl["id"], items[0]["id"])
    led.set_item_human(pid, cl["id"], items[1]["id"])
    assert checklist_progress(led.get(pid)["checklists"][0]) == (1, 1)


def test_set_item_human_is_een_schrijfmethode_onder_het_slot():
    from nooch_village.projects import _WRITE_METHODS
    assert "set_item_human" in _WRITE_METHODS
