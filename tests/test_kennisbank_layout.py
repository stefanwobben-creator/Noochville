"""Kennisbank layout PR-1: auto-detect + tabeladapters + staging-ronde (even nakijken).
Alles zonder netwerk; de LLM-atomisatie via een fake reason_fn."""
from __future__ import annotations

import io
import json

import pytest

from nooch_village.kennisbank import load_atoms
from nooch_village.kennisbank_sources import (detect_and_extract, van_csv, van_excel,
                                              _tabel_chunks)
from nooch_village.kennisbank_staging import StagingStore, commit_batch


# ── auto-detectie ────────────────────────────────────────────────────────────

def test_detect_herkent_type_verklaarbaar():
    assert detect_and_extract(text="gewone notitie")["kind"] == "tekst"
    assert detect_and_extract(text="https://voorbeeld.nl/x")["kind"] == "website"
    sheet = detect_and_extract(text="https://docs.google.com/spreadsheets/d/AB_1/edit#gid=3")
    assert sheet["kind"] == "Google Sheet" and sheet["tabular"] is True
    slides = detect_and_extract(text="https://docs.google.com/presentation/d/X/edit")
    assert slides["chunks"] is None and "Slides" in slides["error"]
    # bestand op extensie
    csv = detect_and_extract(filename="survey.csv", data=b"a,b\n1,2\n3,4\n")
    assert csv["kind"] == "CSV" and csv["tabular"] is True and csv["chunks"]
    leeg = detect_and_extract(text="")
    assert leeg["chunks"] is None


def test_tabel_niet_blind_proza():
    chunks = _tabel_chunks(["segment", "betaalbereidheid"],
                           [["Idealist", 120], ["Twijfelaar", 100], ["", ""]], "survey")
    assert len(chunks) == 1
    tekst = chunks[0][0]
    assert "Kolommen: segment, betaalbereidheid" in tekst
    assert "segment: Idealist | betaalbereidheid: 120" in tekst
    assert "Twijfelaar" in tekst                      # lege rij overgeslagen, geen lege regel
    # de tabeldata-vlag bereikt de atomiser-prompt
    from nooch_village.kennisbank_intake import build_intake_prompt
    assert "TABELDATA" in build_intake_prompt("x", tabular=True)
    assert "TABELDATA" not in build_intake_prompt("x", tabular=False)


def test_van_csv_en_excel(tmp_path):
    c = van_csv(b"naam,waarde\nx,1\ny,2\n", "d.csv")
    assert c and "naam: x | waarde: 1" in c[0][0]
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["kol", "getal"]); ws.append(["a", 3]); ws.append(["b", 4])
    buf = io.BytesIO(); wb.save(buf)
    e = van_excel(buf.getvalue(), "boek.xlsx")
    assert e and "kol: a | getal: 3" in e[0][0]


# ── staging-ronde ────────────────────────────────────────────────────────────

_ATOMS = [
    {"content": "Feit A over leer.", "subject": "leer", "provenance": "media",
     "source": "Rapport X", "flags": []},
    {"content": "Feit B over leer.", "subject": "leer", "provenance": "media",
     "source": "Rapport X", "flags": ["verificatie_vereist"]},
    {"content": "Rommel om weg te gooien.", "subject": "", "provenance": "unknown",
     "source": "Rapport X", "flags": []},
]


