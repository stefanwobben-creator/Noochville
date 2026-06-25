"""Weekrapport/digest in de cockpit: vat samen wat er de afgelopen 7 dagen nieuw is
(goedgekeurde woorden, linkbuilding-doelwitten, marktinteresse). Pure functie + render."""
from __future__ import annotations
import time

from nooch_village.cockpit import compute_digest, _render_digest, _within


def _d(days_ago: int, now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now - days_ago * 86400))


def test_within_venster():
    now = time.time()
    assert _within(_d(0, now), now, 7)
    assert _within(_d(6, now), now, 7)
    assert not _within(_d(30, now), now, 7)
    assert not _within("", now, 7)
    assert not _within("geen-datum", now, 7)


def test_digest_neemt_alleen_recent_mee():
    now = time.time()
    library = {
        "vegan sneakers":   {"status": "approved", "date": _d(1, now),
                             "evidence": {"interest": 800}, "locale": "en"},
        "oud woord":        {"status": "approved", "date": _d(40, now)},
        "afgewezen woord":  {"status": "forbidden", "date": _d(1, now)},
    }
    links = [
        {"title": "Best Vegan Sneakers", "source": "Ecothes", "priority": "hoog",
         "link": "https://x", "first_seen": _d(2, now)},
        {"title": "Oude gids", "source": "Y", "priority": "midden",
         "link": "https://y", "first_seen": _d(20, now)},
    ]
    comp_cands = [{"brand": "Flamingos Life", "first_seen": _d(1, now)},
                  {"brand": "OudMerk", "first_seen": _d(50, now)}]
    dg = compute_digest(library, links, comp_cands, ["LØCI", "Merrell"], now)

    # 'vegan sneakers' (meerwoord, geen mega-volume) → doelwit
    assert [w["word"] for w in dg["new_targets"]] == ["vegan sneakers"]   # geen oud/afgewezen
    assert dg["new_targets"][0]["interest"] == 800
    assert [l["title"] for l in dg["new_links"]] == ["Best Vegan Sneakers"]
    assert dg["new_competitors"] == ["Flamingos Life"]
    assert dg["monitored_competitors"] == ["LØCI", "Merrell"]


def test_digest_sorteert_links_op_prioriteit():
    now = time.time()
    links = [
        {"title": "midden-gids", "priority": "midden", "link": "a", "first_seen": _d(1, now)},
        {"title": "hoog-gids",   "priority": "hoog",   "link": "b", "first_seen": _d(1, now)},
    ]
    dg = compute_digest({}, links, [], [], now)
    assert [l["priority"] for l in dg["new_links"]] == ["hoog", "midden"]


def test_render_toont_weekrapport_en_inhoud():
    now = time.time()
    dg = compute_digest(
        {"vegan sneakers": {"status": "approved", "date": _d(1, now),
                            "evidence": {"interest": 800}, "locale": "en"}},
        [{"title": "Best Vegan Sneakers", "priority": "hoog", "link": "https://x",
          "first_seen": _d(1, now)}],
        [], ["LØCI"], now)
    html = _render_digest(dg)
    assert "Weekrapport" in html
    assert "vegan sneakers" in html
    assert "Best Vegan Sneakers" in html
    assert "LØCI" in html


def test_render_leeg_is_vriendelijk():
    html = _render_digest(compute_digest({}, [], [], [], time.time()))
    assert "Niks nieuws" in html
