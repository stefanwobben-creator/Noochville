"""De opruiming van de embedding-indexen: gegrond op levende ids, droge loop, fail-closed.

Nalatenschap van de adres-sleutel (zie test_embed_sleutel.py). Deze module gooit 476 MB weg op prod,
dus de vraag is niet of hij werkt maar of hij de JUISTE dingen weggooit — en wat hij doet als hij
het niet zeker weet.
"""
from __future__ import annotations

import json
import os

from nooch_village.embed_opruimen import levende_ids, opruimen
from nooch_village.kennis_embeddings import EmbeddingStore
from nooch_village.kennisbank import KennisbankStore
from nooch_village.radar_store import RadarStore

INDEX = "kennisbank_embeddings.json"


def _index(dd, sleutels: list[str]) -> str:
    pad = os.path.join(str(dd), INDEX)
    st = EmbeddingStore(pad)
    for k in sleutels:
        st.upsert(k, "tekst van " + k, [0.1, 0.2, 0.3])
    st.save()
    return pad


def _kennisbank(dd, n: int = 2) -> list[str]:
    kb = KennisbankStore(os.path.join(str(dd), "kennisbank.json"))
    return [kb.add(f"inzicht {i}", why="omdat") for i in range(n)]


# ── Wat er weggaat, en wat niet ──────────────────────────────────────────────

def test_afval_gaat_weg_en_levende_ids_blijven(tmp_path):
    echt = _kennisbank(tmp_path)
    _index(tmp_path, echt + ["135585706102912", "135585706099648"])
    v = opruimen(str(tmp_path), INDEX, apply=True)
    assert v["entries_voor"] == 4 and v["entries_na"] == 2
    assert v["weg"] == 2 and v["adres_achtig"] == 2
    over = {k for k, _ in EmbeddingStore(os.path.join(str(tmp_path), INDEX)).items()}
    assert over == set(echt)


def test_een_levende_id_blijft_ook_als_de_tekst_veranderde(tmp_path):
    """Opruimen is goedkoop maar niet gratis: een onterecht verwijderde vector kost een embed-call,
    en die calls zijn juist het schaarse goed. Een veranderde tekst regelt `vectors_for` zelf via de
    hash-vergelijking — daar hoeft deze opruiming niet op vooruit te lopen."""
    echt = _kennisbank(tmp_path, 1)
    pad = _index(tmp_path, echt)
    st = EmbeddingStore(pad); st.upsert(echt[0], "HEEL ANDERE TEKST", [0.9]); st.save()
    opruimen(str(tmp_path), INDEX, apply=True)
    assert [k for k, _ in EmbeddingStore(pad).items()] == echt


def test_de_droge_loop_is_de_default_en_schrijft_niets(tmp_path):
    echt = _kennisbank(tmp_path)
    pad = _index(tmp_path, echt + ["999999999999"])
    voor = os.path.getsize(pad)
    v = opruimen(str(tmp_path), INDEX)                    # geen apply
    assert v["weg"] == 1 and v["toegepast"] is False and v["reden"] == "droge loop"
    assert os.path.getsize(pad) == voor
    assert len(list(EmbeddingStore(pad).items())) == 3


def test_twee_keer_toepassen_verandert_niets_meer(tmp_path):
    """Idempotent: een tweede run mag niet nóg een keer 'weg: n' rapporteren."""
    echt = _kennisbank(tmp_path)
    _index(tmp_path, echt + ["135585706102912"])
    opruimen(str(tmp_path), INDEX, apply=True)
    tweede = opruimen(str(tmp_path), INDEX, apply=True)
    assert tweede["weg"] == 0 and tweede["reden"] == "niets op te ruimen"


# ── Fail-closed: op grond van niet-weten gooi je niets weg ───────────────────

def test_zonder_leesbaar_corpus_wordt_er_niets_verwijderd(tmp_path):
    """Een lege verzameling levende ids betekent hier 'ik weet het niet', niet 'alles mag weg'.
    Zonder deze poort wist een ontbrekende kennisbank.json de hele index."""
    pad = _index(tmp_path, ["135585706102912", "kb_echt"])   # géén kennisbank.json
    v = opruimen(str(tmp_path), INDEX, apply=True)
    assert v["weg"] == 0
    assert "fail-closed" in v["reden"]
    assert len(list(EmbeddingStore(pad).items())) == 2


def test_een_onbekende_index_raakt_hij_niet_aan(tmp_path):
    _kennisbank(tmp_path)
    pad = os.path.join(str(tmp_path), "iets_anders.json")
    EmbeddingStore(pad).save()
    with open(pad, "w") as f:
        json.dump({"x": {"h": "1", "v": [0.1]}}, f)
    v = opruimen(str(tmp_path), "iets_anders.json", apply=True)
    assert v["weg"] == 0 and len(list(EmbeddingStore(pad).items())) == 1


def test_een_ontbrekende_index_is_geen_fout(tmp_path):
    v = opruimen(str(tmp_path), INDEX, apply=True)
    assert v["bestond"] is False and v["weg"] == 0


# ── De radar-index heeft twee gebruikers ────────────────────────────────────

def test_de_radar_index_houdt_ook_de_niet_goedgekeurde_signalen(tmp_path):
    """DE VAL. `radar_clusters` indexeert ALLE radar-items, `_signalen` alleen de goedgekeurde.
    Opruimen op de goedgekeurde verzameling zou het werk van de ander weggooien."""
    radar = RadarStore(os.path.join(str(tmp_path), "radar.json"))
    goed = radar.add(role="scout", feed="f", kind="markt", content="wel", source="rss")
    radar.set_status(goed, "goedgekeurd")
    wacht = radar.add(role="scout", feed="f", kind="markt", content="nog niet", source="rss")
    levend = levende_ids(str(tmp_path), "radar_embeddings.json")
    assert goed in levend and wacht in levend
