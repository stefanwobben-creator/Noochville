"""Wiki brok 1 — de rol-note als pagina: links, backlinks en feiten met grond.

De pagina is GEEN nieuw type: het is de bestaande note (kind="note") in de AttachmentStore. Deze
tests bewaken drie beloften:
  1. een `[[link]]` wijst nooit naar een gok (dubbele titel → geen link),
  2. backlinks zijn afgeleid, niet opgeslagen,
  3. grond wordt bij het LEZEN vergeleken — een verlopen certificaat draagt vanzelf niets meer.
"""
from __future__ import annotations

import json
import os

import pytest

from nooch_village import cert_register, cockpit2, wiki
from nooch_village.attachments import AttachmentStore, body_cap
from nooch_village.views.wiki import render_pagina

OWNER = "mother_earth__nooch__creator_of_shoes"
CIRCLE = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _stores(tmp_path):
    return cockpit2._Stores(_dd(tmp_path))


def _changelog(dd):
    path = os.path.join(dd, "artefact_changelog.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ── links: resolutie ────────────────────────────────────────────────────────

def test_link_lost_op_via_id_en_via_unieke_titel(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="HyphaLite", body="")
    pags = wiki.paginas(st.att)
    assert wiki.resolve(a.id, pags).id == a.id                    # op id
    assert wiki.resolve("hyphalite", pags).id == a.id             # op titel, hoofdletter-ongevoelig
    assert wiki.resolve("bestaat niet", pags) is None


def test_dubbele_titel_lost_bewust_niet_op(tmp_path):
    # Twee pagina's met dezelfde naam: liever zichtbaar 'bestaat niet' dan een link naar de
    # verkeerde pagina. Op id blijven ze allebei gewoon bereikbaar.
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="Vegan")
    b = st.att.add(CIRCLE, "note", title="Vegan")
    pags = wiki.paginas(st.att)
    assert wiki.resolve("Vegan", pags) is None
    assert wiki.resolve(a.id, pags).id == a.id and wiki.resolve(b.id, pags).id == b.id


def test_backlinks_zijn_afgeleid_uit_de_bodies(tmp_path):
    st = _stores(tmp_path)
    doel = st.att.add(OWNER, "note", title="HyphaLite")
    bron = st.att.add(OWNER, "note", title="Vamp", body="De vamp is van [[HyphaLite]].")
    st.att.add(OWNER, "note", title="Laces", body="Organic cotton, geen verwijzing.")
    pags = wiki.paginas(st.att)
    assert [b.id for b in wiki.backlinks(doel, pags)] == [bron.id]
    assert wiki.backlinks(bron, pags) == []                       # geen wederkerige link verzonnen


def test_ontbrekende_links_zijn_de_verlanglijst(tmp_path):
    st = _stores(tmp_path)
    p = st.att.add(OWNER, "note", title="Vamp", body="[[HyphaLite]] en nog eens [[hyphalite]].")
    pags = wiki.paginas(st.att)
    assert wiki.ontbrekende_links(p, pags) == ["HyphaLite"]       # dedup, en niets aangemaakt
    assert len(wiki.paginas(st.att)) == 1


# ── feiten: normalisatie ────────────────────────────────────────────────────

def test_maak_feit_normaliseert_en_weigert_leeg():
    assert wiki.maak_feit("   ") is None
    f = wiki.maak_feit("  De  outsole is   Pliant ", soort="kroniek", ref="abc123")
    assert f["tekst"] == "De outsole is Pliant"
    assert f["grond"]["soort"] == "kroniek" and f["grond"]["ref"] == "abc123"
    # onbekende soort → geen grond (het feit mag bestaan, maar heet dan ongegrond)
    assert wiki.maak_feit("iets", soort="onzin")["grond"] == {}


# ── feiten: grond wordt bij het LEZEN vergeleken ────────────────────────────

