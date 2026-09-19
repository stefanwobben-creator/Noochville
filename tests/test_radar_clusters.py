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

from nooch_village import cockpit2, radar_clusters, radar_nieuwheid

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


def test_embedden_gaat_in_batches_niet_in_een_reuzencall(dd):
    """De embed-API neemt geen willekeurig grote batch aan — de kennisbank-backfill werkt niet
    voor niets in groepjes van 20. Eén call met honderden teksten faalt, en omdat `embed_many`
    fail-soft is zou dat STIL neerkomen op lexicaal clusteren terwijl het scherm semantisch belooft."""
    groottes = []

    def _embed(texts):
        groottes.append(len(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]

    items = [_sig(f"s{n}", f"Signaal {n}", source=f"b{n}.com") for n in range(45)]
    radar_clusters._vectoren(items, dd, embed_fn=_embed, cap=100, batch=20)
    assert groottes == [20, 20, 5]
    assert max(groottes) <= 20


def test_render_embedt_hoogstens_de_cap(dd):
    """Een page-load mag geen lange API-sessie worden; de bulk hoort uit `radar_embed` te komen."""
    geteld = []

    def _embed(texts):
        geteld.extend(texts)
        return [[1.0, 0.0, 0.0] for _ in texts]

    items = [_sig(f"s{n}", f"Signaal {n}", source=f"b{n}.com") for n in range(200)]
    radar_clusters._vectoren(items, dd, embed_fn=_embed, cap=60, batch=20)
    assert len(geteld) == 60


def test_halve_index_clustert_eerlijk_lexicaal(dd):
    """Bij een gedeeltelijke index zou een signaal zonder vector cosinus 0 scoren tegen alles en
    dus altijd een eigen cluster worden — dat leest als 'apart onderwerp' terwijl het 'nog niet
    geïndexeerd' betekent. Dan liever eerlijk lexicaal voor de hele render."""
    items = [_sig(f"s{n}", f"Mycelium kweken variant {n}", source=f"b{n}.com") for n in range(6)]
    # Slechts de helft krijgt een vector.
    radar_clusters._vectoren(items[:3], dd, embed_fn=lambda t: [[1.0, 0.0] for _ in t],
                             cap=10, batch=20)
    clusters = radar_clusters.cluster_signalen(items, data_dir=dd,
                                               embed_fn=lambda t: [None for _ in t])
    assert all(c["modus"] == "lexicaal" for c in clusters)
    assert sum(len(c["leden"]) for c in clusters) == 6          # niets kwijt


def test_volledige_index_clustert_semantisch(dd):
    items = [_sig(f"s{n}", f"Mycelium kweken variant {n}", source=f"b{n}.com") for n in range(4)]
    clusters = radar_clusters.cluster_signalen(
        items, data_dir=dd, embed_fn=lambda t: [[1.0, 0.0, 0.0] for _ in t])
    assert all(c["modus"] == "semantisch" for c in clusters)
    assert len(clusters) == 1                                   # identieke vectoren → één onderwerp


def test_index_verliest_het_werk_van_een_andere_schrijver_niet(dd):
    """De index heeft twee schrijvers: de render (bijwerken per page-load) en de bulk-vuller.
    Op prod gaf dat een echte race — 'No such file or directory: radar_embeddings.json.tmp'.
    Wie zijn in-memory kopie wegschrijft, wist het werk van de ander. Daarom leest de schrijfkant
    onder het slot opnieuw in."""
    import os

    from nooch_village.kennis_embeddings import EmbeddingStore

    pad = os.path.join(dd, radar_clusters.INDEX_BESTAND)
    eigen = [_sig("mijn", "Mijn signaal")]

    # Een andere schrijver vult de index terwijl wij aan het embedden zijn: we simuleren dat door
    # 'm weg te schrijven ná het moment waarop `_vectoren` de store voor het eerst inlas.
    def _embed(texts):
        ander = EmbeddingStore(pad)
        ander.upsert("van-de-ander", "Ander signaal", [0.5, 0.5])
        ander.save()
        return [[1.0, 0.0] for _ in texts]

    radar_clusters._vectoren(eigen, dd, embed_fn=_embed, cap=10, batch=20)
    na = dict(EmbeddingStore(pad).items())
    assert "mijn" in na                              # ons eigen werk staat er...
    assert "van-de-ander" in na                      # ...en dat van de ander is niet gewist


def test_vul_index_is_idempotent(dd):
    calls = []

    def _embed(texts):
        calls.append(len(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]

    items = [_sig(f"s{n}", f"Signaal {n}", source=f"b{n}.com") for n in range(25)]
    eerst = radar_clusters.vul_index(items, dd, embed_fn=_embed, per_min=0,
                                     sleep_fn=lambda *_: None, log_fn=lambda *_: None)
    assert eerst["todo"] == 25 and eerst["gedaan"] == 25
    calls.clear()
    weer = radar_clusters.vul_index(items, dd, embed_fn=_embed, per_min=0,
                                    sleep_fn=lambda *_: None, log_fn=lambda *_: None)
    assert weer["todo"] == 0 and calls == []                    # tweede run kost niets


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










