"""Kennisbank-statements (herontwerp dd 2026-07-18, SPEC_prototype.html):
kaal overzicht · klik = uitklap-detail (datum · bron op één plek · versie · gekoppeld ·
tags) · '✏️ bewerk' opent de textarea pas op verzoek · ⠿-drag&drop-merge met modal
(kb_atoom_merge: target_id + source_id + tekst)."""
from __future__ import annotations

import types

import pytest

from nooch_village.insight import Insight
from nooch_village.kennisbank import KennisbankStore, load_atoms
from nooch_village.notes_store import NotesStore


def _st(dd):
    from nooch_village.kennisbank_spel import SpelStore
    from nooch_village.kennisbank_staging import StagingStore
    return types.SimpleNamespace(
        dd=dd, kennisbank=KennisbankStore(f"{dd}/kennisbank.json"),
        spel=SpelStore(f"{dd}/kennisbank_spel.json"),
        staging=StagingStore(f"{dd}/kennisbank_staging.json"),
        notes=NotesStore(f"{dd}/notes.json"))


def _seed(dd):
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="a1", claim="Een paar vegan sneakers bevat driekwart liter olie.",
                   source="recurate", reference="https://voorbeeld.nl/olie",
                   source_date="2019-03", provenance="media",
                   tags=["materialen"], links_to=["a2"]))
    ns.add(Insight(id="a2", claim="Vegan betekent niet plasticvrij.",
                   source="recurate", provenance="media",
                   tags=["materialen", "definitie"], contradicts=["a3"]))
    ns.add(Insight(id="a3", claim="Consument-frame kalft af in het boekcorpus.",
                   source="Harry Hemp ngram", provenance="internal_data",
                   tags=["framing"]))
    return ns


# ── kb_atoom_merge: de store-laag ────────────────────────────────────────────

def test_merge_into_tekstkeuze_versie_en_union(tmp_path):
    dd = str(tmp_path)
    ns = _seed(dd)
    kaart = ns.merge_into("a2", "a1", "Vegan is niet plasticvrij; er zit olie in.")
    assert kaart is not None and kaart.id == "a2"
    # tekstkeuze + versie += 1, vorige claim append-only bewaard
    assert kaart.claim == "Vegan is niet plasticvrij; er zit olie in."
    assert kaart.version == 2
    assert kaart.edit_history[-1]["claim"] == "Vegan betekent niet plasticvrij."
    # tags = union (volgorde-stabiel, ontdubbeld)
    assert kaart.tags == ["materialen", "definitie"]
    # links = union zonder self-references (a1→a2 en a1's links_to=[a2] vervallen als self)
    assert "a2" not in kaart.links_to and "a1" not in kaart.links_to
    assert kaart.contradicts == ["a3"]
    # herkomst stapelt: target had geen reference → die van source overgenomen,
    # en het spoor is aantoonbaar via merged_from + het gearchiveerde source-atoom
    assert kaart.reference == "https://voorbeeld.nl/olie"
    assert kaart.merged_from == ["a1"]
    alles = load_atoms(dd, include_archived=True)
    assert alles["a1"]["archived"] is True
    assert alles["a1"]["superseded_by"] == ["a2"]
    # en uit de lijst verdwenen
    assert "a1" not in load_atoms(dd)


def test_merge_into_herwijst_verwijzingen_elders(tmp_path):
    dd = str(tmp_path)
    ns = _seed(dd)
    ns.add(Insight(id="a4", claim="Wijst naar het bron-atoom.", source="x",
                   links_to=["a1"], supports=["a1"], contradicts=["a1", "a2"]))
    ns.merge_into("a2", "a1", "samengevoegd")
    a4 = load_atoms(dd)["a4"]
    # a1 → a2, ontdubbeld (contradicts had a1 én a2 → één a2)
    assert a4["links_to"] == ["a2"] and a4["supports"] == ["a2"]
    assert a4["contradicts"] == ["a2"]


def test_merge_into_referenties_stapelen_en_grounds(tmp_path):
    dd = str(tmp_path)
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="t", claim="doel", source="Bron A",
                   reference="https://a.nl", provenance="media"))
    ns.add(Insight(id="s", claim="bron", source="Bron B",
                   reference="https://b.nl", grounds="omdat B het mat",
                   status="supported", provenance="media"))
    kaart = ns.merge_into("t", "s", "doel, aangescherpt")
    # tweede bron aantoonbaar: source en reference stapelen ";"-gescheiden
    assert kaart.source == "Bron A; Bron B"
    assert kaart.reference == "https://a.nl; https://b.nl"
    # grounds: target had er geen → overgenomen van source
    assert kaart.grounds == "omdat B het mat"


def test_merge_into_weigert_self_en_onbekend(tmp_path):
    dd = str(tmp_path)
    ns = _seed(dd)
    voor = load_atoms(dd, include_archived=True)
    assert ns.merge_into("a1", "a1", "tekst") is None          # self
    assert ns.merge_into("a1", "bestaat_niet", "tekst") is None
    assert ns.merge_into("bestaat_niet", "a1", "tekst") is None
    assert ns.merge_into("a1", "a2", "") is None               # lege tekst
    assert load_atoms(dd, include_archived=True) == voor       # niets gewijzigd


