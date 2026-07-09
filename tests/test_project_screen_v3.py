"""SCOPE 1 — projectscherm-herindeling (wall links + structuur-kantlijn rechts).

Puur weergave. Dekt: alle bestaande acties bereikbaar vanuit de nieuwe layout; de vier
checklist-states onderscheidbaar (incl. fail-soft op ontbrekend payload_ok); voortgangsbalk telt
alleen afgevinkte items; verzwakt-blok conditioneel; dangling-rol-waarschuwing; read-only kijker
zonder bewerk-knoppen; pushState/popstate in de bord-JS; opdracht als eerste wall-post (omschrijving
-veld weg).
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2
from nooch_village.views.projects import render_project, _modal_html

_RID = "mother_earth__nooch__website_developer"


def _setup(tmp_path, *, missie="", owner=_RID, description=""):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    codie = st.personas.add("Codie")
    st.assign.assign(_RID, "persona", codie.id)          # AI-filler → ai_reply beschikbaar
    pid = st.projects.create(owner, "Checkout flow verbeteren", "human",
                             missie_impact=missie, description=description)
    return dd, pid, codie


def _frag(dd, pid, csrf="t"):
    return render_project(cockpit2._Stores(dd), pid, csrf_token=csrf, fragment=True)


# a. elke bestaande actie is bereikbaar vanuit de nieuwe layout
def test_a_alle_acties_bereikbaar(tmp_path):
    dd, pid, codie = _setup(tmp_path, missie="verzwakt", description="doe iets")
    st = cockpit2._Stores(dd)
    # feed-comment (mens) → react_add + feed_edit + feed_remove; attachment → attach_remove;
    # checklist met item → check_toggle/check_remove; check_add via '+ item'.
    st.projects.add_feed_entry(pid, "let op de tone", kind="comment", author_type="human")
    st.projects.attach_add(pid, url="https://ref.example", title="Referentie")
    cl = st.projects.checklist_add(pid, title="Uitvoerplan")
    st.projects.check_add(pid, cl["id"], "onderzoek", skill="openalex_evidence", query="x")
    frag = _frag(dd, pid)
    # proj_describe staat hier BEWUST niet meer: de opdracht-editor is uit de UI verwijderd (scope e).
    # De dispatch-tak blijft bestaan en is via de API bereikbaar (zie test_project_modal: dispatch
    # proj_describe werkt nog), maar heeft geen UI-caller meer — daarom niet in deze UI-bereikbaarheidslijst.
    for action in ("proj_rename", "proj_status", "proj_done", "proj_archive", "proj_delete",
                   "proj_setowner", "proj_settrekker", "proj_setprivate", "proj_setimpact",
                   "proj_setdue", "checklist_add", "check_toggle", "check_add",
                   "check_remove", "attach_file", "attach_add", "attach_remove", "proj_feed",
                   "ai_reply", "react_add", "feed_edit", "feed_remove", "proj_agendeer_verzwakt"):
        assert f"value='{action}'" in frag or f'value="{action}"' in frag, f"actie ontbreekt: {action}"
    assert "value='proj_describe'" not in frag        # UI-ingang verwijderd; dispatch blijft API-bereikbaar


# b. checklist rendert de vier states onderscheidbaar; ⚠ toont de reden; ontbrekend payload_ok = uitvoerbaar
def test_b_checklist_states_onderscheidbaar(tmp_path):
    dd, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    cl = st.projects.checklist_add(pid, title="Uitvoerplan")
    cid = cl["id"]
    st.projects.check_add(pid, cid, "afgerond-item", skill="openalex_evidence", query="q")
    st.projects.check_add(pid, cid, "uitvoerbaar-item", skill="openalex_evidence", query="barefoot")  # geen payload_ok → ·
    st.projects.check_add(pid, cid, "warn-item", skill="competitor_news", reason="brands ontbreekt", payload_ok=False)
    st.projects.check_add(pid, cid, "noskill-item", skill=None, reason="mens nodig")
    # eerste item afvinken
    first = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]["id"]
    st.projects.check_toggle(pid, cid, first)
    frag = _frag(dd, pid)
    assert "ck-skill" in frag                                   # skill-naam getoond (uitvoerbaar/warn)
    assert "ck-warn" in frag and "brands ontbreekt" in frag     # ⚠ + reden letterlijk
    assert "ck-noskill" in frag                                 # ○ geen-skill
    assert "b-warn" in frag and "b-noskill" in frag             # ⚠ en ○ verschillen visueel (box-klasse)
    # het uitvoerbare item (query=barefoot) staat NIET als ⚠ gemarkeerd
    assert "uitvoerbaar-item" in frag
    # ontbrekend payload_ok telt niet als ongeldig: precies één ⚠-blok (het warn-item), niet meer
    assert frag.count("payload onvolledig") == 1


# b2. item met ONTBREKEND payload_ok-veld → uitvoerbaar, niet ⚠ (legacy vóór PR #136)
def test_b2_ontbrekend_payload_ok_is_uitvoerbaar(tmp_path):
    dd, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    cl = st.projects.checklist_add(pid, title="Uitvoerplan")
    st.projects.check_add(pid, cl["id"], "legacy-item", skill="ngram_culture", query="vegan")
    # zeker weten: geen payload_ok-veld op het item
    item = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]
    assert "payload_ok" not in item
    frag = _frag(dd, pid)
    assert "ck-skill" in frag                       # als uitvoerbaar gerenderd (skill-chip)
    assert "payload onvolledig" not in frag         # NIET als ⚠ gemarkeerd


# c. voortgangsbalk telt alleen afgevinkte items (⚠ en ○ tellen als open)
def test_c_voortgang_telt_alleen_afgevinkt(tmp_path):
    dd, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    cl = st.projects.checklist_add(pid, title="Uitvoerplan")
    cid = cl["id"]
    st.projects.check_add(pid, cid, "a", skill="openalex_evidence", query="q")
    st.projects.check_add(pid, cid, "b", skill="competitor_news", reason="x", payload_ok=False)
    st.projects.check_add(pid, cid, "c", skill=None, reason="mens")
    st.projects.check_add(pid, cid, "d", skill="openalex_evidence", query="q")
    first = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]["id"]
    st.projects.check_toggle(pid, cid, first)       # 1 van 4 af
    frag = _frag(dd, pid)
    assert "1/4" in frag                            # alleen het afgevinkte telt, ⚠/○ als open


# d. verzwakt-blok verschijnt alleen bij missie-impact=verzwakt
def test_d_verzwakt_conditioneel(tmp_path):
    dd_ok, pid_ok, _ = _setup(tmp_path, missie="verzwakt")
    assert "proj_agendeer_verzwakt" in _frag(dd_ok, pid_ok)
    dd_no, pid_no, _ = _setup(tmp_path / "b", missie="versterkt")
    assert "proj_agendeer_verzwakt" not in _frag(dd_no, pid_no)


# e. dangling-rol → waarschuwing zichtbaar
def test_e_dangling_rol_waarschuwing(tmp_path):
    dd, pid, _ = _setup(tmp_path, owner="rol_bestaat_niet_meer_xyz")
    frag = _frag(dd, pid)
    assert "dangling-warn" in frag and "bestaat niet meer" in frag


# f. read-only kijker (guest, geen csrf) ziet weergave zonder bewerk-knoppen
def test_f_readonly_geen_bewerkknoppen(tmp_path):
    dd, pid, codie = _setup(tmp_path, description="de opdracht")
    st = cockpit2._Stores(dd)
    st.projects.add_feed_entry(pid, "een reactie", kind="comment", author_type="human")
    frag = render_project(cockpit2._Stores(dd), pid, csrf_token="", fragment=True)
    assert "de opdracht" in frag and "een reactie" in frag      # inhoud zichtbaar
    for action in ("proj_rename", "proj_status", "proj_feed", "check_toggle", "proj_describe"):
        assert f"value='{action}'" not in frag                  # geen bewerk-acties
    assert "comp-form" not in frag                              # geen composer


# g. pushState: de bord-JS wijzigt de URL bij openen en sluit de modal bij back (popstate)
def test_g_pushstate_popstate_bedrading():
    js = _modal_html("[]")
    assert "history.pushState" in js and "popstate" in js
    assert "openCard(u,push)" in js                             # push-parameter aanwezig
    assert "/project?pid=" in js                                # adresbalk weerspiegelt het project
    assert "history.back()" in js                               # sluiten popt naar de bord-URL


# h. omschrijving-veld weg; opdracht rendert als eerste wall-post
def test_h_opdracht_eerste_post_geen_omschrijving(tmp_path):
    dd, pid, codie = _setup(tmp_path, description="Verbeter de checkout-copy")
    st = cockpit2._Stores(dd)
    st.projects.add_feed_entry(pid, "latere reactie", kind="comment", author_type="human")
    frag = _frag(dd, pid)
    assert "Omschrijving" not in frag                           # het losse omschrijving-blok is weg
    assert "fentry-opdracht" in frag and "Verbeter de checkout-copy" in frag
    # opdracht (oudste, created_at) staat vóór de latere reactie in de wall
    assert frag.index("fentry-opdracht") < frag.index("latere reactie")
