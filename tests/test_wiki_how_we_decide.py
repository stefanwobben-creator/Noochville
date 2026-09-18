"""De methode-pagina en de besluiten die eronder hangen.

Twee dingen worden hier bewaakt, en ze zijn allebei een belofte uit de scope:

1. De besluiten-sectie is AFGELEID BIJ HET LEZEN. De pagina bewaart geen kopie van een besluit;
   komt er een rij bij of valt er een weg, dan klopt de sectie de volgende pageload vanzelf. Een
   opgeslagen kopie zou uiteenlopen zonder dat iets zich meldt — dezelfde regel als bij `feiten`
   en `backlinks`.
2. "Predictions due" staat wel in het prototype maar hoort bij fase 2, en is hier niet gebouwd —
   ook niet als lege huls, want een leeg blok belooft iets wat er niet is.
"""
from __future__ import annotations

import tempfile

import pytest

from nooch_village import cockpit2, decision_sheets as ds, wiki_how_we_decide as hwd
from nooch_village.views.wiki import render_pagina

BLOK = """=== DECISION SHEET ===
Decision: Add a second factory this year, or stay with one
Chosen option: Stay with one for now
Assumption 1: the current line holds its defect rate
Assumption 2: a second line costs three months of attention
Prediction (number and date): 40 pairs by 1 March
Stop signal: two late batches in a row
Still unknown, and whether that is acceptable: tooling cost — acceptable
Coach version: 1
=== END DECISION SHEET ==="""


@pytest.fixture()
def dorp():
    """Een wegwerp-dorp MET de pagina gezaaid.

    Het zaaien gebeurt hier expliciet en niet in de bootstrap: inhoud aanmaken is geen
    infrastructuur. Een cockpit-start die een pagina schrijft doet dat namelijk ook in elk
    test-dorp, en dan telt elke test die notities telt er ineens één te veel — negen tests
    braken daarop voordat dit verplaatst werd naar `village wiki_zaad`."""
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    hwd.zorg_voor_pagina(st.att, st.records, ".", apply=True)
    return st, dd


def _pagina(st):
    return next(a for a in st.att.list(hwd.EIGENAAR, "note") if a.title == hwd.TITEL)


# ── de pagina zelf ───────────────────────────────────────────────────────────

def test_pagina_staat_bij_strategic_lead_en_draagt_de_negen_regels(dorp):
    st, _ = dorp
    a = _pagina(st)
    assert a.anchor == hwd.EIGENAAR
    for nr in range(9):
        assert f"{nr}. **" in a.body                       # 0 t/m 8, de methode zelf
    assert "/decision-coach" in a.body                     # de link onder de negen regels
    assert "never reaches NoochVille" in a.body            # de derde uitleg-zin


def test_zaaien_is_idempotent_en_overschrijft_niet(dorp):
    """Wat de eigenaar sinds het zaaien aanpast, blijft staan."""
    st, _ = dorp
    a = _pagina(st)
    st.att.update(a.id, body="mijn eigen versie", actor_id="mens", actor_type="person")
    rap = hwd.zorg_voor_pagina(st.att, st.records, ".", apply=True)
    assert rap[0]["actie"] == "bestaat al"
    assert st.att.get(a.id).body == "mijn eigen versie"


def test_zonder_bronbestand_geen_pagina(tmp_path):
    """De methode wordt niet verzonnen als de tekst er niet is."""
    with pytest.raises(hwd.TekstOntbreekt):
        hwd.pagina(str(tmp_path))


def test_gearchiveerde_eigenaar_krijgt_geen_pagina(dorp):
    """Fail-closed uit wiki_seed: stil op de verkeerde plek is erger dan zichtbaar overgeslagen."""
    st, _ = dorp
    rap = hwd.zorg_voor_pagina(st.att, st.records, ".", apply=True, eigenaar="bestaat_niet")
    assert rap[0]["actie"] == "overgeslagen" and "bestaat niet" in rap[0]["reden"]


# ── de besluiten-sectie ──────────────────────────────────────────────────────