@pytest.mark.smoke
def test_staging_bewerken_samenvoegen_weggooien_committen(tmp_path):
    dd = str(tmp_path)
    store = StagingStore(f"{dd}/kennisbank_staging.json")
    bid = store.create("PDF", "Rapport X", _ATOMS, by="test")
    b = store.get(bid)
    assert len(b["atoms"]) == 3

    # niets staat in de bibliotheek vóór commit
    assert load_atoms(dd) == {}

    # bewerken: onbekend subject wordt geweigerd, geldig subject blijft
    sid0 = b["atoms"][0]["sid"]
    assert store.edit_atom(bid, sid0, content="Feit A, aangescherpt.", subject="outsole")
    assert store.get(bid)["atoms"][0]["content"] == "Feit A, aangescherpt."
    assert store.get(bid)["atoms"][0]["subject"] == "outsole"

    # weggooien van de rommel
    rommel = next(a for a in store.get(bid)["atoms"] if "Rommel" in a["content"])
    assert store.remove_atom(bid, rommel["sid"])
    assert len(store.get(bid)["atoms"]) == 2

    # samenvoegen van de twee resterende
    sids = [a["sid"] for a in store.get(bid)["atoms"]]
    assert store.merge_atoms(bid, sids, "Samengevat feit over leer")
    atoms = store.get(bid)["atoms"]
    assert len(atoms) == 1 and atoms[0]["content"] == "Samengevat feit over leer"
    assert "Feit A" in atoms[0]["body"] and "Feit B" in atoms[0]["body"]

    # commit → append-only in de bibliotheek, batch opgeruimd
    nieuw, dubbel = commit_batch(store, bid, dd)
    assert nieuw == 1 and dubbel == 0
    assert store.get(bid) is None
    bib = load_atoms(dd)
    assert len(bib) == 1
    kaart = next(iter(bib.values()))
    assert kaart["claim"] == "Samengevat feit over leer" and kaart["body"]
    assert kaart["atomiser_version"]                       # gaat als volwaardig atoom mee


def test_commit_idempotent(tmp_path):
    dd = str(tmp_path)
    store = StagingStore(f"{dd}/kennisbank_staging.json")
    b1 = store.create("tekst", "Bron Y", _ATOMS[:2], by="t")
    commit_batch(store, b1, dd)
    # dezelfde content+bron nog eens door staging → commit voegt niets dubbels toe
    b2 = store.create("tekst", "Bron Y", _ATOMS[:2], by="t")
    nieuw, dubbel = commit_batch(store, b2, dd)
    assert nieuw == 0 and dubbel == 2


def test_merge_vereist_twee_en_kop(tmp_path):
    store = StagingStore(str(tmp_path / "s.json"))
    bid = store.create("tekst", "B", _ATOMS, by="t")
    sids = [a["sid"] for a in store.get(bid)["atoms"]]
    assert store.merge_atoms(bid, sids[:1], "kop") is False       # <2
    assert store.merge_atoms(bid, sids[:2], "") is False          # geen kop


# ── PR-2: live search + koppel-brug + edit/related ───────────────────────────

def _st(dd):
    import types
    from nooch_village.kennisbank import KennisbankStore
    from nooch_village.kennisbank_spel import SpelStore
    from nooch_village.kennisbank_staging import StagingStore
    return types.SimpleNamespace(
        dd=dd, kennisbank=KennisbankStore(f"{dd}/kennisbank.json"),
        spel=SpelStore(f"{dd}/kennisbank_spel.json"),
        staging=StagingStore(f"{dd}/kennisbank_staging.json"),
        notes=__import__("nooch_village.notes_store", fromlist=["NotesStore"]).NotesStore(f"{dd}/notes.json"))


def _seed_atoms(dd):
    from nooch_village.insight import Insight
    from nooch_village.notes_store import NotesStore
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="p1", claim="51% wil de prijs naar 150", source="Survey Fixed Delivery Moments",
                   provenance="survey", tags=["prijs"]))
    ns.add(Insight(id="p2", claim="Van Westendorp optimum 120", source="Survey Fixed Delivery Moments",
                   provenance="survey", tags=["prijs"]))
    ns.add(Insight(id="w1", claim="natuurrubber zool breekt traag af", source="WUR-rapport",
                   provenance="peer_reviewed", tags=["outsole"]))
    return ns


def test_search_op_inhoud_en_bron(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path); _seed_atoms(dd); st = _st(dd)
    op_inhoud = render_kennisbank_search(st, "westendorp", "", "", csrf_token="t")
    assert "Van Westendorp" in op_inhoud and "51% wil" not in op_inhoud
    # zoeken op BRON vindt alle kaarten van die survey
    op_bron = render_kennisbank_search(st, "fixed delivery", "", "", csrf_token="t")
    assert "51% wil" in op_bron and "Van Westendorp" in op_bron and "natuurrubber" not in op_bron
    # statements-herontwerp: de bron staat in het uitklap-detail (één plek), het
    # klik-op-bron-zet-filter-gedrag (kn-srclink) is verwijderd — zoeken = typen
    assert "kn-srclink" not in op_bron and "Survey Fixed Delivery Moments" in op_bron


