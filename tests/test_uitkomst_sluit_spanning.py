"""Een uitkomst kiezen sluit de bronspanning. In één handeling.

HET GEVAL (3 sep 2026): Stefan verwerkte "MITH en STCB subsidie admin proces" tot een project. Het
project werd gemaakt (07:03), de spanning bleef staan. Twee dingen zaten fout:

1. `mark_done` zette `read` en `processed` — dezelfde velden als `mark_item_processed` — terwijl
   `open_for_targets` alleen op `archived`/`deleted` filterde. Sluiten schreef dus een staat die de
   wachtrij niet als gesloten kende. Dat gold voor ÉLKE spanning.
2. De projectroute is een link naar de wizard en droeg geen `nid` mee, dus de wizard kon niets
   terugmelden. Zelfs de geslaagde weg liet de bron open, met een leeg `project_id`.
"""
from __future__ import annotations

import time

from nooch_village.notifications import NotifStore


def _store(tmp_path):
    return NotifStore(str(tmp_path / "notifications.json"))


def test_sluiten_haalt_het_item_uit_de_wachtrij(tmp_path):
    """DE KERN. Hiervoor bleef een gesloten spanning eeuwig in de inbox staan."""
    st = _store(tmp_path)
    n = st.add("person", "p1", "", by="zelf", snippet="een spanning")
    tg = [("person", "p1")]
    assert len(st.open_for_targets(tg)) == 1

    st.mark_done(n["id"], by="Stefan")
    assert st.open_for_targets(tg) == []
    assert st.status_of(st._find(n["id"])) == "klaar"


def test_verwerkt_is_geen_gesloten(tmp_path):
    """`mark_item_processed` betekent 'bekeken/afgehandeld', geen besluit. Die twee mochten nooit
    dezelfde staat schrijven — dat wás de bug."""
    st = _store(tmp_path)
    n = st.add("person", "p1", "", by="zelf", snippet="een spanning")
    st.mark_item_processed(n["id"])
    assert len(st.open_for_targets([("person", "p1")])) == 1     # blijft staan
    assert st.status_of(st._find(n["id"])) == "verwerkt"


def test_geen_stille_retro_close_van_oude_items(tmp_path):
    """Zes bestaande items dorp-breed dragen `processed` zonder ooit bewust gesloten te zijn. Die
    alsnog dichtdoen zou geschiedenis herschrijven op een aanname."""
    st = _store(tmp_path)
    n = st.add("person", "p1", "", by="zelf", snippet="oud item")
    st._find(n["id"])["processed"] = True                        # zoals de oude mark_done deed
    assert len(st.open_for_targets([("person", "p1")])) == 1


def test_done_at_legt_vast_wanneer(tmp_path):
    st = _store(tmp_path)
    n = st.add("person", "p1", "", by="zelf", snippet="x")
    voor = time.time()
    st.mark_done(n["id"])
    assert st._find(n["id"])["done_at"] >= voor


def test_de_uitkomst_blijft_leesbaar_na_sluiten(tmp_path):
    """Sluiten mag het record niet wissen: de raadsvergadering leest terug wát eruit kwam."""
    st = _store(tmp_path)
    n = st.add("person", "p1", "", by="zelf", snippet="x")
    st.add_outcome(n["id"], intent="doen", otype="project", ref="PID1", label="project: subsidie")
    st.mark_done(n["id"])
    verw = st.verwerkingen_of(st._find(n["id"]))
    assert len(verw) == 1 and verw[0]["ref"] == "PID1"