def test_besluiten_worden_bij_het_lezen_afgeleid(dorp):
    """Niet opgeslagen: de pagina verandert niet, de weergave wel."""
    st, dd = dorp
    a = _pagina(st)
    voor = render_pagina(st, a.id)
    assert "Add a second factory" not in voor
    body_voor = st.att.get(a.id).body

    ds.log_sheet(dd, ds.parse(BLOK), decider="Stefan Wobben", role="Strategic Lead", raw=BLOK)

    na = render_pagina(st, a.id)
    assert "Add a second factory" in na and "40 pairs by 1 March" in na
    assert st.att.get(a.id).body == body_voor            # de pagina zelf is niet aangeraakt


def test_een_pagina_zonder_coachverwijzing_krijgt_geen_sectie(dorp):
    """De pagina bepaalt het zelf via zijn inhoud — geen titel-match, geen rol-id in de code."""
    st, dd = dorp
    ds.log_sheet(dd, ds.parse(BLOK), decider="Stefan Wobben", role="", raw=BLOK)
    ander = st.att.add(hwd.EIGENAAR, "note", title="Iets anders", body="gewone notitie",
                       actor_id="system", actor_type="persona")
    assert "Decisions logged" not in render_pagina(st, ander.id)


def test_persoonfilter_werkt_op_de_pagina(dorp):
    st, dd = dorp
    a = _pagina(st)
    ds.log_sheet(dd, ds.parse(BLOK), decider="Stefan Wobben", role="", raw=BLOK)
    ds.log_sheet(dd, ds.parse(BLOK.replace("Add a second factory this year, or stay with one",
                                           "Iets van Lotte")),
                 decider="Lotte Mulder", role="", raw=BLOK)
    alles = render_pagina(st, a.id)
    assert "Add a second factory" in alles and "Iets van Lotte" in alles
    alleen_lotte = render_pagina(st, a.id, persoon="Lotte Mulder")
    assert "Iets van Lotte" in alleen_lotte and "Add a second factory" not in alleen_lotte
    assert f"persoon=Lotte" in alles                      # de chip staat er


def test_id_is_kopieerbaar_op_de_pagina(dorp):
    """De Copy id-knop moet ook echt iets doen: de kopieer-JS gaat mee met de sectie."""
    st, dd = dorp
    a = _pagina(st)
    rij = ds.log_sheet(dd, ds.parse(BLOK), decider="Stefan Wobben", role="", raw=BLOK)
    html = render_pagina(st, a.id)
    assert f"data-dc-id='{rij['id']}'" in html
    assert "navigator.clipboard" in html


def test_predictions_due_is_niet_gebouwd(dorp):
    """Fase 2. Een lege huls belooft iets wat er niet is."""
    st, dd = dorp
    a = _pagina(st)
    ds.log_sheet(dd, ds.parse(BLOK), decider="Stefan Wobben", role="", raw=BLOK)
    html = render_pagina(st, a.id)
    assert "Predictions due" not in html
    assert "It held" not in html and "It did not hold" not in html


def test_geen_inline_styles_op_de_pagina(dorp):
    st, dd = dorp
    a = _pagina(st)
    ds.log_sheet(dd, ds.parse(BLOK), decider="Stefan Wobben", role="", raw=BLOK)
    assert "style=" not in render_pagina(st, a.id)


def test_de_bootstrap_zaait_geen_inhoud(tmp_path):
    """Inhoud aanmaken is geen infrastructuur.

    De zaaier zat eerst in de cockpit-start. Dat betekende een pagina in élk test-dorp, en negen
    bestaande tests die notities tellen braken erop. Zaaien hoort bij `village wiki_zaad`: een
    bewuste handeling, met dry-run, één keer per omgeving."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    assert [a for a in st.att.by_kind("note") if a.title == hwd.TITEL] == []


def test_zaaien_is_dry_run_tenzij_apply(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rap = hwd.zorg_voor_pagina(st.att, st.records, ".", apply=False)
    assert rap[0]["actie"] == "zou aanmaken"
    assert [a for a in st.att.by_kind("note") if a.title == hwd.TITEL] == []
