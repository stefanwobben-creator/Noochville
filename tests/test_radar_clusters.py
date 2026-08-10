"""Radar: onderwerp-clustering met bronnen-teller, en inhoudelijke nieuwheid — strikt gescheiden.

Twee mechanismen, en de tests bewaken vooral dat ze elkaar niet opeten:

  1. **Clustering + bronnen-teller** is een BEREKENING. Hij groepeert en telt; hij oordeelt niet en
     gooit niets weg. Het getal dat telt is het aantal VERSCHILLENDE bronnen — acht vermeldingen
     uit één feed is één bron die zichzelf herhaalt, geen trend.
  2. **Nieuwheid** is het oordeel, en draait BINNEN de cluster op de inhoud. De harde regel:
     onderwerp-bekend is niet inhoud-bekend, dus een nieuw feit in een bekend onderwerp moet
     individueel opduiken.

En over allebei heen: fail-soft en recall-veilig. Geen embeddings → lexicaal clusteren. Geen
Kroniek → alles nieuw. Een signaal verdwijnt nooit omdat een laag stuk was — dat is het soort
stille fout waar je maanden later achter komt.
"""
from __future__ import annotations

import time

import pytest

from nooch_village import cockpit2, founder_taken, radar_clusters, radar_nieuwheid
from nooch_village import founder_flow as ff

DAG = 86400


@pytest.fixture
def dd(tmp_path):
    d = str(tmp_path / "poc")
    cockpit2._bootstrap(d)
    return d


def _sig(sid, content, *, source="fashionunited.com", dagen_terug=1, rationale="", role="harry_hemp"):
    return {"id": sid, "content": content, "rationale": rationale, "source": source,
            "feed": "Material Innovation", "role": role, "status": "wacht",
            "at": time.time() - dagen_terug * DAG, "published_at": ""}


def _voeg_toe(st, content, *, source, dagen_terug=1, rationale=""):
    rid = st.radar.add(role="harry_hemp", feed="Material Innovation", kind="s",
                       content=content, rationale=rationale, source=source)
    it = st.radar.get(rid)
    it["at"] = time.time() - dagen_terug * DAG
    return rid


# ── 1. De bronnen-teller ─────────────────────────────────────────────────────

def test_acht_vermeldingen_uit_een_bron_tellen_als_een_bron():
    """De guard waar het hele mechanisme om draait. Wie op vermeldingen stuurt, wordt geregeerd
    door de luidruchtigste feed."""
    leden = [_sig(f"s{n}", f"Mycelium leer variant {n}", source="fashionunited.com")
             for n in range(8)]
    assert len(leden) == 8
    assert len(radar_clusters.bronnen_van(leden)) == 1


def test_acht_bronnen_tellen_als_acht():
    leden = [_sig(f"s{n}", f"Mycelium leer variant {n}", source=f"bron{n}.com") for n in range(8)]
    assert len(radar_clusters.bronnen_van(leden)) == 8


def test_bron_valt_terug_op_link_dan_feed_dan_onbekend():
    zonder = {"id": "a", "content": "x", "feed": "Material Innovation"}
    assert radar_clusters.bron_van(zonder) == "material innovation"
    met_link = {"id": "b", "content": "x", "link": "https://www.mdpi.com/artikel/1"}
    assert radar_clusters.bron_van(met_link) == "www.mdpi.com"
    # Herkomstloos telt als ÉÉN bron, niet als n: anders zouden acht anonieme signalen als acht
    # onafhankelijke bevestigingen lezen.
    leeg = [{"id": str(n), "content": "x"} for n in range(8)]
    assert radar_clusters.bronnen_van(leeg) == {"onbekend"}


# ── 2. Clustering ────────────────────────────────────────────────────────────

def test_clustering_groepeert_op_onderwerp_en_scheidt_de_rest():
    leden = ([_sig(f"m{n}", f"Mycelium paddenstoelvezel kweken proces {n}",
                   source=f"bron{n}.com") for n in range(4)]
             + [_sig("a1", "Ananasvezel Pinatex fabriek Filipijnen", source="mdpi.com")])
    clusters = radar_clusters.cluster_signalen(leden, semantisch=False)
    maten = sorted(len(c["leden"]) for c in clusters)
    assert maten == [1, 4]
    assert all(c["modus"] == "lexicaal" for c in clusters)


