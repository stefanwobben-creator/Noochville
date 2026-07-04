"""Harde UI-regel (CLAUDE.md — 'UI — designsysteem'): governeerde views hergebruiken
design-systeem-klassen en bevatten GEEN inline style-attributen.

Deze guard rendert de artefact-views (policies/notes/tools, inclusief de add- én edit-forms) en
faalt zodra er een `style=`-attribuut in zit. Elke nieuwe governeerde view voeg je hier toe.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import overview

CIRCLE = "mother_earth__nooch"


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