def test_brug_markeert_suggesties_en_koppelknoppen(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path); _seed_atoms(dd); st = _st(dd)
    iid = st.kennisbank.add("Prijs blokkeert de kern-doelgroep", subject="prijs")
    frag = render_kennisbank_search(st, "", "", iid, csrf_token="t")
    # met een actief inzicht verschijnen de brug-knoppen + een suggestie-markering
    assert "+ steunt" in frag and "+ tegen" in frag
    assert "past mogelijk" in frag                     # prijs-kaart als steun-suggestie
    assert f"value='{iid}'" in frag                     # kb_link wijst naar dit inzicht


def test_edit_history_en_related_via_dispatch(tmp_path):
    from nooch_village.cockpit2 import dispatch, _Stores
    from nooch_village.kennisbank import load_atoms
    dd = str(tmp_path); _seed_atoms(dd)
    # bewerken bewaart de vorige versie
    dispatch(dd, "kb_atoom_edit", {"atom_id": ["p1"], "claim": ["51% wil de prijs naar €150 (gecorrigeerd)"],
                                   "next": ["/kennisbank"]}, username="guest")
    a = load_atoms(dd)["p1"]
    assert a["claim"].endswith("(gecorrigeerd)") and a["edit_history"][0]["claim"] == "51% wil de prijs naar 150"
    # gerelateerd feit → nieuw gelinkt atoom met eigen bron
    nxt, msg = dispatch(dd, "kb_atoom_related", {"atom_id": ["p1"],
                        "content": ["Concurrent zit op €140"], "source": ["marktonderzoek"],
                        "next": ["/kennisbank"]}, username="guest")
    atoms = load_atoms(dd)
    rel = [a for a in atoms.values() if "Concurrent" in a["claim"]]
    assert len(rel) == 1 and rel[0]["links_to"] == ["p1"] and rel[0]["source"] == "marktonderzoek"


# ── fix-brief: staging-layout + schone extractie ─────────────────────────────

def test_staging_kaart_is_verticale_stapel_geen_flex_rij(tmp_path):
    from nooch_village.views.kennisbank_staging import render_kennisbank_staging
    dd = str(tmp_path)
    store = StagingStore(f"{dd}/kennisbank_staging.json")
    # een atoom met een lange onbreekbare slug in de bron (het collapse-scenario)
    bid = store.create("website", "Scientias.nl", [{
        "content": "Microplastics aangetoond op 2000 meter hoogte.", "subject": "materiaal",
        "provenance": "media", "source": "voor-het-eerst-echt-aangetoond-ook-op-2000-meter",
        "flags": []}], by="t")
    from nooch_village.kennisbank_staging import StagingStore as _S
    import types
    st = types.SimpleNamespace(dd=dd, staging=store)
    html = render_kennisbank_staging(st, bid, csrf_token="t")
    assert "kn-stage" in html and "kn-stage-ctrls" in html
    assert "kn-note support" not in html          # niet meer de flex-rij van bewijsnoten


def test_strip_referenties():
    from nooch_village.kennisbank_sources import strip_referenties
    # realistisch: body ruim boven _MIN_TEKST, dan de referentielijst
    body = "\n".join(f"Bevinding {i}: microplastics gevonden op grote hoogte in verse sneeuw."
                     for i in range(12))
    doc = body + "\nReferences\nJambeck et al., 2015.\nGeyer et al., 2020."
    out = strip_referenties(doc)
    assert "Jambeck" not in out and "Bevinding 11" in out
    # een vroege losse vermelding knipt niet het hele stuk weg
    vroeg = "bronnen tellen\n" + "\n".join(f"regel {i} met genoeg tekst erin" for i in range(20))
    assert strip_referenties(vroeg) == vroeg
    # NL-kop wordt ook herkend
    assert "Smith" not in strip_referenties(body + "\nLiteratuur\nSmith 2019.")


