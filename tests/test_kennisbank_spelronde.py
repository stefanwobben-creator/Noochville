"""Spelronde dd 2026-07-19 (founder): de suggestiekaart bovenaan de inzichten-kolom
(vóórgevuld, lichtgeel, 'not verified', verify → spel, bladeren) en de Oracle-zoekkolom
op de spel-pagina (live fragment, in-het-spel-kaarten groen/rood gemarkeerd, zoekterm
blijft staan na een koppel, ➕ Bron toevoegen ter plekke). Plus de ZACHTE vijf: boven de
vijf kaarten een vriendelijke hint over onafhankelijke stemmen — nooit een blokkade.
Alles zonder netwerk (gather draait hier met reason_fn=None → fail-closed 'support')."""
from __future__ import annotations

import types

from nooch_village.insight import Insight
from nooch_village.kennisbank import KennisbankStore, load_atoms
from nooch_village.kennisbank_spel import SpelStore, spel_suggesties
from nooch_village.kennisbank_staging import StagingStore
from nooch_village.notes_store import NotesStore


def _st(dd):
    return types.SimpleNamespace(
        dd=dd, kennisbank=KennisbankStore(f"{dd}/kennisbank.json"),
        spel=SpelStore(f"{dd}/kennisbank_spel.json"),
        staging=StagingStore(f"{dd}/kennisbank_staging.json"))


def _seed(dd):
    """Drie prijs-kaarten (één cluster in de 'prijs'-hub) + één losse outsole-kaart."""
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="p1", claim="51% wil de prijs naar 150 euro brengen",
                   source="Survey A", provenance="survey", tags=["prijs"]))
    ns.add(Insight(id="p2", claim="Van Westendorp zet de optimale prijs op 120 euro",
                   source="Survey B", provenance="survey", tags=["prijs"]))
    ns.add(Insight(id="p3", claim="De prijs van 120 euro schrikt twijfelaars niet af",
                   source="Interview C", provenance="interview", tags=["prijs"]))
    ns.add(Insight(id="w1", claim="natuurrubber zool breekt traag af",
                   source="WUR-rapport", provenance="peer_reviewed", tags=["outsole"]))
    return ns


# ── de suggestie-motor (deterministisch, geen LLM) ───────────────────────────

def test_spel_suggesties_deterministisch_en_representatief(tmp_path):
    dd = str(tmp_path); _seed(dd); st = _st(dd)
    atoms = load_atoms(dd)
    a = spel_suggesties(atoms, st.kennisbank.all())
    b = spel_suggesties(atoms, st.kennisbank.all())
    assert a == b                                     # zelfde input → zelfde voorzet
    assert a and a[0]["hub"] == "prijs" and set(a[0]["atom_ids"]) == {"p1", "p2", "p3"}
    # de startformulering is een ECHTE kaart-claim uit het cluster (geen thema-string)
    assert a[0]["hunch"] in {atoms[i]["claim"] for i in ("p1", "p2", "p3")}
    # kaarten die al in een inzicht zitten doen niet meer mee (ongebonden-regel)
    iid = st.kennisbank.add("prijsinzicht")
    for aid in ("p1", "p2", "p3"):
        st.kennisbank.link(iid, aid, "support")
    assert spel_suggesties(load_atoms(dd), st.kennisbank.all()) == []


# ── de suggestiekaart op /kennisbank ─────────────────────────────────────────

def test_suggestiekaart_bovenaan_met_verify_en_bladeren(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path); ns = _seed(dd); st = _st(dd)
    html = render_kennisbank(st, csrf_token="t")
    # lichtgeel + expliciet not-verified + verify start het spel met de cluster-hand
    assert "kn-sugg" in html and "not verified" in html
    assert "kb_spel_start" in html and "Verify" in html
    for aid in ("p1", "p2", "p3"):
        assert f"name='kaart' value='{aid}'" in html
    # de kaart neemt de bovenste plek van de inzichten-kolom (vóór de Insights-kop)
    assert html.index("kn-sugg") < html.index("<h2>Insights</h2>")
    # tweede cluster erbij → bladeren met kandidaat-teller; ?sug= kiest de volgende
    ns.add(Insight(id="w2", claim="rubber zool slijt traag op asfalt",
                   source="Lab D", provenance="peer_reviewed", tags=["outsole"]))
    met_nav = render_kennisbank(st, csrf_token="t")
    assert "kandidaat 1 van 2" in met_nav and "?sug=1" in met_nav
    tweede = render_kennisbank(st, csrf_token="t", sug=1)
    assert "kandidaat 2 van 2" in tweede
    # met een open inzicht-detail wijkt de suggestiekaart (het detail is de bovenste plek)
    iid = st.kennisbank.add("een inzicht")
    assert "kn-sugg" not in render_kennisbank(st, kid=iid, csrf_token="t")
    # read-only (geen csrf): geen suggestiekaart — verify zou toch niet kunnen posten
    assert "kn-sugg" not in render_kennisbank(st, csrf_token="")


