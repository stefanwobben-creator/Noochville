"""Fase 3 — Synthesist: de kennisgraaf gaat ademen via creatieve links tussen kaartjes.
Pure engine (bridge/duplicaat/dichtheid) + de skill + de runner die een gelinkt synthese-kaartje maakt."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.card_synthesis import bridge_pairs, duplicate_pairs, graph_density
from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight, GroundingStatus
from nooch_village.synthesist import synthesize_once, synthesize_round, density


def _cards():
    return [
        {"id": "a", "text": "consumer frame is collapsing culturally in the book corpus", "links_to": []},
        {"id": "b", "text": "vegan sneakers are mostly plastic, a marketing trick", "links_to": []},
        {"id": "c", "text": "consumer frame collapsing culturally book corpus citizen", "links_to": []},
    ]


def test_bridge_en_duplicate_en_dichtheid():
    cards = _cards()
    dups = duplicate_pairs(cards, threshold=0.4)
    assert any({a, b} == {"a", "c"} for _s, a, b in dups)     # a~c bijna gelijk
    g = graph_density(cards)
    assert g["cards"] == 3 and g["links"] == 0


def test_bridge_negeert_reeds_verbonden():
    cards = _cards()
    cards[0]["links_to"] = ["b"]                               # a al aan b gelinkt
    assert all({a, b} != {"a", "b"} for _s, a, b in bridge_pairs(cards, lo=0.0, hi=1.0))


def _notes(tmp_path):
    ns = NotesStore(str(tmp_path / "notes.json"))
    ns.add(Insight(id="a", claim="The consumer frame is collapsing culturally.",
                   source="harry", status=GroundingStatus.SUPPORTED,
                   grounds="ngram laat een daling zien"))
    ns.add(Insight(id="b", claim="Most vegan sneakers are plastic, a marketing trick.",
                   source="harry", status=GroundingStatus.SUPPORTED,
                   grounds="PU-leer is plastic"))
    return ns


def test_synthesize_once_maakt_gelinkt_kaartje(tmp_path):
    ns = _notes(tmp_path)
    ctx = SimpleNamespace()
    resp = ("SYNTHESE: de culturele kanteling van consument naar burger is de hefboom om "
            "plastic-vegan als marketingtruc te ontmaskeren\nWAAROM: sluit aan op Noochs missie")
    with patch("nooch_village.llm.reason", return_value=resp):
        r = synthesize_once(ns, ctx, lo=0.0, hi=1.0)
    assert r is not None and r["parents"] == ["a", "b"]
    syn = ns.get(r["id"])
    assert "synthese" in syn.tags and set(syn.links_to) == {"a", "b"}
    assert syn.claim.startswith("de culturele kanteling")
    # de ouders zien het synthese-kaartje nu als buur (graaf ademt)
    assert any(n.id == r["id"] for n in ns.neighbors("a"))


def test_synthesize_dedup_en_failclosed(tmp_path):
    ns = _notes(tmp_path)
    ctx = SimpleNamespace()
    resp = "SYNTHESE: x verbindt y\nWAAROM: z"
    with patch("nooch_village.llm.reason", return_value=resp):
        assert synthesize_once(ns, ctx, lo=0.0, hi=1.0) is not None
        assert synthesize_once(ns, ctx, lo=0.0, hi=1.0) is None   # a+b al gebridged
    # fail-closed: geen LLM → geen kaartje (vers pad)
    ns2 = NotesStore(str(tmp_path / "notes2.json"))
    ns2.add(Insight(id="a", claim="The consumer frame is collapsing.", source="harry",
                    status=GroundingStatus.SUPPORTED, grounds="ngram"))
    ns2.add(Insight(id="b", claim="Vegan sneakers are plastic.", source="harry",
                    status=GroundingStatus.SUPPORTED, grounds="PU"))
    with patch("nooch_village.llm.reason", return_value=None):
        assert synthesize_once(ns2, ctx, lo=0.0, hi=1.0) is None


def test_density_helper(tmp_path):
    ns = _notes(tmp_path)
    d = density(ns)
    assert d["cards"] == 2 and d["links"] == 0
