"""Pijplijn stap 6 — de wachtrij leeghalen zonder de geschiedenis weg te gooien.

DE FOUT DIE DIT MOET VOORKOMEN is niet "te weinig opruimen" maar te véél: de goedgekeurde en
afgewezen radar-items zijn het referentiemateriaal waar de adapters en de dedup op terugkijken.
Een leeggemaakte bak betekent dat hetzelfde nieuws morgen opnieuw als nieuw binnenkomt.

Vier garanties:
  1. alleen `wacht` gaat om; goedgekeurd, afgewezen en samengevoegd blijven exact zoals ze zijn;
  2. er wordt niets VERWIJDERD — de items blijven bestaan, alleen hun status wijzigt;
  3. de droge run schrijft niets, en dat is niet "gedrag" maar de hele werkafspraak;
  4. van de claims-taken gaat alleen open werk om; `done` is afgerond werk en blijft staan.

En de vijfde, die over de METHODE gaat: `verschil()` vergelijkt veld voor veld, want een sha256
zegt alleen dát er iets veranderde. Die functie is hier zelf getest, want een verificatie die zijn
eigen fout niet vangt is geen verificatie.
"""
from __future__ import annotations

import json
import tempfile

import pytest

from nooch_village import radar_archief as ra
from nooch_village.projects import ProjectLedger
from nooch_village.radar_store import RadarStore


@pytest.fixture()
def dd():
    d = tempfile.mkdtemp()
    r = RadarStore(f"{d}/radar.json")
    ids = {}
    for i, status in enumerate(["wacht"] * 3 + ["goedgekeurd", "afgewezen", "samengevoegd"]):
        iid = r.add(role="rol", feed="Legal & Green Claims", kind="signaal",
                    content=f"signaal {i}", link=f"https://x/{i}")
        ids[iid] = status
        if status != "wacht":
            r.set_status(iid, status)
    led = ProjectLedger(f"{d}/projects.json")
    led.create("rol", "open claim-taak", "role", status="future", origin=ra.CLAIMS_ORIGIN)
    # `create` weigert `done` als startstatus (START_STATUSSEN), dus afronden gaat zoals in
    # productie: aanmaken en daarna `complete`. Dat is ook eerlijker — het project heeft dan het
    # spoor van een afgerond project.
    klaar = led.create("rol", "afgeronde claim-taak", "role", status="running",
                       origin=ra.CLAIMS_ORIGIN)
    led.complete(klaar, outcome="af")
    led.create("rol", "gewoon project", "human", status="running")
    return d, klaar


def _statussen(d: str) -> dict:
    items = json.load(open(f"{d}/radar.json"))["items"]
    uit: dict = {}
    for it in items.values():
        uit[it["status"]] = uit.get(it["status"], 0) + 1
    return uit


# ── 1-2. alleen de wachtrij, en niets verdwijnt ──────────────────────────────────────────────

def test_alleen_wacht_gaat_om(dd):
    d, _ = dd
    assert _statussen(d) == {"wacht": 3, "goedgekeurd": 1, "afgewezen": 1, "samengevoegd": 1}
    ra.voer_uit(d, apply=True)
    assert _statussen(d) == {"gearchiveerd": 3, "goedgekeurd": 1, "afgewezen": 1,
                             "samengevoegd": 1}


def test_er_verdwijnt_niets(dd):
    """Archiveren is geen legen. De adapters en de dedup kijken over álle statussen heen."""
    d, _ = dd
    voor = json.load(open(f"{d}/radar.json"))["items"]
    ra.voer_uit(d, apply=True)
    na = json.load(open(f"{d}/radar.json"))["items"]
    assert set(voor) == set(na)
    for iid, item in voor.items():
        for sleutel, waarde in item.items():
            if sleutel == "status":
                continue
            assert na[iid][sleutel] == waarde, f"{iid}.{sleutel} is ongevraagd gewijzigd"


def test_de_run_meldt_zelf_of_er_iets_onverwachts_veranderde(dd):
    """De verificatie hoort bij de actie, niet bij de goede bedoelingen van de aanroeper."""
    d, _ = dd
    v = ra.voer_uit(d, apply=True)
    assert v["onverwacht"] == []
    assert v["radar_gewijzigd"] == 3 and v["mislukt"] == []
    assert v["sha_radar"] and v["sha_radar_na"] != v["sha_radar"]     # er ÍS iets veranderd


# ── 3. de droge run ──────────────────────────────────────────────────────────────────────────

def test_de_droge_run_schrijft_niets(dd):
    d, _ = dd
    sha_voor = ra.sha256(f"{d}/radar.json")
    v = ra.voer_uit(d)
    assert v["toegepast"] is False and len(v["radar_ids"]) == 3
    assert ra.sha256(f"{d}/radar.json") == sha_voor
    assert _statussen(d)["wacht"] == 3


# ── 4. de claims-taken ───────────────────────────────────────────────────────────────────────

def test_alleen_open_claims_taken_worden_gearchiveerd(dd):
    d, klaar = dd
    v = ra.voer_uit(d, apply=True)
    assert v["projecten_gewijzigd"] == 1
    led = ProjectLedger(f"{d}/projects.json")
    rest = [p for p in led.all() if p.get("origin") == ra.CLAIMS_ORIGIN]
    af = [p for p in rest if p["id"] == klaar][0]
    assert af["archived"] is False, "afgerond werk blijft staan"
    assert all(p["archived"] for p in rest if p["id"] != klaar)
    # en een project van een andere herkomst blijft ongemoeid
    assert not any(p["archived"] for p in led.all() if p.get("origin") != ra.CLAIMS_ORIGIN)


def test_twee_keer_draaien_verandert_de_tweede_keer_niets(dd):
    """Idempotent: na de eerste ronde staat er niets meer op `wacht`."""
    d, _ = dd
    ra.voer_uit(d, apply=True)
    sha = ra.sha256(f"{d}/radar.json")
    tweede = ra.voer_uit(d, apply=True)
    assert tweede["radar_ids"] == [] and tweede["radar_gewijzigd"] == 0
    assert ra.sha256(f"{d}/radar.json") == sha


# ── 5. de verificatie vangt zijn eigen fout ──────────────────────────────────────────────────

def test_verschil_ziet_een_ongevraagde_wijziging():
    voor = {"a": {"status": "wacht", "content": "x"}}
    na = {"a": {"status": "gearchiveerd", "content": "GEWIJZIGD"}}
    uit = ra.verschil(voor, na)
    assert any("content" in r for r in uit), "een stille inhoudswijziging moet opvallen"
    assert any("status" in r for r in uit)


def test_verschil_ziet_een_verdwenen_item():
    assert ra.verschil({"a": {"status": "wacht"}}, {}) == ["a: VERDWENEN"]