def test_clustering_is_deterministisch():
    """Een clustering die per page-load verspringt is onbruikbaar om op te sturen."""
    leden = [_sig(f"m{n}", f"Mycelium kweken variant {n}", source=f"b{n}.com", dagen_terug=n)
             for n in range(6)]
    eerst = radar_clusters.cluster_signalen(leden, semantisch=False)
    for _ in range(3):
        opnieuw = radar_clusters.cluster_signalen(list(reversed(leden)), semantisch=False)
        assert [c["sleutel"] for c in opnieuw] == [c["sleutel"] for c in eerst]


def test_geen_embeddings_valt_terug_op_lexicaal_en_valt_niet_stil(monkeypatch):
    """Fail-soft: zonder sleutel/SDK moet de radar clusteren, niet stoppen."""
    monkeypatch.setattr(radar_clusters, "_vectoren", lambda *a, **k: {})
    leden = [_sig(f"m{n}", f"Mycelium kweken variant {n}", source=f"b{n}.com") for n in range(3)]
    clusters = radar_clusters.cluster_signalen(leden, data_dir="/bestaat/niet")
    assert clusters and sum(len(c["leden"]) for c in clusters) == 3
    assert clusters[0]["modus"] == "lexicaal"


def test_clusterdrempel_is_configureerbaar():
    leden = [_sig("a", "Mycelium leer kweken", source="x.com"),
             _sig("b", "Mycelium leer productie", source="y.com")]
    los = radar_clusters.cluster_signalen(leden, semantisch=False, drempel=0.99)
    samen = radar_clusters.cluster_signalen(leden, semantisch=False, drempel=0.01)
    assert len(los) == 2 and len(samen) == 1


def test_geen_signaal_verdwijnt_bij_het_clusteren():
    leden = [_sig(f"s{n}", f"Onderwerp {n % 3} variant {n}", source=f"b{n}.com") for n in range(12)]
    clusters = radar_clusters.cluster_signalen(leden, semantisch=False)
    ids = {i["id"] for c in clusters for i in c["leden"]}
    assert ids == {i["id"] for i in leden}


# ── 3. Trend ─────────────────────────────────────────────────────────────────

def test_trend_beslist_op_bronnen_niet_op_vermeldingen():
    """Twintig vermeldingen nu uit één bron, tegen twee bronnen ervoor: dat is geen stijging."""
    nu = time.time()
    leden = ([_sig(f"n{n}", "Mycelium", source="fashionunited.com", dagen_terug=3)
              for n in range(20)]
             + [_sig("o1", "Mycelium", source="mdpi.com", dagen_terug=40),
                _sig("o2", "Mycelium", source="scienmag.com", dagen_terug=40)])
    t = radar_clusters.trend_van(leden, nu=nu, venster_dagen=30)
    assert t["signalen"] == 20 and t["bronnen"] == 1
    assert t["eerder_bronnen"] == 2
    assert t["richting"] == "dalend"          # meer lawaai, minder bronnen


def test_trend_stijgend_bij_meer_bronnen():
    nu = time.time()
    leden = ([_sig(f"n{n}", "Mycelium", source=f"bron{n}.com", dagen_terug=3) for n in range(5)]
             + [_sig("o1", "Mycelium", source="mdpi.com", dagen_terug=40)])
    t = radar_clusters.trend_van(leden, nu=nu, venster_dagen=30)
    assert t["bronnen"] == 5 and t["eerder_bronnen"] == 1 and t["richting"] == "stijgend"


def test_trend_venster_is_configureerbaar():
    nu = time.time()
    leden = [_sig("a", "Mycelium", source="x.com", dagen_terug=10)]
    assert radar_clusters.trend_van(leden, nu=nu, venster_dagen=30)["signalen"] == 1
    assert radar_clusters.trend_van(leden, nu=nu, venster_dagen=5)["signalen"] == 0


def test_published_at_wint_van_ingest_moment():
    """Een oud artikel dat vandaag binnenkomt is historisch bewijs, geen vers nieuws."""
    oud = {"id": "a", "content": "x", "at": time.time(),
           "published_at": "2020-01-01T10:00:00+00:00"}
    assert radar_clusters.tijdstip(oud) < time.time() - 365 * DAG


# ── 4. Nieuwheid: onderwerp-bekend is niet inhoud-bekend ─────────────────────

class _Geheugen:
    """Een geheugen dat één onderwerp kent — de kortste weg naar de kernvraag."""

    def __init__(self, kent: str, *, ontploft: bool = False):
        self.kent, self.ontploft = kent, ontploft

    def run(self, payload, context=None):
        if self.ontploft:
            raise RuntimeError("kennisbank onleesbaar")
        vraag = (payload or {}).get("vraag", "").lower()
        raakt = self.kent.lower() in vraag
        return {"ok": True, "bekend": raakt, "treffers": 3 if raakt else 0,
                "inzichten": [{"titel": self.kent}] if raakt else [],
                "kaarten": [], "projecten": [], "kroniek": {}, "context": []}


