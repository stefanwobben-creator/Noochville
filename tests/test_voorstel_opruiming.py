"""De eenmalige opruiming van de vastgelopen projectvoorstellen (21 september 2026).

De lus die ze maakte is in dezelfde beurt opgeheven. Wat achterbleef waren 10 projecten met status
`proposed` — de oudste 43 dagen — die niemand meer kon aannemen of afwijzen omdat de Founder Flow
weg is. Deze tests bewaken de drie eigenschappen die maken dat ik zo'n opruiming op productie durf
te draaien: hij liegt niet in de droge run, hij raakt niets anders aan, en hij wist niet."""
from __future__ import annotations

import json

from nooch_village import voorstel_opruiming as VO
from nooch_village.projects import ProjectLedger


def _dorp(tmp_path, aantal=3):
    """Een projects.json met `aantal` vastgelopen voorstellen plus drie projecten die moeten blijven."""
    led = ProjectLedger(str(tmp_path / "projects.json"))
    vast = []
    for i in range(aantal):
        pid = led.create("rol_a", f"Voorstel {i}", "role", status="future")
        led._projects[pid]["status"] = "proposed"          # zoals ze live staan; create weigert dit nu
        led._save()                                        # elke ledger-actie herleest van schijf
        vast.append(pid)
    blijft = [led.create("rol_a", "Loopt", "human", status="running"),
              led.create("rol_b", "Wacht", "human", status="future")]
    al_weg = led.create("rol_a", "Oud voorstel", "role", status="future")
    led._projects[al_weg]["status"] = "proposed"
    led._projects[al_weg]["archived"] = True               # al gearchiveerd: niet opnieuw aanraken
    led._save()
    return str(tmp_path), vast, blijft, al_weg


def test_de_droge_run_schrijft_niets(tmp_path):
    """De belangrijkste eigenschap: een plan maken mag het bestand niet aanraken. Zonder dit kan ik
    de uitkomst niet lezen vóór ik besluit."""
    dd, vast, _, _ = _dorp(tmp_path)
    voor = VO.sha256(f"{dd}/projects.json")
    uit = VO.voer_uit(dd, apply=False)
    assert sorted(uit["ids"]) == sorted(vast)
    assert uit["toegepast"] is False and uit["gewijzigd"] == 0
    assert VO.sha256(f"{dd}/projects.json") == voor      # byte-voor-byte hetzelfde


def test_alleen_de_vastgelopen_voorstellen_veranderen(tmp_path):
    """De veldvergelijking, niet de hash: een sha256 zegt alleen DAT er iets veranderde."""
    dd, vast, blijft, al_weg = _dorp(tmp_path)
    voor = json.load(open(f"{dd}/projects.json"))
    uit = VO.voer_uit(dd, apply=True)
    assert uit["gewijzigd"] == len(vast) and uit["mislukt"] == []
    assert uit["onverwacht"] == []                        # niets buiten archived/updated_at
    na = json.load(open(f"{dd}/projects.json"))
    assert all(na[p]["archived"] is True for p in vast)
    assert all(na[p]["archived"] is False for p in blijft)
    # en de rest van het record van een opgeruimd voorstel is ongemoeid
    p0 = vast[0]
    onveranderd = {k: v for k, v in voor[p0].items() if k not in ("archived", "updated_at")}
    assert all(na[p0][k] == v for k, v in onveranderd.items())
    assert na[al_weg]["updated_at"] == voor[al_weg]["updated_at"]   # al gearchiveerd = niet aangeraakt


def test_archiveren_is_geen_wissen(tmp_path):
    """`reject_proposal` deed vroeger een harde `del`. Dit niet: de tekst, de herkomst en de datum
    blijven leesbaar, ze verdwijnen alleen uit elke lijst."""
    dd, vast, _, _ = _dorp(tmp_path)
    VO.voer_uit(dd, apply=True)
    na = json.load(open(f"{dd}/projects.json"))
    assert set(vast) <= set(na)
    assert na[vast[0]]["scope"] == "Voorstel 0" and na[vast[0]]["status"] == "proposed"


def test_twee_keer_draaien_doet_de_tweede_keer_niets(tmp_path):
    """Idempotent, zoals elke opruiming hier: een herhaling mag geen tweede `updated_at`-bump geven."""
    dd, _, _, _ = _dorp(tmp_path)
    VO.voer_uit(dd, apply=True)
    tussen = VO.sha256(f"{dd}/projects.json")
    tweede = VO.voer_uit(dd, apply=True)
    assert tweede["ids"] == [] and tweede["gewijzigd"] == 0
    assert VO.sha256(f"{dd}/projects.json") == tussen


def test_zonder_bestand_valt_hij_niet_om(tmp_path):
    """Fail-closed: geen projects.json (een vers dorp) is geen fout, het is nul werk."""
    assert VO.plan(str(tmp_path))["ids"] == []