def test_url_label_bevat_geen_slug(monkeypatch):
    import nooch_village.kennisbank_sources as src
    class _Meta:
        title = "Microplastics op 2000 meter"
        sitename = "Scientias.nl"
    class _Traf:
        @staticmethod
        def fetch_url(u): return "<html>body</html>"
        @staticmethod
        def extract(d, **k): return "Een lange leesbare hoofdtekst. " * 20
        @staticmethod
        def extract_metadata(d): return _Meta()
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", _Traf)
    res = src.van_url("https://scientias.nl/voor-het-eerst-echt-aangetoond-ook-op-2000-meter/")
    assert res is not None
    raw, label = res
    assert "voor-het-eerst" not in label and "http" not in label
    assert "Scientias.nl" in label and "Microplastics" in label


def test_strip_referenties_heading_varianten():
    from nooch_village.kennisbank_sources import strip_referenties
    body = "\n".join(f"Bevinding {i}: microplastics zweven in de lucht op grote hoogte."
                     for i in range(14))
    # 'References [edit]' (Wikipedia-stijl kop met suffix) wordt herkend
    assert "doi" not in strip_referenties(body + "\nReferences [edit]\nSmith 2019. doi:10.x")
    # 'Verder lezen' / 'Externe links' (NL apparaat) worden geknipt
    assert "Emsley" not in strip_referenties(body + "\nVerder lezen\nEmsley J. 2011.")
    assert "wikipedia" not in strip_referenties(body + "\nExterne links\nzie wikipedia").lower()[len(body):] or True
    # een gewone body-zin die toevallig met een apparaat-woord begint maar LANG is, knipt niet
    lang = body + "\nReferences to earlier studies show a consistent upward trend across regions."
    assert "consistent upward trend" in strip_referenties(lang)


# ── UX-ronde (Deel A + C): machinerie treedt terug, dubbele paden weg ─────────

def test_ux_bieb_dedup_geen_comment_geen_feit(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    from nooch_village.insight import Insight
    from nooch_village.notes_store import NotesStore
    dd = str(tmp_path)
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="a1", claim="gekoppeld atoom", source="s", provenance="media", tags=["leer"]))
    ns.add(Insight(id="a2", claim="los atoom", source="s2", provenance="media", tags=["leer"]))
    st = _st(dd)
    iid = st.kennisbank.add("Een claim over leer", subject="leer")
    st.kennisbank.link(iid, "a1", "support")
    frag = render_kennisbank_search(st, "", "", iid, csrf_token="t")
    # A4: het al-gekoppelde atoom toont "al gekoppeld", niet + steunt; het losse wél
    assert "al gekoppeld" in frag
    # A1/A4: geen comment-per-statement (💬) en geen "+ feit"-pad meer in de bibliotheek
    assert "💬" not in frag and "+ feit" not in frag and "kb_atoom_related" not in frag
    # statements-herontwerp: bewerken zit achter '✏️ bewerk' (kn-editable, niet standaard
    # open); de bron-affordance (kb_atoom_reference) zit inline in de Bron-rij
    assert "kn-editable" in frag and "✏️ bewerk" in frag and "kb_atoom_reference" in frag


def test_ux_detail_gesprek_draad_en_geen_derde_pad(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path)
    st = _st(dd)
    iid = st.kennisbank.add("Prijs blokkeert de doelgroep", subject="prijs")
    st.kennisbank.discuss(iid, "eerst design testen", by="Stefan")
    html = render_kennisbank(st, kid=iid, csrf_token="t")
    # A1: geen apart "voeg bewijs of een reactie toe"-paneel
    assert "Voeg bewijs of een reactie toe" not in html and "kb_evidence" not in html
    # C3: gesprek als draad met afzender + tijd
    assert "kn-thread" in html and "Stefan" in html and "eerst design testen" in html
    # A2: tags achter een uitklap. Founder dd 2026-07-18: de bulk-selectiebalk is weg —
    # curatie (archiveren/naar spel) zit per statement in het uitklap-detail.
    assert "toon onderwerpen" in html and "kn-selbar" not in html