# ── kb_atoom_merge: via dispatch (banner + inzicht-herwijzing) ───────────────

def test_dispatch_merge_herwijst_ook_inzichten(tmp_path):
    from nooch_village.cockpit2 import dispatch
    dd = str(tmp_path)
    _seed(dd)
    st = _st(dd)
    iid = st.kennisbank.add("Inzicht over materialen")
    st.kennisbank.link(iid, "a1", "support")
    iid2 = st.kennisbank.add("Inzicht met beide atomen")
    st.kennisbank.link(iid2, "a1", "support")
    st.kennisbank.link(iid2, "a2", "counter")
    nxt, msg = dispatch(dd, "kb_atoom_merge",
                        {"target_id": ["a2"], "source_id": ["a1"],
                         "tekst": ["De samengevoegde tekst."], "next": ["/kennisbank"]},
                        username="guest")
    assert "🧩" in msg and "v2" in msg
    st = _st(dd)
    # inzicht 1: evidence herwezen a1 → a2 (geen wees-verwijzing)
    ev1 = [l["atom_id"] for l in st.kennisbank.get(iid)["evidence"]]
    assert ev1 == ["a2"]
    # inzicht 2: wees a1 vervalt want a2 was er al (geen dubbele stem)
    ev2 = [l["atom_id"] for l in st.kennisbank.get(iid2)["evidence"]]
    assert ev2 == ["a2"]


def test_dispatch_merge_weigering_met_banner(tmp_path):
    from nooch_village.cockpit2 import dispatch
    dd = str(tmp_path)
    _seed(dd)
    _, zelf = dispatch(dd, "kb_atoom_merge",
                       {"target_id": ["a1"], "source_id": ["a1"],
                        "tekst": ["x"], "next": ["/kennisbank"]}, username="guest")
    assert zelf.startswith("✗")
    _, onbekend = dispatch(dd, "kb_atoom_merge",
                           {"target_id": ["a1"], "source_id": ["nee"],
                            "tekst": ["x"], "next": ["/kennisbank"]}, username="guest")
    assert onbekend.startswith("✗")
    _, leeg = dispatch(dd, "kb_atoom_merge",
                       {"target_id": [""], "source_id": [""],
                        "tekst": ["x"], "next": ["/kennisbank"]}, username="guest")
    assert leeg.startswith("✗")
    assert "a1" in load_atoms(dd)                              # niets verdwenen


# ── bewerken = nieuwe versie ─────────────────────────────────────────────────

def test_edit_bumpt_versie_fail_soft_voor_bestaande_data(tmp_path):
    dd = str(tmp_path)
    ns = _seed(dd)
    # bestaande data zonder version-veld leest als v1 (pydantic-default)
    assert ns.get("a1").version == 1
    ns.edit_note("a1", claim="Aangescherpt.")
    assert ns.get("a1").version == 2
    ns.edit_note("a1", claim="Aangescherpt.")                  # no-op → geen bump
    assert ns.get("a1").version == 2


# ── render: kaal overzicht + uitklap-detail ──────────────────────────────────

def _frag(dd, q="", active=""):
    from nooch_village.views.kennisbank import render_kennisbank_search
    return render_kennisbank_search(_st(dd), q, "", active, csrf_token="tok")


def test_overzicht_is_kaal_detail_heeft_alles(tmp_path):
    dd = str(tmp_path)
    _seed(dd)
    frag = _frag(dd)
    # kaal: de kop-regel (summary) is alléén de claim-tekst — bron en tags pas in het detail
    kop = frag.split("<summary class='kn-stmttekst'>")[1].split("</summary>")[0]
    assert kop == "Vegan betekent niet plasticvrij." or kop.startswith("Consument")
    assert "chip" not in kop and "recurate" not in kop
    assert "kn-srclink" not in frag                    # klik-op-bron-filter is weg
    # detail: datum (source_date vóór), bron als externe link, versie, tags als chips
    assert "2019-03" in frag
    assert "· toegevoegd" in frag                      # atomen zónder source_date
    assert "target='_blank'" in frag and "https://voorbeeld.nl/olie" in frag
    assert "v1" in frag
    assert "<span class='chip'>materialen</span>" in frag
    # zonder reference: '+ voeg bron toe' op de Bron-plek; mét: het kleine ✏️
    assert "+ voeg bron toe" in frag and "bron wijzigen of toevoegen" in frag
    # bron-koppelvormen inline (URL + bestaand PDF-formulier), geen losse bronlink-uitklapper
    assert "kb_atoom_reference" in frag and "kb_atoom_ref_pdf" in frag
    assert "🔗 bronlink" not in frag
    # gekoppeld: chips die het doel openen; contradicts visueel onderscheiden (contra)
    assert "href='#stmt-a2'" in frag
    assert "kn-koppel contra" in frag and "href='#stmt-a3'" in frag
    # bewerken pas op verzoek, met versie-semantiek
    assert "✏️ bewerk" in frag and "Bewaar (nieuwe versie)" in frag
    # founder dd 2026-07-18: curatie per statement — archiveer-tekstlink in het detail,
    # geen selectie-checkbox in de rij en geen bulk-formulier meer
    assert "kb_atoom_archive" in frag and "📦 archiveer" in frag
    assert "class='kn-sel'" not in frag and "curatieform" not in frag


