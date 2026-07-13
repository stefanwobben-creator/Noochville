"""inoreader_ingest (fase 2a): veiligheidsfilter + strenge distill → RadarStore van de rol, idempotent."""
from __future__ import annotations

from nooch_village import inoreader_ingest as ing
from nooch_village.radar_store import RadarStore

_ROLE = "concurrent_scout"
_FEED = "Competitor Watch"


def _reason_veja(prompt):
    # stub-LLM: doet alsof elk aangeboden artikel een concurrent-signaal is
    return "SOORT: concurrent\nINHOUD: Veja\nWAAROM: nieuwe duurzame sneaker"


def _radar(tmp_path):
    return RadarStore(str(tmp_path / "radar.json"))


def test_blocklist_en_distill(tmp_path):
    items = [
        {"title": "These feet beckon you!", "url": "https://rawporn.org/threads/x", "content_html": "<p>...</p>"},
        {"title": "Veja launches new sneaker", "url": "https://example.com/veja", "content_html": "<p>Veja...</p>",
         "date_published": "2019-06-01T08:00:00Z"},
        {"title": "", "url": "https://x.com/leeg"},                 # geen titel -> overgeslagen
    ]
    res = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path),
                                llm_reason=_reason_veja)
    assert res["blocked"] == 1                                      # porno-domein eruit
    assert len(res["trace"]) == 3 and any(v == "geblokkeerd" for _, v in res["trace"])
    assert res["proposed"] == 1                                     # veja-voorstel
    pend = _radar(tmp_path).pending(_ROLE)
    assert len(pend) == 1 and pend[0]["kind"] == "concurrent" and pend[0]["content"] == "Veja"
    assert pend[0]["feed"] == _FEED and pend[0]["status"] == "wacht"
    assert pend[0]["published_at"] == "2019-06-01T08:00:00Z"        # publicatiedatum uit de feed bewaard


def test_idempotent_op_link(tmp_path):
    items = [{"title": "Veja nieuws", "url": "https://example.com/a", "content_html": "x"}]
    r1 = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path), llm_reason=_reason_veja)
    r2 = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path), llm_reason=_reason_veja)
    assert r1["proposed"] == 1 and r2["proposed"] == 0 and r2["seen"] == 1
    assert len(_radar(tmp_path).pending(_ROLE)) == 1                # geen dubbel signaal


def test_eigen_merk_label(tmp_path):
    def reason_kaart(prompt):
        return "SOORT: kaart\nINHOUD: Nooch krijgt lovende review\nWAAROM: reputatie"
    items = [{"title": "Nooch.earth review", "url": "https://blog.example/nooch", "content_html": "Nooch is great"}]
    res = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path), llm_reason=reason_kaart)
    assert res["own_brand"] == 1
    p = _radar(tmp_path).pending(_ROLE)[0]
    assert p["rationale"].startswith("[eigen merk]")


def test_blocked_domain_helper():
    assert ing._blocked("https://femdomss.com/video/x") is True
    assert ing._blocked("https://www.veja-store.com/nieuws") is False


def test_strict_distill_param(tmp_path):
    from nooch_village.news_distill import distill_article
    assert distill_article({"title": "iets vaags", "brand": "x"},
                           llm_reason=lambda p: "SOORT: geen", strict=True) is None
    d = distill_article({"title": "Merk X lanceert vegan schoen", "brand": "x"},
                        llm_reason=lambda p: "SOORT: concurrent\nINHOUD: Merk X\nWAAROM: lancering",
                        strict=True)
    assert d and d["kind"] == "concurrent"
