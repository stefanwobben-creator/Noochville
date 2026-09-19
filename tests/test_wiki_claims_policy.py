"""De beleidspagina "Claims policy", en de twee poorten die er omheen staan.

De pagina zelf is het makkelijke deel. Wat hier echt bewaakt wordt is de grens die Stefan op
20 september 2026 expliciet liet nakijken vóór hij akkoord gaf:

    "Check expliciet dat `_artefact_gate` daarmee niemand anders dan compliance blokkeert om de
     pagina te bewerken — dat zou fase 5's beslissing (wie ingelogd is mag de claims-curatie doen)
     weer terugdraaien."

Het antwoord is: **twee verschillende oppervlakken, en ze raken elkaar niet.**

| wat | poort | wie |
|---|---|---|
| de claims-DATABASE cureren | `_claims_gate` | iedereen-ingelogd (fase 5, ongewijzigd) |
| de beleids-PAGINA bewerken | `_artefact_gate` | rolvervuller van compliance óf Circle Lead |
| de beleids-pagina laten WIJZIGEN | `pagina_voorstel` | iedereen-ingelogd (ongated, geen mutatie) |

Een ingelogde die compliance niet vervult mag dus nog steeds alles met de claims-database, en kan
de pagina niet zelf herschrijven maar wél een voorstel indienen. Dat is geen terugdraaiing van
fase 5; het is de bestaande artefact-regel die op élke rol-pagina staat.
"""
from __future__ import annotations

import tempfile

import pytest

from nooch_village import cockpit2, wiki, wiki_claims_policy as wcp

CIRKEL_LEAD = "mother_earth__nooch__circle_lead"


@pytest.fixture()
def dorp():
    """Wegwerp-dorp MET de beleidspagina gezaaid. Zaaien gebeurt expliciet en niet in de bootstrap
    — inhoud aanmaken is geen infrastructuur (zelfde reden als bij de methode-pagina)."""
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    wcp.zorg_voor_pagina(st.att, st.records, ".", apply=True)
    return st, dd


def _pagina(st):
    return next(a for a in st.att.list(wcp.EIGENAAR, wiki.PAGINA_KIND) if a.title == wcp.TITEL)


# ── de pagina zelf ───────────────────────────────────────────────────────────

def test_pagina_staat_bij_compliance_en_is_een_wiki_pagina(dorp):
    st, _ = dorp
    a = _pagina(st)
    assert a.anchor == wcp.EIGENAAR == "mother_earth__nooch__compliance"
    assert a.kind == wiki.PAGINA_KIND == "note"       # alleen notes zijn wiki-pagina's
    assert a in wiki.paginas(st.att)                  # dus ook echt vindbaar in de wiki


def test_de_vier_voorwaarden_en_de_vier_verboden_staan_er_letterlijk(dorp):
    """De tekst is beleid, geen proza dat de implementatie mag herschrijven."""
    st, _ = dorp
    body = _pagina(st).body
    assert "Anyone may publish a sustainability claim, provided that all four of these hold" in body
    for kop in ("Four conditions", "Never, whatever the evidence (EU-blacklist, Annex I UCPD)",
                "Who decides"):
        assert kop in body
    for voorwaarde in ("On the list.", "Evidence with the claim.", "Scoped.", "Alive."):
        assert voorwaarde in body
    for oordeel in ("Green:", "Orange:", "Red:", "No hard legal basis:"):
        assert oordeel in body
    # De laatste alinea is de reden dat deze pagina géén feiten draagt.
    assert "governs whether a claim may be published, not whether it is true" in body


def test_geen_feiten_op_de_beleidspagina(dorp):
    """Grond-status hoort over een claim te gaan, niet over de regel die claims toetst."""
    st, _ = dorp
    assert wiki.feiten(_pagina(st)) == []


def test_zaaien_is_idempotent_en_overschrijft_niet(dorp):
    """Wat compliance sinds het zaaien aanpast, blijft staan."""
    st, _ = dorp
    a = _pagina(st)
    st.att.update(a.id, body="onze eigen versie", actor_id="mens", actor_type="person")
    rap = wcp.zorg_voor_pagina(st.att, st.records, ".", apply=True)
    assert rap[0]["actie"] == "bestaat al"
    assert _pagina(st).body == "onze eigen versie"


def test_dry_run_schrijft_niets():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rap = wcp.zorg_voor_pagina(st.att, st.records, ".", apply=False)
    assert rap[0]["actie"] == "zou aanmaken"
    assert st.att.list(wcp.EIGENAAR, wiki.PAGINA_KIND) == []


def test_zonder_eigenaar_rol_geen_pagina_ergens_anders():
    """Fail-closed: liever zichtbaar overgeslagen dan stil op de verkeerde rol."""
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rap = wcp.zorg_voor_pagina(st.att, st.records, ".", apply=True,
                               eigenaar="rol_die_niet_bestaat")
    assert rap[0]["actie"] == "overgeslagen" and "bestaat niet" in rap[0]["reden"]
    assert wiki.paginas(st.att) == []