def test_grond_kroniek_bevestigd_is_gegrond_leeg_is_niet(tmp_path):
    st = _stores(tmp_path)
    goed = st.evidence.record(role_id="harry_hemp", skill="openalex_evidence", query="hemp",
                              source="openalex", status="bevestigd")
    leeg = st.evidence.record(role_id="harry_hemp", skill="openalex_evidence", query="x",
                              source="openalex", status="leeg")
    g = wiki.grond_status(wiki.maak_feit("a", soort="kroniek", ref=goed["id"]), ledger=st.evidence)
    assert g["status"] == wiki.GEGROND
    l = wiki.grond_status(wiki.maak_feit("a", soort="kroniek", ref=leeg["id"]), ledger=st.evidence)
    assert l["status"] == wiki.ONGECONTROLEERD          # leeg is een echt resultaat, geen bewijs


def test_grond_onbekend_record_is_ontbreekt_niet_stil_goed(tmp_path):
    st = _stores(tmp_path)
    g = wiki.grond_status(wiki.maak_feit("a", soort="kroniek", ref="bestaatniet"),
                          ledger=st.evidence)
    assert g["status"] == wiki.ONTBREEKT


def _cert_record(st, *, geldig_tot: str, claim: str = "vegan"):
    return st.evidence.record(
        role_id="compliance", skill=cert_register.SKILL, query=claim,
        source=cert_register.EXTERN, status="bevestigd",
        meta={"feit": claim, "instantie": "PETA", "geldig_tot": geldig_tot, "claims": [claim]})


def test_verlopen_certificaat_verliest_zijn_grond_vanzelf(tmp_path):
    # De kern van de architectuurbeslissing: een goedkeuring mag zijn bewijs niet overleven.
    st = _stores(tmp_path)
    r = _cert_record(st, geldig_tot="2030-01-01")
    feit = wiki.maak_feit("De schoen is vegan", soort="cert", ref=r["id"])
    assert wiki.grond_status(feit, ledger=st.evidence, vandaag="2026-08-20")["status"] == wiki.GEGROND
    # zelfde record, latere dag → vervallen. Er is niets opgeslagen dat dit hoeft bij te werken.
    later = wiki.grond_status(feit, ledger=st.evidence, vandaag="2031-01-01")
    assert later["status"] == wiki.VERVALLEN and "expired" in later["label"]


def test_certificaat_zonder_leesbare_datum_draagt_niet(tmp_path):
    st = _stores(tmp_path)
    r = _cert_record(st, geldig_tot="")
    g = wiki.grond_status(wiki.maak_feit("a", soort="cert", ref=r["id"]), ledger=st.evidence)
    assert g["status"] == wiki.VERVALLEN               # onbekend is nadrukkelijk niet 'geldig'


def test_kroniek_record_dat_geen_certificaat_is_wordt_geweigerd(tmp_path):
    st = _stores(tmp_path)
    r = st.evidence.record(role_id="x", skill="claims_check", query="vegan",
                           source="claims_check", status="bevestigd")
    g = wiki.grond_status(wiki.maak_feit("a", soort="cert", ref=r["id"]), ledger=st.evidence)
    assert g["status"] == wiki.ONTBREEKT               # eigen skill-run is geen extern certificaat


def test_grond_policy_actief_versus_gearchiveerd(tmp_path):
    st = _stores(tmp_path)
    p = st.att.add(OWNER, "policy", title="Alleen plantaardig", domain="Materials")
    g = wiki.grond_status(wiki.maak_feit("a", soort="policy", ref=p.id), store=st.att)
    assert g["status"] == wiki.GEGROND and g["label"] == "Alleen plantaardig"
    st.att.archive(p.id)
    st2 = cockpit2._Stores(st.dd)
    g2 = wiki.grond_status(wiki.maak_feit("a", soort="policy", ref=p.id), store=st2.att)
    assert g2["status"] == wiki.VERVALLEN


def test_geciteerde_bron_is_herkomst_geen_bewijs():
    zonder = wiki.grond_status(wiki.maak_feit("a", soort="bron"))
    assert zonder["status"] == wiki.ONTBREEKT
    met = wiki.grond_status(wiki.maak_feit("a", soort="bron", url="https://voorbeeld.nl"))
    assert met["status"] == wiki.ONGECONTROLEERD       # nooit stilzwijgend 'gegrond'


