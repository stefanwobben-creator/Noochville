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




