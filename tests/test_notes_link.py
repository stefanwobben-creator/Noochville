"""Tests voor NotesStore.link — de graaf-rand (links_to vullen). Thread-vrij.

De link is de keystone onder de kennisgraaf: pas als kaartjes verbonden zijn,
kan de scientist kind-kaartjes ophangen en kan de Content Strategist clusters
combineren. Deze tests leggen de vier regels vast: gericht, persistent,
idempotent, fail-closed (onbestaand of naar-zichzelf).
"""
from __future__ import annotations

from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


def _kaart(kid: str, claim: str = "een claim", word: str | None = None) -> Insight:
    return Insight(id=kid, claim=claim, source="test", word=word)


def _store(tmp_path, *kaarten: Insight) -> NotesStore:
    s = NotesStore(str(tmp_path / "notes.json"))
    for k in kaarten:
        s.add(k)
    return s


def test_link_verbindt_gericht(tmp_path):
    """a -> b: b staat in a.links_to; de link wijst NIET terug."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    bron = s.link("a", "b")
    assert bron is not None
    assert "b" in bron.links_to
    assert s.get("b").links_to == []   # gericht, geen automatische terugkoppeling


def test_link_is_persistent(tmp_path):
    """Een link overleeft een herlaad van schijf."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    vers = NotesStore(str(tmp_path / "notes.json"))
    assert "b" in vers.get("a").links_to


def test_link_is_idempotent(tmp_path):
    """Tweemaal dezelfde link voegt niets dubbels toe."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    s.link("a", "b")
    assert s.get("a").links_to == ["b"]


def test_link_naar_onbestaand_kaartje_doet_niets(tmp_path):
    """Fail-closed: ontbreekt bron of doel, dan None en geen wijziging."""
    s = _store(tmp_path, _kaart("a"))
    assert s.link("a", "weg") is None        # doel bestaat niet
    assert s.get("a").links_to == []
    assert s.link("weg", "a") is None        # bron bestaat niet


def test_link_naar_zichzelf_doet_niets(tmp_path):
    """Een kaartje linkt niet naar zichzelf."""
    s = _store(tmp_path, _kaart("a"))
    assert s.link("a", "a") is None
    assert s.get("a").links_to == []


# ── brokje 2: link lezen (neighbors) ──────────────────────────────────────────

def _ids(kaarten):
    return sorted(k.id for k in kaarten)


def test_neighbors_vindt_uitgaande_link(tmp_path):
    """a -> b: neighbors(a) bevat b (de kant waar a naar wijst)."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    assert _ids(s.neighbors("a")) == ["b"]


def test_neighbors_vindt_inkomende_link(tmp_path):
    """a -> b: neighbors(b) bevat a (de kant die naar b wijst)."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    assert _ids(s.neighbors("b")) == ["a"]


def test_neighbors_beide_richtingen_ontdubbeld(tmp_path):
    """c -> a en a -> b: neighbors(a) = {b (uitgaand), c (inkomend)}, elk één keer."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"), _kaart("c"))
    s.link("a", "b")
    s.link("c", "a")
    assert _ids(s.neighbors("a")) == ["b", "c"]


def test_neighbors_telt_dubbele_richting_enkel(tmp_path):
    """a -> b en b -> a: neighbors(a) bevat b precies één keer."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    s.link("b", "a")
    assert _ids(s.neighbors("a")) == ["b"]


def test_neighbors_onbestaand_kaartje_is_leeg(tmp_path):
    """Fail-closed: een kaartje dat niet bestaat heeft geen buren."""
    s = _store(tmp_path, _kaart("a"))
    assert s.neighbors("weg") == []


def test_neighbors_zonder_links_is_leeg(tmp_path):
    """Een los kaartje zonder touwtjes heeft geen buren."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    assert s.neighbors("a") == []


# ── brokje 9: cluster lezen (samenhangend groepje rond een zaad) ──────────────

def test_cluster_zaad_eerst_dan_buren(tmp_path):
    """a-b en a-c: cluster(a) = [a, b, c] (zaad vooraan, buren erna)."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"), _kaart("c"))
    s.link("a", "b")
    s.link("a", "c")
    assert [n.id for n in s.cluster("a")] == ["a", "b", "c"]


def test_cluster_volgt_touwtjes_transitief(tmp_path):
    """a-b-c (keten): cluster(a) bereikt ook c, twee hops ver."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"), _kaart("c"))
    s.link("a", "b")
    s.link("b", "c")
    assert [n.id for n in s.cluster("a")] == ["a", "b", "c"]


def test_cluster_los_kaartje_is_alleen_zichzelf(tmp_path):
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    assert [n.id for n in s.cluster("a")] == ["a"]


def test_cluster_respecteert_max_size(tmp_path):
    """Ster met veel buren: max_size kapt het groepje af (zaad telt mee)."""
    s = _store(tmp_path, _kaart("hub"), *[_kaart(f"n{i}") for i in range(5)])
    for i in range(5):
        s.link("hub", f"n{i}")
    out = s.cluster("hub", max_size=3)
    assert len(out) == 3
    assert out[0].id == "hub"


def test_cluster_onbestaand_zaad_is_leeg(tmp_path):
    s = _store(tmp_path, _kaart("a"))
    assert s.cluster("weg") == []
