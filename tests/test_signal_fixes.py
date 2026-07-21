"""Signal-fixes (founder 20 jul): (1) een projectsignaal toont de CONCLUSIE (dod_outcome),
niet de "checklist voltooid"-mededeling; (2) de dedup onderdrukt óók afgewezen en verwerkte
signalen, zodat wat je gisteren afhandelde niet als vers item terugkomt."""
from __future__ import annotations

from nooch_village.project_signal import signal_from_project, project_link
from nooch_village.radar_store import RadarStore


def test_signaal_toont_de_conclusie_niet_de_checklist(tmp_path):
    radar = RadarStore(f"{tmp_path}/radar.json")
    p = {"id": "p1", "owner": "harry_hemp", "scope": "Massa-verlies schoenzolen",
         "outcome": "checklist voltooid (5/5) — goedgekeurd na review",
         "dod_outcome": "Ca. 1-5 g per 100 km; grotendeels microplastics in het milieu.",
         "updated_at": 1784000000.0}
    rid = signal_from_project(radar, p)
    it = radar.get(rid)
    assert it["content"].startswith("Ca. 1-5 g")
    assert "checklist voltooid" not in it["content"]
    radar2 = RadarStore(f"{tmp_path}/radar2.json")
    rid2 = signal_from_project(radar2, {**p, "id": "p2", "dod_outcome": ""})
    assert "checklist voltooid" in radar2.get(rid2)["content"]


def test_link_is_dedup_sleutel_en_blijft_stabiel():
    assert project_link("abc") == "/project?id=abc"


def test_afgewezen_signaal_komt_niet_terug(tmp_path):
    radar = RadarStore(f"{tmp_path}/radar.json")
    rid = radar.add(role="scout", feed="Industry Watch", kind="nieuws",
                    content="Lululemon lanceert vegan schoenenlijn")
    radar.set_status(rid, "afgewezen")
    again = radar.add(role="scout", feed="Industry Watch", kind="nieuws",
                      content="Lululemon lanceert vegan schoenenlijn")
    assert again == rid
    assert radar.get(rid)["status"] == "afgewezen"
    assert len(radar.all_items()) == 1


def test_verwerkt_signaal_komt_niet_terug(tmp_path):
    radar = RadarStore(f"{tmp_path}/radar.json")
    rid = radar.add(role="scout", feed="Industry Watch", kind="nieuws", content="Foot Locker koopt Dick's")
    radar.set_status(rid, "goedgekeurd")
    again = radar.add(role="scout", feed="Industry Watch", kind="nieuws", content="Foot Locker koopt Dick's")
    assert again == rid and len(radar.all_items()) == 1