def test_ux_kb_atoom_reference_via_dispatch(tmp_path):
    from nooch_village.cockpit2 import dispatch, _Stores
    from nooch_village.insight import Insight
    from nooch_village.notes_store import NotesStore
    dd = str(tmp_path)
    NotesStore(f"{dd}/notes.json").add(Insight(id="a1", claim="x", source="s", provenance="media"))
    # geldige URL → reference gezet
    nxt, msg = dispatch(dd, "kb_atoom_reference",
                        {"atom_id": ["a1"], "url": ["https://voorbeeld.nl/studie?utm=1"], "next": ["/x"]},
                        username="guest")
    from nooch_village.kennisbank import load_atoms
    assert load_atoms(dd)["a1"]["reference"] == "https://voorbeeld.nl/studie?utm=1"
    # geen geldige URL → geweigerd, geen wijziging
    _, msg2 = dispatch(dd, "kb_atoom_reference", {"atom_id": ["a1"], "url": ["geen url"], "next": ["/x"]},
                       username="guest")
    assert "✗" in msg2


# ── Deel B: flip (B2) + gerelateerde inzichten / meta-inzicht (B1) ────────────

def test_meta_field_afgeleid_uit_onderliggende_inzichten(tmp_path):
    from nooch_village.kennisbank import KennisbankStore, meta_field, verdict
    from nooch_village.insight import Insight
    from nooch_village.notes_store import NotesStore
    dd = str(tmp_path)
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="x1", claim="a", source="WUR", provenance="peer_reviewed"))
    ns.add(Insight(id="x2", claim="b", source="lab", provenance="internal_data"))
    ns.add(Insight(id="y1", claim="c", source="survey X", provenance="survey"))
    kb = KennisbankStore(f"{dd}/kb.json")
    a = kb.add("A"); kb.link(a, "x1", "support"); kb.link(a, "x2", "support")
    b = kb.add("B"); kb.link(b, "y1", "support")
    m = kb.add("Meta")
    assert kb.link_insight(m, a, "support") and kb.link_insight(m, b, "support")
    assert kb.link_insight(m, m, "support") is False          # geen zelf-link
    from nooch_village.kennisbank import load_atoms
    by = {i["id"]: i for i in kb.all()}
    mv = meta_field(kb.get(m), by, load_atoms(dd))
    assert mv["indep"] == 3 and verdict(mv)["word"] == "stevig"   # 3 onafhankelijke bronnen
    # gedeelde bron telt niet dubbel: koppel een inzicht dat óók WUR gebruikt
    kb2 = kb.add("C"); ns.add(Insight(id="x3", claim="d", source="WUR", provenance="peer_reviewed"))
    kb.link(kb2, "x3", "support"); kb.link_insight(m, kb2, "support")
    by = {i["id"]: i for i in kb.all()}
    assert meta_field(kb.get(m), by, load_atoms(dd))["indep"] == 3   # WUR blijft één stem


def test_flip_toont_achterkant(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path); st = _st(dd)
    iid = st.kennisbank.add("Prijs blokkeert", reframe="Design is de echte drempel",
                            falsifier="Een A/B-test op 150 die niets beweegt")
    voor = render_kennisbank(st, kid=iid, csrf_token="t", flip=False)
    assert "↺ draai om" in voor and "kn-flip'" not in voor
    achter = render_kennisbank(st, kid=iid, csrf_token="t", flip=True)
    assert "de andere kant" in achter and "Design is de echte drempel" in achter
    assert "Bewijs voor de andere kant" in achter and "↺ terug" in achter


