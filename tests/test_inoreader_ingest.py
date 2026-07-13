"""inoreader_ingest (pilot): veiligheidsfilter + distill → news_proposals, idempotent."""
from __future__ import annotations

from nooch_village import inoreader_ingest as ing
from nooch_village.news_distill import NewsProposals


def _reason_veja(prompt):
    # stub-LLM: doet alsof elk aangeboden artikel een concurrent-signaal is
    return "SOORT: concurrent\nINHOUD: Veja\nWAAROM: nieuwe duurzame sneaker"


def test_blocklist_en_distill(tmp_path):
    items = [
        {"title": "These feet beckon you!", "url": "https://rawporn.org/threads/x", "content_html": "<p>...</p>"},
        {"title": "Veja launches new sneaker", "url": "https://example.com/veja", "content_html": "<p>Veja...</p>"},
        {"title": "", "url": "https://x.com/leeg"},                 # geen titel -> overgeslagen
    ]
    res = ing.ingest_items(items, str(tmp_path), llm_reason=_reason_veja)
    assert res["blocked"] == 1                                      # porno-domein eruit
    assert res["proposed"] == 1                                     # veja-voorstel
    props = NewsProposals(str(tmp_path / "inoreader_proposals.json"))
    pend = props.pending()
    assert len(pend) == 1 and pend[0]["kind"] == "concurrent" and pend[0]["content"] == "Veja"


def test_idempotent_op_link(tmp_path):
    items = [{"title": "Veja nieuws", "url": "https://example.com/a", "content_html": "x"}]
    r1 = ing.ingest_items(items, str(tmp_path), llm_reason=_reason_veja)
    r2 = ing.ingest_items(items, str(tmp_path), llm_reason=_reason_veja)     # zelfde link nogmaals
    assert r1["proposed"] == 1 and r2["proposed"] == 0 and r2["seen"] == 1


def test_eigen_merk_label(tmp_path):
    def reason_kaart(prompt):
        return "SOORT: kaart\nINHOUD: Nooch krijgt lovende review\nWAAROM: reputatie"
    items = [{"title": "Nooch.earth review", "url": "https://blog.example/nooch", "content_html": "Nooch is great"}]
    res = ing.ingest_items(items, str(tmp_path), llm_reason=reason_kaart)
    assert res["own_brand"] == 1
    p = NewsProposals(str(tmp_path / "inoreader_proposals.json")).pending()[0]
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
