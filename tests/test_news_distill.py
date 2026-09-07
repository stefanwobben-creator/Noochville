"""Scout destilleert concurrent-nieuws tot mens-gated voorstellen (kaart/seed/doelwit/concurrent),
en bevestigen routeert naar de juiste store."""
from __future__ import annotations
import json

from nooch_village.news_distill import NewsProposals, distill_article, distill_news



def test_distill_article_parse_en_failclosed():
    art = {"brand": "Cariuma", "title": "Cariuma lanceert cactusleer-sneaker", "link": "u1"}
    fake = lambda p: "SOORT: doelwit\nINHOUD: cactusleer sneaker\nWAAROM: intentie"
    assert distill_article(art, llm_reason=fake) == {
        "kind": "doelwit", "content": "cactusleer sneaker", "rationale": "intentie"}
    # geen LLM-antwoord → None (fail-closed)
    assert distill_article(art, llm_reason=lambda p: None) is None
    # 'geen' → None
    assert distill_article(art, llm_reason=lambda p: "SOORT: geen\nINHOUD: -") is None
    # al gevolgd merk wordt niet als concurrent voorgesteld
    assert distill_article(art, known_brands=["Veja"],
                           llm_reason=lambda p: "SOORT: concurrent\nINHOUD: Veja\nWAAROM: x") is None
    # lege kop → None
    assert distill_article({"title": ""}, llm_reason=fake) is None


def test_distill_news_dedup_en_seen(tmp_path):
    np = NewsProposals(str(tmp_path / "np.json"))
    news = {"Cariuma": {"title": "Cariuma cactus sneaker", "link": "u1", "date": "2026-06-01"}}
    # distill_news gaat via distill_articles: het antwoord draagt de [[N: i]]-nummering van de batch
    fake = lambda p: "[[N: 1]]\nSOORT: seed\nINHOUD: cactusleer\nWAAROM: breed"
    assert distill_news(news, np, llm_reason=fake) == {"scanned": 1, "proposed": 1}
    # tweede run: link al gezien → niet opnieuw
    assert distill_news(news, np, llm_reason=fake) == {"scanned": 0, "proposed": 0}
    assert [p["content"] for p in np.pending()] == ["cactusleer"]


def _data(tmp_path):
    d = tmp_path / "data"; d.mkdir()
    for f in ("governance_records.json", "library.json", "human_inbox.json"):
        (d / f).write_text("{}", encoding="utf-8")
    (d / "competitor_brands.json").write_text(
        json.dumps({"candidates": {}, "confirmed": [], "rejected": []}), encoding="utf-8")
    return d