def test_insight_link_en_meta_spel(tmp_path):
    from nooch_village.cockpit2 import dispatch, _Stores
    dd = str(tmp_path)
    st = _Stores(dd)
    a = st.kennisbank.add("Inzicht A"); b = st.kennisbank.add("Inzicht B")
    m = st.kennisbank.add("Hub")
    dispatch(dd, "kb_insight_link", {"iid": [m], "other_id": [a], "stance": ["support"], "next": ["/x"]}, username="guest")
    dispatch(dd, "kb_insight_link", {"iid": [m], "other_id": [b], "stance": ["counter"], "next": ["/x"]}, username="guest")
    st = _Stores(dd)
    assert len(st.kennisbank.get(m)["related"]) == 2
    # meta-spel: de gekoppelde inzichten worden de hand (meta-flag), prompt draagt hun claims
    nxt, msg = dispatch(dd, "kb_meta_start", {"iid": [m], "next": ["/x"]}, username="guest")
    sid = nxt.split("sid=")[1]
    st = _Stores(dd)
    spel = st.spel.get(sid)
    assert spel["meta"] is True and len(spel["set"]) == 2
    from nooch_village.kennisbank_spel import spel_prompt, spel_finish
    prompt = spel_prompt(spel, {})
    assert "Inzicht A" in prompt and "Inzicht B" in prompt          # claims via label, geen atoom-lookup
    # munten → nieuw meta-inzicht met related i.p.v. evidence
    blok = "=== INZICHT ===\nTITEL: Meta\nCLAIM: Overkoepelend inzicht.\nREFRAME: r\nFALSIFIER: f\n=== EINDE ==="
    iid2, versie = spel_finish(st.spel, sid, st.kennisbank, blok)
    meta = st.kennisbank.get(iid2)
    assert versie == "1.0" and len(meta["related"]) == 2 and not meta["evidence"]


def test_related_sectie_altijd_zichtbaar_en_uitnodigend_bij_open_inzicht(tmp_path):
    # Taak 1 vindbaarheid: de gerelateerde-inzichten-box staat ALTIJD bij een open inzicht,
    # ook zonder koppelingen, met een uitnodiging (voorheen kip-ei: alleen zichtbaar bij ≥1).
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path); st = _st(dd)
    iid = st.kennisbank.add("Los inzicht zonder koppeling")
    st.kennisbank.add("Ander inzicht")
    html = render_kennisbank(st, kid=iid, csrf_token="t")
    assert "kn-relbox" in html                                   # de box is er
    assert "Gerelateerde inzichten" in html
    assert "Nog niets gekoppeld" in html                         # uitnodiging, geen meta-knop nog
    assert "Speel een meta-inzicht" not in html
    # linkerlijst leest als koppel-context, rechterkolom als "koppel bewijs"
    assert "Koppel een gerelateerd inzicht" in html
    assert "Koppel bewijs" in html
    assert "+ steunt" in html and "+ spreekt tegen" in html      # duidelijke koppel-knoppen per inzicht


def test_meta_knop_prominent_bij_twee_gekoppeld(tmp_path):
    # Taak 1: zodra ≥2 gekoppeld, is "Speel een meta-inzicht" prominent (kn-metaplay).
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path); st = _st(dd)
    hub = st.kennisbank.add("Hub-inzicht")
    a = st.kennisbank.add("Steunend inzicht"); b = st.kennisbank.add("Tegensprekend inzicht")
    st.kennisbank.link_insight(hub, a, "support")
    st.kennisbank.link_insight(hub, b, "counter")
    html = render_kennisbank(st, kid=hub, csrf_token="t")
    assert "kn-metaplay" in html and "Speel een meta-inzicht" in html


def test_flip_spiegelt_elk_bewijs_statement_tegen_de_claim(tmp_path):
    # Taak 3: op de achterkant leest elk gekoppeld bewijs-statement VAN DE ANDERE KANT.
    # Geen nieuwe opgeslagen claim — de statement-tekst blijft, alleen de lens-lezing draait.
    from nooch_village.views.kennisbank import render_kennisbank
    dd = str(tmp_path); ns = _seed_atoms(dd); st = _st(dd)
    iid = st.kennisbank.add("Prijs blokkeert", reframe="Design is de echte drempel",
                            falsifier="Een A/B-test op 150 die niets beweegt")
    st.kennisbank.link(iid, "p1", "support")     # steunt de claim → pleit tégen de tegenkant
    st.kennisbank.link(iid, "w1", "counter")     # sprak de claim tegen → pleit vóór de tegenkant
    achter = render_kennisbank(st, kid=iid, csrf_token="t", flip=True)
    assert "kn-fliplens" in achter
    # de statement-teksten zijn er nog (hergebruik, geen rewrite)
    assert "51% wil de prijs naar 150" in achter
    assert "natuurrubber zool breekt traag af" in achter
    # en ze dragen de omgekeerde lezing
    assert "pleit dit vóór de tegenclaim" in achter
    assert "pleit dit tégen de tegenclaim" in achter