def test_nieuw_feit_in_bekend_onderwerp_komt_individueel_boven(dd):
    """DE harde regel. Het dorp kent mycelium; dit signaal voegt een leverancier, een land en een
    temperatuur toe. Dat moet naar boven komen, niet invouwen achter 'onderwerp is bekend'."""
    oordeel = radar_nieuwheid.beoordeel_signaal(
        "Mycelium: kweker Ecovative levert vanaf Q3 in Portugal bij 40 graden",
        data_dir=dd, skill=_Geheugen("mycelium"))
    assert oordeel["nieuw"] is True
    assert not oordeel["gefaald"]
    assert "known topic" in oordeel["reden"]
    kernen = set(oordeel["kernen"])
    assert "ecovative" in kernen and "portugal" in kernen        # leverancier + plaats
    assert "40" in kernen                                        # het getal telt expliciet mee


def test_bekende_inhoud_in_bekend_onderwerp_vouwt_in(dd):
    oordeel = radar_nieuwheid.beoordeel_signaal("Mycelium", data_dir=dd,
                                                skill=_Geheugen("mycelium"))
    assert oordeel["nieuw"] is False
    assert "already cover this" in oordeel["reden"]


def test_onbekend_onderwerp_is_nieuw(dd):
    oordeel = radar_nieuwheid.beoordeel_signaal("Ananasvezel uit de Filipijnen",
                                                data_dir=dd, skill=_Geheugen("mycelium"))
    assert oordeel["nieuw"] is True and "nothing on this yet" in oordeel["reden"]


def test_gefaalde_geheugencheck_laat_het_signaal_staan(dd):
    """Recall-veilig: nooit een signaal verbergen omdat de geheugencheck stuk was."""
    oordeel = radar_nieuwheid.beoordeel_signaal("Mycelium kweker", data_dir=dd,
                                                skill=_Geheugen("mycelium", ontploft=True))
    assert oordeel["nieuw"] is True
    assert oordeel["gefaald"] is True
    assert "shown to be safe" in oordeel["reden"]


def test_gefaald_oordeel_wordt_niet_gecachet(dd):
    """Anders bevriest één storing het oordeel 'nieuw' voor altijd."""
    items = [_sig("a", "Mycelium kweker")]
    stuk = _Geheugen("mycelium", ontploft=True)
    eerst = radar_nieuwheid.beoordeel_items(items, data_dir=dd, skill=stuk)
    assert eerst["a"]["gefaald"] is True
    heel = _Geheugen("mycelium")
    daarna = radar_nieuwheid.beoordeel_items(items, data_dir=dd, skill=heel)
    assert daarna["a"]["gefaald"] is False       # opnieuw gedraaid, niet uit de cache


def test_oordeel_wordt_wel_gecachet_als_het_lukte(dd):
    items = [_sig("a", "Mycelium")]
    radar_nieuwheid.beoordeel_items(items, data_dir=dd, skill=_Geheugen("mycelium"))

    class _Ontploft:
        def run(self, *a, **k):
            raise AssertionError("de cache had dit moeten opvangen")

    uit = radar_nieuwheid.beoordeel_items(items, data_dir=dd, skill=_Ontploft())
    assert uit["a"]["nieuw"] is False


def test_nieuwheid_draait_binnen_de_cluster(dd):
    """Een cluster bevat zowel invouwers als individueel opkomende signalen. Zou de nieuwheid op
    clusterniveau draaien, dan verdween het tweede type."""
    leden = [_sig("bekend", "Mycelium"),
             _sig("nieuw", "Mycelium kweker Ecovative Portugal 40 graden")]
    clusters = radar_clusters.cluster_signalen(leden, semantisch=False, drempel=0.01)
    assert len(clusters) == 1
    oordelen = radar_nieuwheid.beoordeel_items(leden, data_dir=dd, skill=_Geheugen("mycelium"),
                                               gebruik_cache=False)
    radar_nieuwheid.splits(clusters, oordelen)
    c = clusters[0]
    assert [i["id"] for i in c["nieuw"]] == ["nieuw"]
    assert [i["id"] for i in c["ingevouwen"]] == ["bekend"]