# ── de spel-pagina: zoekkolom rechts + markering + zachte vijf ───────────────

def test_spel_zoekkolom_markeert_in_het_spel_groen_rood(tmp_path):
    from nooch_village.views.kennisbank_spel import (render_kennisbank_spel,
                                                     render_kennisbank_spel_search)
    dd = str(tmp_path); _seed(dd); st = _st(dd)
    sid = st.spel.start("prijs rond 120 werkt", [
        {"atom_id": "p1", "stance": "support"},
        {"atom_id": "p2", "stance": "counter"}], by="t")
    frag = render_kennisbank_spel_search(st, sid, zoek="prijs euro", csrf_token="t")
    # in het spel → subtiel groen (steunt) / rood (spreekt tegen), met ↔-flip
    assert "kn-inhand-sup" in frag and "kn-inhand-cou" in frag and "kb_spel_flip" in frag
    # nog niet in het spel → koppel-formulier, en de zoekterm reist mee in next
    assert "kb_spel_add" in frag and "atom_id' value='p3'" in frag
    assert "zoek=prijs%20euro" in frag
    # de volledige pagina draagt de live-zoekbalk + het fragment-anker + bron-ingang
    pagina = render_kennisbank_spel(st, sid, csrf_token="t")
    assert "kn-spelsearch" in pagina and "kn-spelresults" in pagina
    assert "/kennisbank/spel/search" in pagina
    assert "kb_bron_add" in pagina and "➕ Bron toevoegen" in pagina
    # leeg zoekveld: uitnodiging, geen resultaten; onbekend spel: nette melding
    assert "Typ hierboven" in render_kennisbank_spel_search(st, sid, "", csrf_token="t")
    assert "niet gevonden" in render_kennisbank_spel_search(st, "spel_x", "q", csrf_token="t")


def test_zachte_vijf_hint_zonder_blokkade(tmp_path):
    from nooch_village.views.kennisbank_spel import render_kennisbank_spel
    dd = str(tmp_path); ns = _seed(dd); st = _st(dd)
    for i in range(4):
        ns.add(Insight(id=f"x{i}", claim=f"extra prijs-observatie nummer {i}",
                       source=f"Bron {i}", provenance="media", tags=["prijs"]))
    vijf = [{"atom_id": a, "stance": "support"} for a in ("p1", "p2", "p3", "x0", "x1")]
    sid = st.spel.start("prijs werkt", vijf, by="t")
    assert "sterkste vijf" not in render_kennisbank_spel(st, sid, csrf_token="t")
    # de zesde kaart: hint verschijnt, maar koppelen blijft gewoon werken (geen blokkade)
    assert st.spel.add_kaart(sid, "x2", "counter") is True
    zes = render_kennisbank_spel(st, sid, csrf_token="t")
    assert "sterkste vijf" in zes and "Tegenbewijs mag er altijd bij" in zes
    assert st.spel.add_kaart(sid, "x3", "support") is True    # en de zevende ook


# ── kleine fixes dd 2026-07-19 (avond): DOI klikbaar, signals echt regular ──

def test_bron_doi_wordt_link_en_summary_regular(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path); st = _st(dd)
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="d1", claim="plastic wordt chemicalie met zeewater",
                   source="Nature (artikel)", provenance="peer_reviewed",
                   reference="DOI:10.1038/s41586-023-06688-2", tags=["materiaal"]))
    frag = render_kennisbank_search(st, "zeewater", "", "", csrf_token="t")
    # de DOI resolvet naar doi.org, opent in een nieuw tabblad, en toont bron + DOI
    assert "https://doi.org/10.1038/s41586-023-06688-2" in frag
    assert "target='_blank'" in frag and "rel='noopener'" in frag
    assert "Nature (artikel)" in frag
    # het gewicht van de statement-tekst leeft op ÉÉN plek (de summary-regel) en is
    # regular — de specifiekere selector mag de kn-stmttekst-fallback nooit overstemmen
    import os
    css = open(os.path.join(os.path.dirname(__file__), "..", "nooch_village",
                            "static", "nooch.css"), encoding="utf-8").read()
    regel = next(r for r in css.splitlines() if r.startswith(".kn-stmtbody>summary{"))
    assert "font-weight:400" in regel
