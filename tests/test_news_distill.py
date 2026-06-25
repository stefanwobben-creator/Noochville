"""Scout destilleert concurrent-nieuws tot mens-gated voorstellen (kaart/seed/doelwit/concurrent),
en bevestigen routeert naar de juiste store."""
from __future__ import annotations
import json

from nooch_village.news_distill import NewsProposals, distill_article, distill_news
from nooch_village import cockpit


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
    fake = lambda p: "SOORT: seed\nINHOUD: cactusleer\nWAAROM: breed"
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


def test_news_prop_confirm_routeert_naar_juiste_store(tmp_path):
    from nooch_village.news_distill import NewsProposals
    from nooch_village.library import Library
    from nooch_village.notes_store import NotesStore
    from nooch_village.competitor_brands import CompetitorBrands
    d = _data(tmp_path)
    np = NewsProposals(str(d / "news_proposals.json"))
    pid_seed = np.add("seed", "cactusleer", "breed", "Cariuma", "t", "u1")
    pid_doel = np.add("doelwit", "plasticvrije sneaker", "intentie", "Cariuma", "t", "u2")
    pid_kaart = np.add("kaart", "Cactusleer is een veganistisch leeralternatief", "feit", "X", "t", "u3")
    pid_conc = np.add("concurrent", "Allbirds", "groot merk", "X", "t", "u4")

    for pid in (pid_seed, pid_doel, pid_kaart, pid_conc):
        res = cockpit._dispatch_action(str(d), "news_prop", pid, "", extra={"decision": "confirm"})
        assert res["ok"]

    lib = Library(str(d / "library.json"))
    assert lib.is_approved("cactusleer") and lib.function_of("cactusleer") == "volg"
    assert lib.is_approved("plasticvrije sneaker") and lib.function_of("plasticvrije sneaker") == "doelwit"
    assert any("Cactusleer" in n.claim for n in NotesStore(str(d / "notes.json")).all())
    assert "Allbirds" in CompetitorBrands(str(d / "competitor_brands.json")).confirmed()
    # alle voorstellen nu confirmed (niet meer pending)
    assert NewsProposals(str(d / "news_proposals.json")).pending() == []


def test_news_prop_reject(tmp_path):
    from nooch_village.news_distill import NewsProposals
    d = _data(tmp_path)
    np = NewsProposals(str(d / "news_proposals.json"))
    pid = np.add("seed", "iets", "x")
    res = cockpit._dispatch_action(str(d), "news_prop", pid, "", extra={"decision": "reject"})
    assert res["ok"] and res["news"] == "rejected"
    assert NewsProposals(str(d / "news_proposals.json")).pending() == []


def test_cockpit_rendert_distilleer_blok(tmp_path):
    d = _data(tmp_path)
    (d / "news_proposals.json").write_text(json.dumps({"items": {
        "p1": {"id": "p1", "kind": "doelwit", "content": "plasticvrije sneaker", "rationale": "intentie",
               "brand": "Cariuma", "title": "kop", "link": "u1", "status": "pending", "at": 1}},
        "seen": []}), encoding="utf-8")
    snap = cockpit.gather(str(d))
    assert [p["content"] for p in snap["news_proposals"]] == ["plasticvrije sneaker"]
    page = cockpit.render_html(snap, csrf_token="t")
    assert "Scout uit het nieuws" in page and "plasticvrije sneaker" in page
    assert 'value="news_prop"' in page and 'value="news_scan"' in page