def test_invouwen_gooit_niets_weg(dd):
    """Invouwen is zichtbaar en omkeerbaar: het ingevouwen signaal blijft volledig aanwezig."""
    leden = [_sig("bekend", "Mycelium"), _sig("nieuw", "Mycelium kweker Ecovative")]
    clusters = radar_clusters.cluster_signalen(leden, semantisch=False, drempel=0.01)
    oordelen = radar_nieuwheid.beoordeel_items(leden, data_dir=dd, skill=_Geheugen("mycelium"),
                                               gebruik_cache=False)
    c = radar_nieuwheid.splits(clusters, oordelen)[0]
    assert len(c["leden"]) == 2                                  # de cluster houdt alles
    assert len(c["nieuw"]) + len(c["ingevouwen"]) == 2
    assert c["ingevouwen"][0]["content"] == "Mycelium"           # volledig signaal, geen stub


# ── 5. De koppeling met de Founder Flow ──────────────────────────────────────

def test_radar_beeld_telt_bronnen_en_houdt_alles(dd):
    st = cockpit2._Stores(dd)
    for n in range(8):
        _voeg_toe(st, f"Mycelium leer kweken variant {n}", source="fashionunited.com")
    _voeg_toe(st, "Ananasvezel Pinatex fabriek", source="mdpi.com")
    beeld = founder_taken.radar_beeld(cockpit2._Stores(dd), dd)
    mycelium = max(beeld["clusters"], key=lambda c: len(c["leden"]))
    assert len(mycelium["leden"]) == 8
    assert mycelium["trend"]["bronnen"] == 1                     # één bron, acht vermeldingen
    assert sum(len(c["open"]) for c in beeld["clusters"]) == 9   # niets kwijt


def test_wachtrij_toont_op_a_en_b_alles_en_lekt_dus_niets(dd):
    """Zou de wachtrij op A/B al gefilterd zijn op het AI-oordeel, dan verraadt het lidmaatschap
    het voorstel en stemt elk blind label per constructie in — 100% zonder iets te meten."""
    st = cockpit2._Stores(dd)
    for n in range(4):
        _voeg_toe(st, f"Onderwerp {n} met eigen inhoud", source=f"bron{n}.com")
    for niveau in ("A", "B"):
        rijen = founder_taken.wachtrij(cockpit2._Stores(dd), dd, ff.RADAR, niveau=niveau)
        assert len(rijen) == 4


def test_wachtrij_vouwt_pas_vanaf_c(dd, monkeypatch):
    st = cockpit2._Stores(dd)
    _voeg_toe(st, "Mycelium", source="a.com")
    _voeg_toe(st, "Mycelium kweker Ecovative Portugal", source="b.com")
    monkeypatch.setattr(radar_nieuwheid, "beoordeel_items",
                        lambda items, **k: {i["id"]: {"nieuw": "Ecovative" in i["content"],
                                                      "reden": "test", "gefaald": False}
                                            for i in items})
    assert len(founder_taken.wachtrij(cockpit2._Stores(dd), dd, ff.RADAR, niveau="B")) == 2
    op_c = founder_taken.wachtrij(cockpit2._Stores(dd), dd, ff.RADAR, niveau="C")
    assert len(op_c) == 1 and "Ecovative" in op_c[0]["titel"]


def test_clustering_heeft_geen_trede_maar_de_nieuwheid_wel():
    """Clustering en de bronnen-teller zijn berekend, dus ze horen niet in de tredes. Het enige
    radar-oordeel dat een trede kent is nieuwheid."""
    assert ff.OORDELEN[ff.RADAR] == ("nieuw", "bekend")
    assert "keep" not in ff.OORDELEN[ff.RADAR] and "dismiss" not in ff.OORDELEN[ff.RADAR]


def test_oude_relevantie_labels_tellen_niet_mee_op_de_nieuwheids_as(dd):
    """De as is veranderd van relevantie naar nieuwheid. Oude keep/dismiss-labels blijven in de
    append-only log staan, maar mogen de nieuwe meting niet vullen — dat zou een relevantie-
    oordeel afzetten tegen een nieuwheids-voorstel."""
    import json
    import os
    with open(os.path.join(dd, ff.BESTAND), "w", encoding="utf-8") as f:
        for n in range(40):
            f.write(json.dumps({"taak": ff.RADAR, "item": f"oud{n}", "mens": "keep",
                                "ai": "keep", "ai_getoond": False, "correctie": False,
                                "niveau": "A", "ts": 1_000_000 + n}) + "\n")
    labels = ff.alle(dd)
    assert len(labels) == 40                                     # de log is niet herschreven
    assert ff.overeenstemming(labels, ff.RADAR, 60)["n"] == 0    # maar ze meten niet mee
    kan, reden = ff.promoveerbaar(labels, ff.RADAR, "A", ff.instellingen(dd, ff.RADAR))
    assert not kan and "0/30 blind examples" in reden
