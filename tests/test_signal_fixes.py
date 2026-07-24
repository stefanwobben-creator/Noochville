"""Signal-fixes: (1) een projectsignaal toont de INHOUD — de conclusie uit het einddocument, anders
een niet-procedurele dod_outcome, anders "Afgerond: <scope>" — nooit de procedurele "checklist
voltooid / goedgekeurd na review" (founder 24 jul); (2) de dedup onderdrukt óók afgewezen en
verwerkte signalen; (3) de backfill herschrijft bestaande procedurele signalen terugwerkend."""
from __future__ import annotations

from nooch_village.project_signal import (signal_from_project, project_link,
                                          project_conclusie, backfill_signal_content, KIND, FEED)
from nooch_village.radar_store import RadarStore


def test_signaal_leest_het_einddocument(tmp_path):
    radar = RadarStore(f"{tmp_path}/radar.json")
    doc = ("# Massa-verlies schoenzolen\n\n## Conclusie\n"
           "Ca. 1-5 g per 100 km slijt weg; grotendeels microplastics in het milieu.\n")
    p = {"id": "p1", "owner": "harry_hemp", "scope": "Massa-verlies schoenzolen",
         "outcome": "checklist voltooid (5/5) — goedgekeurd na review",
         "dod_outcome": "", "updated_at": 1784000000.0}
    rid = signal_from_project(radar, p, doc)
    it = radar.get(rid)
    assert it["content"].startswith("Ca. 1-5 g")
    assert "checklist voltooid" not in it["content"]


def test_seed_boilerplate_wordt_nooit_de_conclusie(tmp_path):
    # Een einddocument dat alleen de geseede opdracht bevat mag NOOIT de sjabloontekst als signaal
    # opleveren ("De inwoner werkt dit document…"); zonder echt antwoord → "Afgerond: <scope>".
    from nooch_village.projects import seed_document
    radar = RadarStore(f"{tmp_path}/radar.json")
    seed = seed_document("Er staat een compliant claim op de site")
    p = {"id": "p9", "owner": "compliance", "scope": "Compliance-check",
         "done_when": "Er staat een compliant claim op de site", "dod_outcome": ""}
    it = radar.get(signal_from_project(radar, p, seed))
    assert it["content"] == "Afgerond: Compliance-check"
    assert "De inwoner werkt dit document" not in it["content"]
    # Mét een echt antwoord onder de seed komt dát antwoord eruit.
    doc = seed + "\n\n## Conclusie\nDrie van de vijf claims zijn onderbouwd; twee wachten op labdata."
    assert project_conclusie(doc, p["done_when"]).startswith("Drie van de vijf")


def test_signaal_nooit_procedureel_zonder_document(tmp_path):
    # Geen einddocument en geen inhoudelijke dod → "Afgerond: <scope>", nooit de checklist-tekst.
    radar = RadarStore(f"{tmp_path}/radar.json")
    p = {"id": "p2", "owner": "harry_hemp", "scope": "Massa-verlies schoenzolen",
         "outcome": "checklist voltooid (5/5) — goedgekeurd na review", "dod_outcome": ""}
    it = radar.get(signal_from_project(radar, p, ""))
    assert it["content"] == "Afgerond: Massa-verlies schoenzolen"
    assert "checklist voltooid" not in it["content"]


def test_backfill_herschrijft_procedureel_maar_spaart_mens(tmp_path):
    radar = RadarStore(f"{tmp_path}/radar.json")

    class Ledger:
        def by_status(self, st):
            return [{"id": "p1", "scope": "Elastan"}] if st == "done" else []

    class Docs:
        def read(self, pid):
            return "## Conclusie\nPHA-blend komt dichtst bij elastan maar is 40% duurder." if pid == "p1" else ""

    proc = radar.add(role="harry", feed=FEED, kind=KIND, content="goedgekeurd na review",
                     link="/project?id=p1")
    mens = radar.add(role="harry", feed=FEED, kind=KIND, content="Zelf mooi samengevat",
                     link="/project?id=p1b")
    radar.set_status(proc, "goedgekeurd")
    res = backfill_signal_content(Ledger(), radar, Docs())
    assert res["updated"] == 1
    assert radar.get(proc)["content"].startswith("PHA-blend")
    assert radar.get(mens)["content"] == "Zelf mooi samengevat"   # mens-tekst blijft staan


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