def test_handle_en_readonly_zonder_csrf(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path)
    _seed(dd)
    met = _frag(dd)
    assert "kn-handle" in met and "⠿" in met and "draggable='true'" in met
    # zonder csrf: read-only — geen handle, geen formulieren of ✏️ (dus ook geen curatie)
    zonder = render_kennisbank_search(_st(dd), "", "", "", csrf_token="")
    assert "kn-handle" not in zonder and "⠿" not in zonder
    assert "kn-sel" not in zonder and "<form" not in zonder
    assert "✏️" not in zonder and "+ voeg bron toe" not in zonder
    # de inhoud zelf blijft leesbaar, inclusief de bron-link
    assert "Vegan betekent niet plasticvrij." in zonder
    assert "target='_blank'" in zonder


def test_zoeken_matcht_op_bron_reference_en_tags(tmp_path):
    dd = str(tmp_path)
    _seed(dd)
    assert "Consument-frame" in _frag(dd, q="harry hemp")      # bron
    assert "driekwart liter olie" in _frag(dd, q="voorbeeld.nl")   # reference
    op_tag = _frag(dd, q="framing")                            # tag
    assert "Consument-frame" in op_tag and "driekwart" not in op_tag


@pytest.mark.smoke
def test_smoke_kennisbank_pagina_met_en_zonder_reference(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path)
    _seed(dd)
    html = render_kennisbank(_st(dd), csrf_token="tok")
    # de nieuwe lijst-markup + modal-markup staan op de pagina
    assert "kn-lijst" in html and "kn-stmt" in html and "kn-stmtdetail" in html
    assert "kn-modal" in html and "Statements mergen" in html
    assert "merge → nieuwe versie" in html and "annuleer" in html
    assert "name='target_id'" in html and "name='source_id'" in html
    assert "kb_atoom_merge" in html
    # atoom mét reference → externe link; zonder → voeg-toe-affordance
    assert "https://voorbeeld.nl/olie" in html and "+ voeg bron toe" in html
    # de oude losse samenvoeg-route uit de selectie-balk is weg (mergen = slepen)
    assert "Voeg samen" not in html
    # zonder csrf ook geen modal- of handle-MARKUP (de inline JS noemt de ids wel,
    # maar vindt dan niets en doet niets)
    ro = render_kennisbank(_st(dd), csrf_token="")
    assert "id='kn-modal'" not in ro and "class='kn-handle'" not in ro


# ── founder-ronde dd 2026-07-18: ruimte winnen (meer content in beeld) ───────

def test_founder_curatie_per_statement_en_naar_spel(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path)
    _seed(dd)
    st = _st(dd)
    # zonder open spel: wél de archiveer-tekstlink, geen 'naar spel'-uitklap
    frag = render_kennisbank_search(st, "", "", "", csrf_token="tok")
    assert "📦 archiveer" in frag and "🎲 naar spel" not in frag
    # met een open spel: per statement een naar-spel-uitklap met spel-keuze
    st.spel.start("een vermoeden", [{"atom_id": "a1", "stance": "support"}], by="t")
    frag2 = render_kennisbank_search(st, "", "", "", csrf_token="tok")
    assert "🎲 naar spel" in frag2 and "kb_atoom_naar_spel" in frag2
    assert "name='atoom'" in frag2 and "name='sid'" in frag2


def test_founder_koppen_tagpill_geen_banner_geen_leeg_inzicht(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path)
    _seed(dd)
    html = render_kennisbank(_st(dd), csrf_token="tok",
                             msg="🔗 PDF als bronlink gekoppeld")
    # 6+7: koppen — "Insights" links, rustige "Signals" rechts (kn-koprustig)
    assert "<h2>Insights</h2>" in html and "Onze inzichten" not in html
    assert "<h2 class='kn-koprustig'>Signals</h2>" in html and "Bibliotheek" not in html
    # 5: de uitlegtekst onder de bibliotheek-kop is weg
    assert "De atomen — het materiaal" not in html
    # 4: '+ Begin een leeg inzicht' is weg (de actiebalk bovenin is de ingang)
    assert "Begin een leeg inzicht" not in html and "kb_new" not in html
    # 3: de groene succes-banner rendert niet meer; een fout-banner (✗) nog wél
    assert "PDF als bronlink gekoppeld" not in html
    err = render_kennisbank(_st(dd), csrf_token="tok",
                            msg="✗ plak een geldige URL (https://…)")
    assert "plak een geldige URL" in err
    # 1: geen bulk-selectie meer
    assert "kn-selbar" not in html and "curatieform" not in html
    # 8: tags-pill naast de Signals-kop; chips zetten de tag in het live-zoekveld (JS)
    assert "kn-tagpill" in html and "kn-tagchip" in html
    assert "data-tag='materialen'" in html and "data-tag='framing'" in html
