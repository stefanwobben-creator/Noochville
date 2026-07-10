"""Harde UI-regel (CLAUDE.md — 'UI — designsysteem'): governeerde views hergebruiken
design-systeem-klassen en bevatten GEEN inline style-attributen.

Twee lagen:
1. Render-guard (artefact-views): rendert policies/notes/tools en faalt op elk `style=`-attribuut
   in de OUTPUT. Precies, maar per view apart op te tuigen.
2. Ratchet-guard (project-breed): telt `style=` in de BRON van élke governeerde view en houdt die
   telling op een per-bestand plafond. Nieuwe inline styles laten de telling stijgen → faal.
   Bestaande schuld is gewhitelist op het huidige aantal; ruim je een view op, verlaag het plafond.
   Doel: monotone daling naar nul, nooit stijging. Zie docs/UX_PATTERNS.md voor de kern-klassen.
"""
from __future__ import annotations

import glob
import os

from nooch_village import cockpit2
from nooch_village.views import overview

CIRCLE = "mother_earth__nooch"

# Per-bestand plafond voor bestaande inline style=-schuld (audit dd 2026-07-05, totaal 137).
# Niet-vermelde governeerde views moeten 0 zijn (schoon). Verlaag een getal zodra je opruimt.
_STYLE_WHITELIST = {
    "views/overview.py": 34,
    "views/projects.py": 19,
    "views/strategy.py": 14,
    "views/werkoverleg.py": 13,
    "views/metrics.py": 8,
    "views/roloverleg.py": 7,
    "views/checklists.py": 5,
    "views/backlog.py": 7,
    "cockpit2.py": 7,
    "views/noochie.py": 5,
    "views/feed.py": 4,
    "views/catalog.py": 2,
}

_PKG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village")


def _governed_files():
    files = sorted(glob.glob(os.path.join(_PKG, "views", "*.py")))
    files.append(os.path.join(_PKG, "cockpit2.py"))
    return files


def test_geen_nieuwe_inline_styles_in_governeerde_views():
    """Ratchet: elke governeerde view mag exact zijn gewhiteliste aantal inline styles hebben.
    Meer → nieuwe schuld (faal). Minder → je hebt opgeruimd, verlaag het plafond (faal met uitleg)."""
    for full in _governed_files():
        rel = os.path.relpath(full, _PKG).replace(os.sep, "/")
        count = open(full, encoding="utf-8").read().count("style=")
        ceiling = _STYLE_WHITELIST.get(rel, 0)
        assert count <= ceiling, (
            f"{rel}: {count} inline style=-attributen, plafond {ceiling}. Nieuwe inline style? "
            f"Gebruik een design-systeem-klasse (docs/UX_PATTERNS.md → Kern-klassen). Bewuste "
            f"uitzondering? Verhoog het plafond in _STYLE_WHITELIST mét reden.")
        assert count >= ceiling, (
            f"{rel}: {count} inline style=-attributen, plafond {ceiling}. Je hebt schuld opgeruimd — "
            f"verlaag het plafond naar {count} (of verwijder de regel bij 0) zodat de ratchet vastzet.")


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_artefact_views_bevatten_geen_inline_style(tmp_path):
    st = _st(tmp_path)
    rec = st.records.get(CIRCLE)
    rec.definition.domains += ["Money", "Decision Making"]   # 2 domeinen → select in de add-form
    st.records.put(rec)
    st.att.add(CIRCLE, "policy", title="P", domain="Money", body="een regel")
    st.att.add(CIRCLE, "note", title="N", body="een notitie")
    st.att.add(CIRCLE, "tool", title="T", url="https://voorbeeld.nl")
    st.att.update(st.att.list(CIRCLE, "policy")[0].id, body="v2")   # extra versie → historie-uitklapper

    # guest → can_edit True, dus ook de add-/edit-/archive-forms komen mee in de render
    for kind, tab in (("policy", "Policies"), ("note", "Notes"), ("tool", "Tools")):
        html = overview._artefact_tab_html(st, rec, kind, "tok", "guest", titel=tab, leeg="leeg")
        assert "style=" not in html, (
            f"inline style-attribuut in de artefact-{kind}-view — gebruik een bestaande "
            f"design-systeem-klasse i.p.v. inline style")


def test_artefact_views_gebruiken_designsysteem_klassen(tmp_path):
    # Positieve tegenhanger: de views hergebruiken wél de bestaande klassen.
    st = _st(tmp_path)
    rec = st.records.get(CIRCLE)
    rec.definition.domains.append("Money"); st.records.put(rec)
    st.att.add(CIRCLE, "policy", title="P", domain="Money", body="b")
    html = overview._artefact_tab_html(st, rec, "policy", "tok", "guest", titel="Policies", leeg="leeg")
    for klass in ("class='card'", "class='qadd-form'", "class='editor'", "att-lbl", "class='ptitle'"):
        assert klass in html, f"design-systeem-klasse ontbreekt: {klass}"
