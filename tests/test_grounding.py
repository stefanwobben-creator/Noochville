"""De Kroniek fase 1 — grondings-poort op de field note. Vangt de '22 mei 2024 / 12 bezoekers'-drift;
markeert i.p.v. schoon publiceren; logt de uitkomst in de Kroniek. Geen false positive op per-pagina-
aantallen (die staan als waarde in de bron)."""
from __future__ import annotations

from nooch_village.grounding import ground_field_note

# 107 = totaal, 96 = per-pagina (beide gegrond); 172 pageviews
PLAUS = {"results": {"visitors": {"value": 107}, "pageviews": {"value": 172}},
         "pages": [{"name": "home", "visitors": 96}, {"name": "blog", "visitors": 3}]}


def test_gegronde_body_geen_issues():
    body = "# Field Note 2026-07-12\n\nBezoekers (7d): 107. Homepage: 96 bezoekers, blog 3 bezoekers."
    assert ground_field_note(body, PLAUS, "2026-07-12") == []


def test_datum_drift_gemarkeerd():
    body = "# Field Note 2026-07-12\n\n**Field Note – 22 mei 2024**. 107 bezoekers."
    issues = ground_field_note(body, PLAUS, "2026-07-12")
    assert any("datum-drift" in i and "2024" in i for i in issues)


def test_ongegrond_bezoekersgetal_gemarkeerd():
    body = "# Field Note 2026-07-12\n\n12 bezoekers deze week."     # 12 komt nergens in de data voor
    issues = ground_field_note(body, PLAUS, "2026-07-12")
    assert any("ongegrond getal" in i and "12" in i for i in issues)


def test_per_pagina_getal_is_gegrond():
    body = "Homepage domineert met 96 bezoekers."                  # 96 = per-pagina-waarde → geen issue
    assert ground_field_note(body, PLAUS, "2026-07-12") == []


def test_field_note_skill_markeert_en_logt(tmp_path, monkeypatch):
    """End-to-end: een gehallucineerde LLM-body → ONGEGROND-banner in het bestand + fout in de Kroniek."""
    import nooch_village.skills_impl.field_note as fn
    from nooch_village.evidence_ledger import EvidenceLedger

    # forceer de LLM-tak met een gehallucineerde body (verkeerde datum + verzonnen bezoekersgetal)
    monkeypatch.setattr(fn, "reason", lambda *a, **k: "**Field Note – 22 mei 2024**\n\n12 bezoekers deze week.")
    ctx = type("Ctx", (), {"data_dir": str(tmp_path)})()
    out = fn.FieldNoteSkill().run({"plausible": {"results": {"visitors": {"value": 107}}}, "trends": {}}, ctx)

    assert out["grounded"] is False and out["issues"]
    body = open(out["path"], encoding="utf-8").read()
    assert "ONGEGROND" in body                                     # gemarkeerd, niet schoon gepubliceerd
    recs = EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl")).all_records()
    assert recs and recs[-1]["skill"] == "field_note" and recs[-1]["status"] == "fout"


def test_field_note_skill_gegrond_geen_banner(tmp_path, monkeypatch):
    import nooch_village.skills_impl.field_note as fn
    from nooch_village.evidence_ledger import EvidenceLedger
    monkeypatch.setattr(fn, "reason", lambda *a, **k: "Rustige week. Bezoekers (7d): 107.")
    ctx = type("Ctx", (), {"data_dir": str(tmp_path)})()
    out = fn.FieldNoteSkill().run({"plausible": {"results": {"visitors": {"value": 107}}}, "trends": {}}, ctx)
    assert out["grounded"] is True and out["issues"] == []
    assert "ONGEGROND" not in open(out["path"], encoding="utf-8").read()
    assert EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl")).all_records()[-1]["status"] == "bevestigd"
