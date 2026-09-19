"""inoreader_ingest (fase 2a): veiligheidsfilter + strenge distill → RadarStore van de rol, idempotent."""
from __future__ import annotations

from nooch_village import inoreader_ingest as ing
from nooch_village.radar_store import RadarStore

_ROLE = "concurrent_scout"
_FEED = "Competitor Watch"


def _batch(prompt, blok):
    """Stub-antwoord in het BATCH-formaat dat distill_articles verwacht: één [[N: i]]-blok per kop.
    news_distill destilleert sinds 546657f meerdere koppen in één call (tegen de dag-cap), dus een
    los SOORT/INHOUD-antwoord zonder nummering wordt — terecht — door de parser genegeerd."""
    n = prompt.count("[[N:")
    return "\n".join(f"[[N: {i}]]\n{blok}" for i in range(1, n + 1))


def _reason_veja(prompt):
    # stub-LLM: doet alsof elk aangeboden artikel een concurrent-signaal is
    return _batch(prompt, "SOORT: concurrent\nINHOUD: Veja\nWAAROM: nieuwe duurzame sneaker")


def _radar(tmp_path):
    return RadarStore(str(tmp_path / "radar.json"))




def test_idempotent_op_link(tmp_path):
    items = [{"title": "Veja nieuws", "url": "https://example.com/a", "content_html": "x"}]
    r1 = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path), llm_reason=_reason_veja)
    r2 = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path), llm_reason=_reason_veja)
    assert r1["proposed"] == 1 and r2["proposed"] == 0 and r2["seen"] == 1
    assert len(_radar(tmp_path).pending(_ROLE)) == 1                # geen dubbel signaal


def test_eigen_merk_label(tmp_path):
    def reason_kaart(prompt):
        return _batch(prompt, "SOORT: kaart\nINHOUD: Nooch krijgt lovende review\nWAAROM: reputatie")
    items = [{"title": "Nooch.earth review", "url": "https://blog.example/nooch", "content_html": "Nooch is great"}]
    res = ing.ingest_feed_items(items, role=_ROLE, feed=_FEED, data_dir=str(tmp_path), llm_reason=reason_kaart)
    assert res["own_brand"] == 1
    p = _radar(tmp_path).pending(_ROLE)[0]
    assert p["rationale"].startswith("[eigen merk]")


def test_blocked_domain_helper():
    assert ing._blocked("https://femdomss.com/video/x") is True
    assert ing._blocked("https://www.veja-store.com/nieuws") is False