def test_de_tekst_komt_uit_content_en_niet_uit_code():
    """Een zin wijzigen mag geen code-deploy vragen."""
    assert wcp.BRONBESTAND.endswith("claims_policy_en.md")
    with pytest.raises(wcp.TekstOntbreekt):
        wcp.tekst(tempfile.mkdtemp())


# ── de poorten: het antwoord op Stefans check ────────────────────────────────

def _drie_mensen(st):
    """compliance-vervuller, Circle Lead, en iemand die geen van beide is."""
    comp = st.people.add("Compliance Mens", "comp@test.nl")
    lead = st.people.add("Lead Mens", "lead@test.nl")
    derde = st.people.add("Derde Mens", "derde@test.nl")
    st.assign.assign(wcp.EIGENAAR, "person", comp.id)
    st.assign.assign(CIRKEL_LEAD, "person", lead.id)
    return comp, lead, derde


def test_artefact_poort_laat_compliance_en_circle_lead_door(dorp):
    st, _ = dorp
    comp, lead, _derde = _drie_mensen(st)
    assert cockpit2._artefact_gate(wcp.EIGENAAR, comp.email, st) is None
    assert cockpit2._artefact_gate(wcp.EIGENAAR, lead.email, st) is None


def test_artefact_poort_weigert_een_derde_ingelogde(dorp):
    """Dit is de prijs van het anker, en hij staat hier zodat niemand hem later ontdekt."""
    st, _ = dorp
    _comp, _lead, derde = _drie_mensen(st)
    deny = cockpit2._artefact_gate(wcp.EIGENAAR, derde.email, st)
    assert deny is not None and "role filler or Circle Lead" in deny


def test_fase5_is_niet_teruggedraaid_diezelfde_derde_mag_claims_cureren(dorp):
    """De claims-DATABASE staat los van de beleids-PAGINA. Zou deze test ooit omvallen, dan is de
    fase-5-beslissing stilzwijgend ingetrokken."""
    st, _ = dorp
    _comp, _lead, derde = _drie_mensen(st)
    assert cockpit2._claims_gate(st, derde.email) is None
    assert cockpit2._claims_gate_open(st, derde.email) is True


def test_wie_niet_mag_bewerken_mag_wel_voorstellen(dorp):
    """De ontsnapping die de wiki-laag standaard biedt: een voorstel is geen mutatie."""
    st, dd = dorp
    _comp, _lead, derde = _drie_mensen(st)
    a = _pagina(st)
    ontv = wiki.ontvanger(a.anchor, st.records, st.assign)
    assert ontv["rol"] == wcp.EIGENAAR        # compliance heeft een mens-vervuller → blijft daar
    doel = [("role", wcp.EIGENAAR)]
    voor = len(st.notif.for_targets(doel))
    veld = {"aid": a.id, "voorstel": a.body + "\n\nOne more line.",
            "waarom": "the scope rule is unclear"}
    _nxt, msg = cockpit2._act_pagina_voorstel(cockpit2._Ctx(
        st=st, g=lambda k, d="": veld.get(k, d), nxt="/pagina", form=None,
        username=derde.email, action="pagina_voorstel", data_dir=dd))
    assert msg.startswith("✓") and len(st.notif.for_targets(doel)) == voor + 1


# ── de render-afspraak ───────────────────────────────────────────────────────

def test_de_tekst_is_geschreven_voor_de_renderer_die_er_is():
    """`_md` (de wiki-renderer) kent `## `-koppen, `- `-lijsten en `**vet**` — en verder niets.

    Een `# `-kop en een `---`-streep komen er LETTERLIJK doorheen, en een lijstregel die over twee
    bronregels loopt breekt midden in de zin af. Dit is geen theorie: de pagina "How we decide
    here" staat sinds 18 september 2026 live mét een zichtbare `# How we decide here` erboven,
    omdat ik die tekst destijds nooit gerenderd heb bekeken. Deze test zorgt dat het hier niet
    nog eens gebeurt."""
    from nooch_village import wiki_claims_policy as wcp
    from nooch_village.cockpit2_util import _md

    ruw = wcp.tekst(".")
    regels = [r for r in ruw.split("\n") if r.strip()]
    assert not any(r.startswith("# ") for r in regels), "`# ` rendert als platte tekst"
    assert not any(r.strip() == "---" for r in regels), "`---` rendert als drie streepjes"
    # Elke lijstregel staat compleet op één bronregel: de volgende regel begint nooit met kleine
    # letter (dat zou een doorgelopen zin zijn).
    for vorige, huidige in zip(regels, regels[1:]):
        if vorige.startswith("- "):
            assert huidige.startswith(("- ", "## ")) or huidige[0].isupper() or huidige[0] == "*", \
                f"doorgelopen lijstregel: {huidige!r}"

    html = _md(ruw)
    assert html.count("<h4>") == 3            # de drie koppen uit het beleid
    assert html.count("<li>") == 12           # 4 voorwaarden + 4 verboden + 4 oordelen
    assert "<strong>On the list.</strong>" in html
