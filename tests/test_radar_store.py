"""RadarStore + feed-config: toevoegen, dedup, seen, status-overgangen, feeds_for_role."""
from __future__ import annotations

import json

from nooch_village.radar_store import RadarStore, feeds_for_role, load_feeds

_ROLE = "concurrent_scout"


def _store(tmp_path):
    return RadarStore(str(tmp_path / "radar.json"))


def test_add_pending_and_get(tmp_path):
    r = _store(tmp_path)
    rid = r.add(role=_ROLE, feed="Competitor", kind="concurrent", content="Veja",
                rationale="lancering", source="example.com", link="https://x/veja",
                published_at="2019-03-14T10:00:00Z")
    assert rid
    it = r.get(rid)
    assert it["status"] == "wacht" and it["role"] == _ROLE and it["kind"] == "concurrent"
    assert it["published_at"] == "2019-03-14T10:00:00Z"    # publicatiedatum bewaard, los van 'at'
    assert it["at"] != it["published_at"]                  # ingest-tijd != artikeldatum
    pend = r.pending(_ROLE)
    assert len(pend) == 1 and pend[0]["id"] == rid
    assert r.approved(_ROLE) == []


def test_add_dedup_over_niet_afgewezen(tmp_path):
    r = _store(tmp_path)
    a = r.add(role=_ROLE, feed="f", kind="concurrent", content="Veja")
    b = r.add(role=_ROLE, feed="f", kind="concurrent", content="veja")   # zelfde (case-insensitive)
    assert a == b and len(r.pending(_ROLE)) == 1
    # afgewezen signaal blokkeert een nieuw voorstel niet
    r.set_status(a, "afgewezen")
    c = r.add(role=_ROLE, feed="f", kind="concurrent", content="Veja")
    assert c and c != a


def test_add_leeg_of_zonder_rol(tmp_path):
    r = _store(tmp_path)
    assert r.add(role=_ROLE, feed="f", kind="kaart", content="   ") is None
    assert r.add(role="", feed="f", kind="kaart", content="iets") is None


def test_seen_dedup_op_link(tmp_path):
    r = _store(tmp_path)
    assert r.seen("https://x/a") is False
    r.mark_seen("https://x/a")
    assert r.seen("https://x/a") is True
    r.mark_seen("https://x/a")                                    # idempotent


def test_status_flow_en_persistentie(tmp_path):
    r = _store(tmp_path)
    rid = r.add(role=_ROLE, feed="f", kind="doelwit", content="Merk Y")
    assert r.set_status(rid, "goedgekeurd") is True
    assert r.set_status("bestaat-niet", "goedgekeurd") is False
    assert r.set_status(rid, "onzin") is False                   # ongeldige status
    assert [it["id"] for it in r.approved(_ROLE)] == [rid]
    assert r.pending(_ROLE) == []
    # herladen vanaf schijf behoudt de status
    r2 = RadarStore(str(tmp_path / "radar.json"))
    assert [it["id"] for it in r2.approved(_ROLE)] == [rid]


def test_feeds_default_en_override(tmp_path):
    # default: drie feeds, elk op een rol
    assert feeds_for_role("concurrent_scout", str(tmp_path))
    assert feeds_for_role("onbekende_rol", str(tmp_path)) == []
    # data/feeds.json overschrijft de default
    (tmp_path / "feeds.json").write_text(
        json.dumps([{"env": "X_URL", "role": "harry_hemp", "mode": "precisie", "label": "Test"}]),
        encoding="utf-8")
    feeds = load_feeds(str(tmp_path))
    assert len(feeds) == 1 and feeds[0]["role"] == "harry_hemp"
    assert feeds_for_role("concurrent_scout", str(tmp_path)) == []
