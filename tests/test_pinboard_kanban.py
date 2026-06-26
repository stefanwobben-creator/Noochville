"""Brok 1 — datamodel van het prikbord-Kanban-dorp: prikbord-store, DoD-contract op projecten,
project-graaf (links), WIP-instelling. Plus één handmatig gevulde keten als bewijs (idee → Harry →
Scout → Harry), gelinkt en via het prikbord. Geen autonome loop / cockpit (dat is brok 2/3)."""
from __future__ import annotations
import json

from nooch_village.pinboard import Pinboard, read_wip
from nooch_village.projects import ProjectLedger


def test_pinboard_post_claim_complete_dedup(tmp_path):
    pb = Pinboard(str(tmp_path / "pinboard.json"))
    bid = pb.post("request", "science", "Zoek elastaan-alternatief", by="scout")
    # dedup: zelfde verzoek niet dubbel
    assert pb.post("request", "science", "Zoek elastaan-alternatief", by="scout") == bid
    assert [i["id"] for i in pb.open("science")] == [bid]
    assert pb.open("copy") == []                       # andere tag → niet zichtbaar
    assert pb.claim(bid, "harry") is True
    assert pb.claim(bid, "iemand") is False            # al geclaimd
    assert pb.open("science") == []                    # geclaimd → niet meer open
    assert pb.complete(bid) is True
    # na done mag dezelfde titel opnieuw (nieuw briefje)
    assert pb.post("request", "science", "Zoek elastaan-alternatief") != bid


def test_pinboard_persistent(tmp_path):
    p = str(tmp_path / "pinboard.json")
    bid = Pinboard(p).post("outcome", "seed", "10 nieuwe seeds gevonden")
    assert Pinboard(p).get(bid)["title"] == "10 nieuwe seeds gevonden"   # overleeft herladen


def test_read_wip_default_en_config(tmp_path):
    (tmp_path / "data").mkdir(); (tmp_path / "config").mkdir()
    (tmp_path / "config" / "strategy.json").write_text(
        json.dumps({"wip": {"board": 5, "roles": {"trends": 2}}}), encoding="utf-8")
    w = read_wip(str(tmp_path / "data"))
    assert w["board"] == 5 and w["roles"]["trends"] == 2
    # geen config (geïsoleerd pad, geen config-buur) → default board 3
    iso = tmp_path / "iso" / "data"; iso.mkdir(parents=True)
    assert read_wip(str(iso))["board"] == 3


def test_project_dod_contract_en_default_future(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("harry", "Elastaan-alternatief onderzoeken", "human", status="future",
                     dod_outcome="Advies: past een natuurlijk elastaan-alternatief bij onze waarden?",
                     done_when="Onderbouwd ja/nee met >=1 bron per kandidaat, of 'geen gevonden'",
                     goes_to="scout")
    p = led.get(pid)
    assert p["status"] == "future"
    assert p["dod_outcome"].startswith("Advies") and "ja/nee" in p["done_when"] and p["goes_to"] == "scout"


def test_project_graph_links(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    a = led.create("harry", "A", "human", status="future")
    b = led.create("scout", "B", "human", status="future")
    assert led.link(a, b) is True
    assert led.link(a, b) is False                     # dedup
    assert led.link(a, a) is False                     # geen zelf-link
    # wederzijds zichtbaar
    assert [n["id"] for n in led.neighbors(a)] == [b]
    assert [n["id"] for n in led.neighbors(b)] == [a]


def test_handmatige_keten_als_bewijs(tmp_path):
    """De sokken-feasibility-keten met de hand opgebouwd: idee → Harry (wetenschap) → Scout
    (leveranciers) → Harry (review), gelinkt als één gesprek + via het prikbord aangeboden."""
    data = tmp_path / "data"; data.mkdir()
    led = ProjectLedger(str(data / "projects.json"))
    pb = Pinboard(str(data / "pinboard.json"))

    idee = led.create("the_source", "Sokken aanbieden in de checkout", "human", status="future",
                      dod_outcome="Besluit: voegen we sok-suggestie toe?", done_when="ja/nee met onderbouwing")
    harry = led.create("harry", "Wetenschappelijk elastaan-alternatief vinden", "human", status="future",
                       dod_outcome="Lijst kandidaat-materialen die bij onze waarden passen",
                       done_when="Per kandidaat een bron, of 'geen gevonden'", goes_to="scout",
                       links=[idee])
    led.link(idee, harry)
    # Harry levert een uitkomst op het prikbord; Scout's tag (supplier) krijgt een verzoek
    out = pb.post("outcome", "supplier", "3 kandidaat-elastaan-alternatieven", by="harry", links=[harry])
    scout = led.create("scout", "Leveranciers zoeken bij Harry's materialen", "human", status="future",
                       dod_outcome="Leverancierslijst die bij de materialen past",
                       done_when="Per leverancier contactinfo, of 'geen gevonden'", goes_to="harry",
                       links=[harry])
    led.link(harry, scout)
    pb.claim(out, "scout"); pb.link_project(out, scout); pb.complete(out)

    # Bewijs: het is één gelinkte keten van 3 projecten, met DoD op elk, en het briefje is afgehandeld.
    assert {n["id"] for n in led.neighbors(harry)} == {idee, scout}     # Harry is de spil
    assert all(led.get(x)["done_when"] for x in (idee, harry, scout))   # elk een done-criterium
    assert pb.get(out)["status"] == "done" and scout in pb.get(out)["links"]
    # persistentie
    assert ProjectLedger(str(data / "projects.json")).neighbors(harry).__len__() == 2