def test_feit_zonder_grond_heet_ongegrond():
    assert wiki.grond_status(wiki.maak_feit("a"))["status"] == wiki.ONGEGROND


# ── opslag: de body-cap van een pagina ──────────────────────────────────────

def test_elke_soort_heeft_de_maat_van_zijn_eigen_ding(tmp_path):
    """De caps verschillen omdat de dingen verschillen, niet omdat het historie is.

    Een NOTE is een wiki-pagina: een document. Een POLICY was een briefje van 4000 — tot hij zijn
    eigen machine-leesbare regels ging dragen naast de prosa, en dus een document met twee lezers
    werd. Dat paste niet, en de store kapte stil af: er stond een half codeblok in COPYCHECK-001.
    Een TOOL is nog steeds een briefje."""
    assert body_cap("note") == 40_000
    assert body_cap("policy") == 12_000
    assert body_cap("tool") == 4000                                      # ongewijzigd
    store = AttachmentStore(str(tmp_path / "att.json"))
    lang = "x" * 20_000
    assert len(store.add(OWNER, "note", body=lang).body) == 20_000
    assert len(store.add(OWNER, "policy", body=lang).body) == 12_000
    assert len(store.add(OWNER, "tool", body=lang).body) == 4000


def test_te_lange_body_wordt_geweigerd_niet_stil_afgekapt(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p", body="origineel")
    nxt, msg = cockpit2.dispatch(dd, "artefact_edit",
                                 {"aid": [a.id], "body": ["y" * 40_001], "next": ["/"]},
                                 username="guest")
    assert "too long" in msg
    assert cockpit2._Stores(dd).att.get(a.id).body == "origineel"       # niets geschreven


# ── routes: feiten toevoegen/verwijderen ────────────────────────────────────

def test_route_feit_add_schrijft_meta_versie_en_changelog(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="HyphaLite")
    nxt, msg = cockpit2.dispatch(dd, "pagina_feit_add",
        {"aid": [a.id], "tekst": ["Mycelium-based upper"], "soort": ["bron"],
         "url": ["https://voorbeeld.nl/hypha"], "next": ["/"]}, username="guest")
    assert "fact added" in msg
    vers = cockpit2._Stores(dd).att.get(a.id)
    feiten = wiki.feiten(vers)
    assert [f["tekst"] for f in feiten] == ["Mycelium-based upper"]
    assert feiten[0]["grond"]["url"] == "https://voorbeeld.nl/hypha"
    assert vers.versions[-1]["change_note"] == "feit toegevoegd"        # zichtbaar in de historie
    assert [e["action"] for e in _changelog(dd)] == ["edit"]


def test_route_feit_add_zonder_tekst_doet_niets(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p")
    nxt, msg = cockpit2.dispatch(dd, "pagina_feit_add",
                                 {"aid": [a.id], "tekst": ["  "], "next": ["/"]}, username="guest")
    assert "needs text" in msg
    assert wiki.feiten(cockpit2._Stores(dd).att.get(a.id)) == []


def test_route_feit_niet_vervuller_krijgt_403(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Bob", "bob@nooch.earth")                  # bestaat, vervult OWNER niet
    a = st.att.add(OWNER, "note", title="p")
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "pagina_feit_add",
                          {"aid": [a.id], "tekst": ["sluipweg"], "next": ["/"]},
                          username="bob@nooch.earth")
    assert wiki.feiten(cockpit2._Stores(dd).att.get(a.id)) == []


def test_route_feit_del_haalt_de_juiste_weg_en_laat_spoor(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p")
    for t in ("eerste", "tweede", "derde"):
        cockpit2.dispatch(dd, "pagina_feit_add",
                          {"aid": [a.id], "tekst": [t], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "pagina_feit_del",
                      {"aid": [a.id], "i": ["1"], "next": ["/"]}, username="guest")
    vers = cockpit2._Stores(dd).att.get(a.id)
    assert [f["tekst"] for f in wiki.feiten(vers)] == ["eerste", "derde"]
    assert "feit verwijderd: tweede" in vers.versions[-1]["change_note"]


def test_route_feit_del_onbekende_index_doet_niets(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "note", title="p")
    cockpit2.dispatch(dd, "pagina_feit_add",
                      {"aid": [a.id], "tekst": ["enig feit"], "next": ["/"]}, username="guest")
    nxt, msg = cockpit2.dispatch(dd, "pagina_feit_del",
                                 {"aid": [a.id], "i": ["7"], "next": ["/"]}, username="guest")
    assert "unknown fact" in msg
    assert len(wiki.feiten(cockpit2._Stores(dd).att.get(a.id))) == 1


def test_route_feit_op_niet_pagina_weigert(tmp_path):
    # Een policy is geen wiki-pagina: feiten horen bij notes, niet bij elk artefact.
    dd = _dd(tmp_path)
    p = cockpit2._Stores(dd).att.add(OWNER, "policy", title="beleid")
    nxt, msg = cockpit2.dispatch(dd, "pagina_feit_add",
                                 {"aid": [p.id], "tekst": ["x"], "next": ["/"]}, username="guest")
    assert "page not found" in msg


# ── scherm ──────────────────────────────────────────────────────────────────

def test_pagina_toont_body_feit_grond_en_backlink(tmp_path):
    st = _stores(tmp_path)
    doel = st.att.add(OWNER, "note", title="HyphaLite", body="Een mycelium-materiaal.")
    st.att.add(OWNER, "note", title="Vamp", body="De vamp is van [[HyphaLite]].")
    r = _cert_record(st, geldig_tot="2030-01-01")
    st.att.update(doel.id, meta={"feiten": [wiki.maak_feit("Vegan gecertificeerd",
                                                           soort="cert", ref=r["id"])]})
    html = render_pagina(cockpit2._Stores(st.dd),
                         doel.id, csrf_token="tok", username="guest")
    assert "HyphaLite" in html and "Een mycelium-materiaal." in html
    assert "Vegan gecertificeerd" in html and "PETA" in html and "valid until" in html
    assert "Vamp" in html                                   # backlink-kaart
    assert "class='card'" in html and "ptitle" in html      # bestaand kaart-idioom


def test_pagina_linkt_bestaande_pagina_en_markeert_onbekende(tmp_path):
    st = _stores(tmp_path)
    doel = st.att.add(OWNER, "note", title="HyphaLite")
    bron = st.att.add(OWNER, "note", title="Vamp",
                      body="[[HyphaLite]] maar ook [[Nog Niet Geschreven]].")
    html = render_pagina(st, bron.id, csrf_token="tok", username="guest")
    assert f"/pagina?id={doel.id}" in html                   # bestaande link
    assert "Nog Niet Geschreven" in html and "chip muted" in html   # verlanglijst, geen link
    assert "Wanted pages" in html


def test_pagina_editknop_alleen_voor_vervuller(tmp_path):
    st = _stores(tmp_path)
    st.people.add("Alice", "alice@nooch.earth")
    st.assign.assign(OWNER, "person", st.people.by_email("alice@nooch.earth").id)
    st.people.add("Bob", "bob@nooch.earth")
    a = st.att.add(OWNER, "note", title="HyphaLite")
    st2 = cockpit2._Stores(st.dd)

    filler = render_pagina(st2, a.id, csrf_token="tok", username="alice@nooch.earth")
    assert "artefact_edit" in filler and "pagina_feit_add" in filler

    outsider = render_pagina(st2, a.id, csrf_token="tok", username="bob@nooch.earth")
    assert "HyphaLite" in outsider                            # lezen mag
    assert "artefact_edit" not in outsider and "pagina_feit_add" not in outsider


def test_onbekende_pagina_geeft_nette_melding(tmp_path):
    st = _stores(tmp_path)
    assert "Page not found" in render_pagina(st, "NOTE-BESTAAT-999", csrf_token="tok",
                                             username="guest")


def test_notes_tab_linkt_naar_de_pagina(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="HyphaLite")
    html = cockpit2.render_node(st, OWNER, "notes", csrf_token="tok", username="guest")
    assert f"/pagina?id={a.id}" in html and "open page" in html
