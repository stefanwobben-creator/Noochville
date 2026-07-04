"""Brok 1 — het artefact-model (note | policy | tool) bovenop de AttachmentStore.

Test de opslaglaag (mens-leesbare id, status/inherit/scope/url, versie-historie, archiveren)
en de domein-logica (`can_write_artefact`, `requires_governance_ref`, `own_and_inherited`).
Gebruikt een echte geboostrapte org zodat de rol-ids en de breadcrumb kloppen.
"""
from __future__ import annotations

import json
import os
import re
import threading

import pytest

from nooch_village import cockpit2
from nooch_village import artefacts
from nooch_village.attachments import AttachmentStore

ANCHOR = "mother_earth"
CIRCLE = "mother_earth__nooch"
LEAD_ROLE = "mother_earth__nooch__circle_lead"
OWNER = "mother_earth__nooch__creator_of_shoes"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


# ── opslaglaag: id-minting ───────────────────────────────────────────────────

def test_mint_id_policy_domein_note_tool(tmp_path):
    # verse store (geen bootstrap-migratie) zodat de nummering deterministisch bij 001 begint
    store = AttachmentStore(str(tmp_path / "att.json"))
    # policy → {DOMEINSLUG}-{NNN}
    assert store.add(OWNER, "policy", title="a", domain="Mission").id == "MISSION-001"
    assert store.add(OWNER, "policy", title="b", domain="Mission").id == "MISSION-002"
    # policy zonder domein → terugval op rol-slug
    assert re.fullmatch(r"[A-Z0-9]{1,6}-001", store.add(OWNER, "policy").id)
    # note/tool houden {TYPE}-{ROLSLUG}
    assert store.add(OWNER, "note").id.startswith("NOTE-")
    assert store.add(OWNER, "tool").id.startswith("TOOL-")
    # niet-artefact soorten houden een opake uuid
    assert re.fullmatch(r"[0-9a-f]{12}", store.add(OWNER, "metric", title="volume").id)


# ── opslaglaag: versie-historie ─────────────────────────────────────────────

def test_add_legt_versie_1_vast(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "policy", body="v1-tekst", actor_id="alice", actor_type="person")
    assert len(a.versions) == 1
    v = a.versions[0]
    assert v["version_nr"] == 1 and v["body_snapshot"] == "v1-tekst"
    assert v["actor_id"] == "alice" and v["actor_type"] == "human"


def test_update_appendt_versie_met_snapshot(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "policy", body="oud")
    b = st.att.update(a.id, body="nieuw", actor_id="ai_bob", actor_type="persona",
                      change_note="verscherpt")
    assert [v["version_nr"] for v in b.versions] == [1, 2]
    assert b.versions[-1]["body_snapshot"] == "nieuw"
    assert b.versions[-1]["actor_type"] == "ai"          # persona → ai
    assert b.versions[-1]["change_note"] == "verscherpt"
    # oude snapshot blijft leesbaar
    assert b.versions[0]["body_snapshot"] == "oud"


def test_archiveren_verbergt_maar_behoudt_historie(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "policy", body="x")
    st.att.update(a.id, body="y")
    arch = st.att.archive(a.id, actor_id="alice", actor_type="person")
    assert arch.status == "archived"
    # uit de gewone lijst, maar historie + record blijven bestaan
    assert a.id not in [x.id for x in st.att.list(OWNER, "policy")]
    assert a.id in [x.id for x in st.att.list(OWNER, "policy", include_archived=True)]
    assert st.att.get(a.id) is not None
    assert st.att.get(a.id).versions[-1]["change_note"] == "gearchiveerd"


# ── domein: autorisatie ─────────────────────────────────────────────────────

def test_filler_mag_schrijven_niet_filler_niet(tmp_path):
    st = _stores(tmp_path)
    st.assign.assign(OWNER, "person", "alice")
    assert artefacts.can_write_artefact("person", "alice", OWNER, st.records, st.assign)
    assert not artefacts.can_write_artefact("person", "stranger_zzz", OWNER, st.records, st.assign)


def test_ai_vervuller_mag_exact_hetzelfde_als_mens(tmp_path):
    st = _stores(tmp_path)
    st.assign.assign(OWNER, "person", "alice")
    st.assign.assign(OWNER, "persona", "ai_bob")
    mens = artefacts.can_write_artefact("person", "alice", OWNER, st.records, st.assign)
    ai = artefacts.can_write_artefact("persona", "ai_bob", OWNER, st.records, st.assign)
    assert mens is True and ai is True
    # en een niet-toegewezen persona mag niet
    assert not artefacts.can_write_artefact("persona", "ai_ghost", OWNER, st.records, st.assign)


def test_circle_lead_mag_schrijven_op_rol_in_cirkel(tmp_path):
    st = _stores(tmp_path)
    st.assign.assign(LEAD_ROLE, "person", "lead_carol")
    assert artefacts.can_write_artefact("person", "lead_carol", OWNER, st.records, st.assign)


def test_anchor_vereist_governance_ref(tmp_path):
    st = _stores(tmp_path)
    assert artefacts.requires_governance_ref(ANCHOR, st.records) is True
    assert artefacts.requires_governance_ref(OWNER, st.records) is False


# ── domein: erf-query ───────────────────────────────────────────────────────

def test_own_and_inherited_respecteert_inherit_en_herkomst(tmp_path):
    st = _stores(tmp_path)
    st.att.add(OWNER, "policy", title="Eigen")
    st.att.add(CIRCLE, "policy", title="Cirkel-erft", inherit=True)
    st.att.add(CIRCLE, "policy", title="Cirkel-privé", inherit=False)

    res = artefacts.own_and_inherited(OWNER, "policy", st.records, st.att)
    assert [a.title for a in res["own"]] == ["Eigen"]
    titles = {i["artefact"].title for i in res["inherited"]}
    assert titles == {"Cirkel-erft"}          # inherit=False valt weg; geen voorgebakken anchor-policies
    origins = {i["artefact"].title: i["origin_id"] for i in res["inherited"]}
    assert origins["Cirkel-erft"] == CIRCLE


def test_gearchiveerd_erft_niet(tmp_path):
    st = _stores(tmp_path)
    p = st.att.add(CIRCLE, "policy", title="Cirkel-erft", inherit=True)
    st.att.archive(p.id)
    res = artefacts.own_and_inherited(OWNER, "policy", st.records, st.att)
    assert "Cirkel-erft" not in {i["artefact"].title for i in res["inherited"]}


# ── migratie ────────────────────────────────────────────────────────────────

def test_migrate_tilt_legacy_tool_note_en_is_idempotent(tmp_path):
    path = str(tmp_path / "att.json")
    # legacy tool-note zoals hij op schijf zou staan (vóór het artefact-model)
    store = AttachmentStore(path)
    store._items["leg1"] = {
        "id": "leg1", "anchor": OWNER, "kind": "note", "subtype": "tool",
        "title": "Serpstat", "body": "https://serpstat", "meta": {},
        "created_at": 1.0, "updated_at": 1.0,
    }
    store._save()                       # persisteren; migrate() her-leest vers van schijf
    changed = store.migrate()
    assert changed == 1
    d = store._items["leg1"]
    assert d["kind"] == "tool" and d["subtype"] == ""
    assert d["status"] == "active" and d["inherit"] is True
    assert d["scope"] == "" and d["url"] == ""
    assert len(d["versions"]) == 1 and d["versions"][0]["body_snapshot"] == "https://serpstat"
    # tweede keer draaien wijzigt niets meer
    assert store.migrate() == 0


# ── concurrency: geen verloren edits, geen dubbele id ───────────────────────

def test_gelijktijdige_adds_uniek_en_niets_verloren(tmp_path):
    """Bootst de cockpit na: elke 'request' bouwt een verse store op hetzelfde pad en add't
    tegelijk. Zonder slot overleeft er maar één (lost update + NNN-botsing); mét slot moeten
    álle adds bewaard blijven met unieke, oplopende ids."""
    path = str(tmp_path / "att.json")
    N = 25
    barrier = threading.Barrier(N)

    def worker():
        barrier.wait()                               # start allemaal tegelijk → maximale race
        AttachmentStore(path).add(OWNER, "policy", title="p")

    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ids = list(AttachmentStore(path)._items.keys())
    assert len(ids) == N, f"lost update: {N - len(ids)} adds verdwenen"
    assert len(set(ids)) == N, "dubbele id (NNN-botsing)"
    nrs = sorted(int(i.rsplit("-", 1)[1]) for i in ids)
    assert nrs == list(range(1, N + 1)), f"NNN niet aaneensluitend: {nrs}"


def test_gelijktijdige_updates_verliezen_geen_versie(tmp_path):
    """Twee gelijktijdige updates op hetzelfde artefact: beide versie-snapshots moeten
    bewaard blijven (geen lost update op de historie)."""
    path = str(tmp_path / "att.json")
    a = AttachmentStore(path).add(OWNER, "policy", body="v1")
    barrier = threading.Barrier(2)

    def worker(tag):
        barrier.wait()
        AttachmentStore(path).update(a.id, body=f"body-{tag}", change_note=f"edit-{tag}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    versions = AttachmentStore(path).get(a.id).versions
    assert [v["version_nr"] for v in versions] == [1, 2, 3], "versie-historie kwijt onder concurrency"


# ── brok 2: write-routes in dispatch + AUTHZ ────────────────────────────────

def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _give_domain(dd, role_id, domain):
    """Simuleer een governance-domein-toewijzing: geef de rol een écht domein zodat de eigenaar er
    daarna een policy op mag maken (de juiste route). Persisteert naar de records."""
    st = cockpit2._Stores(dd)
    rec = st.records.get(role_id)
    if domain not in rec.definition.domains:
        rec.definition.domains.append(domain)
        st.records.put(rec)


def _changelog(dd):
    path = os.path.join(dd, "artefact_changelog.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_route_vervuller_mag_toevoegen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    alice = st.people.add("Alice", "alice@nooch.earth")
    st.assign.assign(OWNER, "person", alice.id)              # persisteren op schijf
    _give_domain(dd, OWNER, "Merkstem")                      # governance wijst eerst het domein toe
    nxt, msg = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [OWNER], "kind": ["policy"], "title": ["Merkstem"],
         "body": ["Altijd 'burger', nooit 'consument'."], "next": ["/"]},
        username="alice@nooch.earth")
    assert "toegevoegd" in msg
    stored = cockpit2._Stores(dd).att.list(OWNER, "policy")
    assert [a.title for a in stored] == ["Merkstem"]
    # changelog-entry met timestamp + erfketen weggeschreven
    log = _changelog(dd)
    assert len(log) == 1 and log[0]["action"] == "add" and log[0]["ts"] > 0
    assert OWNER in log[0]["erfketen"]


def test_route_niet_vervuller_krijgt_403(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Bob", "bob@nooch.earth")                  # bestaat, maar vervult OWNER niet
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "artefact_add",
            {"owner": [OWNER], "kind": ["policy"], "title": ["Sluipweg"], "next": ["/"]},
            username="bob@nooch.earth")
    assert cockpit2._Stores(dd).att.list(OWNER, "policy") == []   # niets geschreven


def test_route_persona_gelijk_aan_person(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    alice = st.people.add("Alice", "alice@nooch.earth")
    st.assign.assign(OWNER, "person", alice.id)
    st.assign.assign(OWNER, "persona", "ai_nooch")
    st2 = cockpit2._Stores(dd)
    # de poort die de route gebruikt, staat de mens toe ...
    assert cockpit2._artefact_gate(OWNER, "alice@nooch.earth", st2) is None
    # ... en can_write_artefact (de AI-weg) geeft voor de persona exact hetzelfde oordeel
    assert artefacts.can_write_artefact("persona", "ai_nooch", OWNER, st2.records, st2.assign)
    assert artefacts.can_write_artefact("person", alice.id, OWNER, st2.records, st2.assign)


def test_route_governance_ref_afgeleid_uit_domein(tmp_path):
    # Geen govref-invoerveld: hij wordt afgeleid uit het écht toegewezen domein van de rol.
    dd = _dd(tmp_path)
    _give_domain(dd, CIRCLE, "Money")                        # governance wijst domein toe
    nxt, msg = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["Geld-regel"], "next": ["/"]},
        username="guest")
    assert "toegevoegd" in msg
    added = [a for a in cockpit2._Stores(dd).att.list(CIRCLE, "policy") if a.title == "Geld-regel"]
    assert added and added[0].domain == "Money"
    assert added[0].versions[-1]["governance_ref"] == "domain:Money"   # afgeleid uit het domein


def test_route_edit_en_archive_via_dispatch(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "policy", title="v1", body="oud")
    cockpit2.dispatch(dd, "artefact_edit",
        {"aid": [a.id], "body": ["nieuw"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "artefact_archive", {"aid": [a.id], "next": ["/"]}, username="guest")
    fresh = cockpit2._Stores(dd).att
    assert fresh.list(OWNER, "policy") == []                 # gearchiveerd → uit de lijst
    hist = fresh.get(a.id)
    assert hist.status == "archived"
    # change_note is nu automatisch (geen invoerveld meer)
    assert [v["change_note"] for v in hist.versions] == ["aangemaakt", "bewerkt", "gearchiveerd"]
    actions = [e["action"] for e in _changelog(dd)]
    assert actions == ["edit", "archive"]                    # de directe add ging niet via een route


def test_route_changelog_erfketen_bevat_nazaten(tmp_path):
    dd = _dd(tmp_path)
    _give_domain(dd, CIRCLE, "Money")
    cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["Cirkelbreed"], "next": ["/"]},
        username="guest")
    chain = _changelog(dd)[0]["erfketen"]
    assert CIRCLE in chain and OWNER in chain               # de rol erft → staat in de keten


def test_changelog_append_serialiseert_onder_slot(tmp_path):
    """Gelijktijdige changelog-appends mogen elkaar niet overschrijven of half schrijven: elke
    regel moet geldige JSON zijn en alle N entries moeten aanwezig zijn (onder util.file_lock)."""
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "policy", title="p")
    records = cockpit2._Stores(dd).records
    N = 30
    barrier = threading.Barrier(N)

    def worker(i):
        barrier.wait()
        artefacts.log_change(dd, action="edit", artefact=a, records=records,
                             actor_id=f"actor-{i}", actor_type="person")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log = _changelog(dd)                                    # parse't elke regel als JSON
    assert len(log) == N, f"changelog verloor regels: {len(log)}/{N}"
    assert len({e["actor_id"] for e in log}) == N           # geen overschreven/gemergde regels


# ── brok 3: /context serialisatie (json + markdown) ─────────────────────────

def test_context_bevat_alle_vier_blokken(tmp_path):
    st = _stores(tmp_path)
    st.att.add(OWNER, "policy", title="Eigen policy")
    st.att.add(OWNER, "note", title="Eigen note")
    st.att.add(OWNER, "tool", title="Figma", url="https://figma.com")
    ctx = artefacts.serialize_context(OWNER, st.records, st.att)
    assert set(ctx) == {"role", "policies", "notes", "tools"}
    assert ctx["role"]["purpose"] and "accountabilities" in ctx["role"] and "domains" in ctx["role"]
    assert [p["title"] for p in ctx["policies"]["own"]] == ["Eigen policy"]
    assert [n["title"] for n in ctx["notes"]["own"]] == ["Eigen note"]
    assert ctx["tools"]["own"][0]["url"] == "https://figma.com"


def test_context_geerfd_toont_herkomstpad(tmp_path):
    st = _stores(tmp_path)
    st.att.add(CIRCLE, "policy", title="Cirkelbreed", inherit=True)
    ctx = artefacts.serialize_context(OWNER, st.records, st.att)
    inh = ctx["policies"]["inherited"]
    cirkelbreed = [p for p in inh if p["title"] == "Cirkelbreed"]
    assert cirkelbreed and cirkelbreed[0]["origin_path"] == "via Nooch"   # circle name = "Nooch"
    assert cirkelbreed[0]["editable"] is False


def test_context_policies_dragen_domein_geen_governance_blok(tmp_path):
    # Policies zijn domein-gescopeerde artefacten (geen apart governance-blok, geen voorbak).
    st = _stores(tmp_path)
    # simuleer: cirkel bezit domein Money, eigenaar maakt er een policy op
    n = st.records.get(CIRCLE); n.definition.domains.append("Money"); st.records.put(n)
    st.att.add(CIRCLE, "policy", title="Geld-regel", domain="Money", inherit=True)
    ctx = artefacts.serialize_context(OWNER, st.records, st.att)
    assert "governance" not in ctx["policies"]            # geen los governance-blok meer
    inh = ctx["policies"]["inherited"]
    geld = next(p for p in inh if p.get("domain") == "Money")
    assert geld["editable"] is False and geld["id"].startswith("MONEY-")


def test_context_markdown_valide(tmp_path):
    st = _stores(tmp_path)
    st.att.add(OWNER, "policy", title="Eigen", body="doe dit")
    st.att.add(CIRCLE, "note", title="Cirkel-note", inherit=True)
    md = artefacts.render_context_markdown(
        artefacts.serialize_context(OWNER, st.records, st.att))
    assert md.startswith("# Rol-context: Creator of Shoes")
    for header in ("## Overzicht", "## Policies", "## Notes", "## Tools"):
        assert header in md
    assert "Alle policies zijn governance-eigendom" in md   # nieuwe policy-kop
    assert "via Nooch" in md                                # geërfde cirkel-note draagt herkomst
    assert md.endswith("\n")


def test_context_endpoint_json_en_markdown_en_404(tmp_path):
    st = _stores(tmp_path)
    status, ctype, body = cockpit2.role_context(st, OWNER, "json")
    assert status == 200 and "application/json" in ctype
    assert set(json.loads(body)) == {"role", "policies", "notes", "tools"}
    status, ctype, body = cockpit2.role_context(st, OWNER, "markdown")
    assert status == 200 and "text/markdown" in ctype and body.startswith("# Rol-context")
    status, _, _ = cockpit2.role_context(st, "bestaat_niet", "json")
    assert status == 404


# ── brok UI: Notes/Policies/Tools tabs ──────────────────────────────────────

def _give_role_domain(st, role_id, domain):
    rec = st.records.get(role_id)
    if domain not in rec.definition.domains:
        rec.definition.domains.append(domain)
        st.records.put(rec)


def test_ui_vervuller_ziet_editknop_niet_vervuller_niet(tmp_path):
    st = _stores(tmp_path)
    st.people.add("Alice", "alice@nooch.earth")
    st.assign.assign(OWNER, "person", st.people.by_email("alice@nooch.earth").id)
    st.people.add("Bob", "bob@nooch.earth")                 # bestaat, vervult OWNER niet
    _give_role_domain(st, OWNER, "Merkstem")                # governance wijst domein toe → policy mogelijk
    st.att.add(OWNER, "policy", title="Merkstem-regel", domain="Merkstem")

    filler = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="alice@nooch.earth")
    assert "artefact_add" in filler and "artefact_edit" in filler   # add- + edit-formulier zichtbaar
    assert "Merkstem-regel" in filler

    outsider = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="bob@nooch.earth")
    assert "Merkstem-regel" in outsider                      # ziet de policy wél (read)
    assert "artefact_add" not in outsider and "artefact_edit" not in outsider   # maar geen edit-knop


def test_ui_geerfd_readonly_met_herkomst(tmp_path):
    st = _stores(tmp_path)
    st.att.add(CIRCLE, "policy", title="Cirkelbreed", inherit=True)
    html = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    assert "Geldend hier" in html and "Cirkelbreed" in html
    assert "via Nooch" in html
    assert f"/node?id={CIRCLE}&tab=policies" in html         # herkomst-badge springt naar bron-rol


def test_ui_policy_form_projecten_patroon_titel_body_domein(tmp_path):
    # Projecten-patroon (qadd-form + att-lbl + editor-toolbar); alleen titel + body + domein.
    st = _stores(tmp_path)
    _give_role_domain(st, OWNER, "Merkstem")
    html = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    for weg in ("governance_ref", "name='scope'", "name='inherit'", "name='change_note'"):
        assert weg not in html
    assert "class='qadd-form'" in html and "att-lbl" in html and "class='editor'" in html
    assert "name='title'" in html and "name='body'" in html
    assert "Domein" in html and "name='domain'" in html


def test_ui_artefact_lijst_gebruikt_card_patroon(tmp_path):
    # Lijst-items volgen het projecten-kaart-patroon (.card / .ptitle), geen bare <li>.
    st = _stores(tmp_path)
    st.att.add(CIRCLE, "note", title="Cirkel-note", inherit=True)   # note: geen domein nodig
    html = cockpit2.render_node(st, CIRCLE, "notes", csrf_token="tok", username="guest")
    assert "class='card'" in html and "ptitle" in html
    assert "class='qadd-form'" in html and "class='editor'" in html   # add-form ook in het patroon


def test_ui_policy_geen_domein_toont_melding_geen_form(tmp_path):
    st = _stores(tmp_path)                                   # OWNER heeft geen domein
    html = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    assert "nog geen domein" in html
    assert "value='artefact_add'" not in html               # geen add-form


def test_ui_policy_1_domein_vaste_regel_2_domeinen_select(tmp_path):
    st = _stores(tmp_path)
    _give_role_domain(st, OWNER, "Merkstem")
    one = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    assert "<input type='hidden' name='domain'" in one and "<select name='domain'>" not in one
    _give_role_domain(st, OWNER, "Toon")                    # nu 2 domeinen → select
    two = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    assert "<select name='domain'>" in two and "Toon" in two


def test_route_policy_domein_server_side_gevalideerd(tmp_path):
    dd = _dd(tmp_path)
    _give_domain(dd, CIRCLE, "Money")
    _give_domain(dd, CIRCLE, "Decision Making")             # 2 domeinen → keuze verplicht + gevalideerd
    bad = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["X"], "domain": ["Verzonnen"], "next": ["/"]},
        username="guest")[1]
    assert "kies een domein" in bad
    assert cockpit2._Stores(dd).att.list(CIRCLE, "policy") == []
    ok = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["Geld-regel"], "domain": ["Money"], "next": ["/"]},
        username="guest")[1]
    assert "toegevoegd" in ok
    assert cockpit2._Stores(dd).att.list(CIRCLE, "policy")[0].domain == "Money"


def test_ui_tools_tab_toont_url_en_icon(tmp_path):
    st = _stores(tmp_path)
    st.att.add(OWNER, "tool", title="Serpstat", url="https://serpstat.com")
    html = cockpit2.render_node(st, OWNER, "tools", csrf_token="tok", username="guest")
    assert "Tools" in html and "https://serpstat.com" in html and "🛠" in html
    # de tab zit in de tabbar
    assert "tab=tools" in cockpit2.render_node(st, OWNER, "overview", csrf_token="tok", username="guest")


def test_ui_policies_governance_eigendom_kop_geen_slotje(tmp_path):
    # Eén regel "governance-eigendom" boven de lijst; geen slotje/badge per item.
    st = _stores(tmp_path)
    # cirkel bezit domein Money, eigenaar maakt er een policy op → subrol erft 'm
    n = st.records.get(CIRCLE); n.definition.domains.append("Money"); st.records.put(n)
    st.att.add(CIRCLE, "policy", title="Geld-regel", domain="Money", inherit=True)
    html = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    assert "Alle policies hieronder zijn governance-eigendom" in html
    assert "🔒" not in html
    assert "Geld-regel" in html and "via Nooch" in html   # geërfd met domein-id + herkomst


def test_ui_versiehistorie_uitklapper(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "policy", title="P", body="v1")
    st.att.update(a.id, body="v2", change_note="verscherpt")
    html = cockpit2.render_node(st, OWNER, "policies", csrf_token="tok", username="guest")
    assert "historie (2)" in html and "verscherpt" in html


# ── brok 5: seen-marker (opdracht-test #8) ──────────────────────────────────

def test_seen_marker_policywijziging_zet_geel_in_keten(tmp_path):
    """Opdracht-test #8: een wijziging aan een active policy zet de geel-markering bij de rollen
    in de erfketen; het openen van de tab (mark) haalt hem weer weg."""
    import time
    from nooch_village import artefact_seen
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    user = "alice@nooch.earth"
    st.people.add("Alice", user)
    st.seen.mark(user, OWNER, "policies")               # Alice heeft de tab net gezien
    _give_domain(dd, CIRCLE, "Money")
    time.sleep(0.02)
    # policy toegevoegd op de cirkel; OWNER zit in de erfketen (inherit=True)
    cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["Nieuw beleid"], "next": ["/"]},
        username="guest")
    cl = artefacts.read_changelog(dd)
    assert "policies" in artefact_seen.unseen_tabs(cockpit2._Stores(dd).seen, cl, user, OWNER)
    # tab openen → last_seen bijgewerkt → markering weg
    cockpit2._Stores(dd).seen.mark(user, OWNER, "policies")
    assert "policies" not in artefact_seen.unseen_tabs(cockpit2._Stores(dd).seen, cl, user, OWNER)


def test_seen_marker_zichtbaar_in_tabbar_en_niet_voor_guest(tmp_path):
    import time
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    user = "alice@nooch.earth"
    st.people.add("Alice", user)
    st.seen.mark(user, OWNER, "policies")
    _give_domain(dd, CIRCLE, "Money")
    time.sleep(0.02)
    cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["X"], "next": ["/"]},
        username="guest")
    marker = "<span class='c2-unseen'"                  # het element, niet de CSS-regel
    # Alice opent een ANDERE tab → policies-tab draagt de unseen-markering
    html = cockpit2.render_node(cockpit2._Stores(dd), OWNER, "notes", csrf_token="tok", username=user)
    assert marker in html
    # guest heeft geen persistente identiteit → geen markering
    guest_html = cockpit2.render_node(cockpit2._Stores(dd), OWNER, "notes", csrf_token="tok", username="guest")
    assert marker not in guest_html


# ── terugdraai fase 2: systeem bakt geen domein/policy voor ──────────────────

def test_bootstrap_bakt_geen_policy_in(tmp_path):
    """Uitgangspunt: het systeem start leeg. Domeinen worden via governance aan een rol toegewezen;
    de eigenaar-rol maakt zélf de policy via het artefact-mechanisme. Deze test faalt zodra seed/
    bootstrap opnieuw een policy of het voorbak-mechanisme (migrate_anchor_policies) introduceert."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pols = [a.id for r in st.records.all() for a in st.att.list(r.id, "policy", include_archived=True)]
    assert pols == [], f"bootstrap bakte policies voor: {pols}"
    # het fase-2 voorbak-mechanisme mag niet terugkeren
    assert not hasattr(artefacts, "migrate_anchor_policies"), "migrate_anchor_policies is terug"
    assert not hasattr(artefacts, "_ANCHOR_POLICIES_FASE2"), "_ANCHOR_POLICIES_FASE2 is terug"
    assert st.records.root().definition.policies == []      # geen string-policies geseeded


def test_policy_alleen_op_governance_domein(tmp_path):
    """Een policy kan alleen op een rol die het domein écht via governance bezit; geen domein →
    nette weigering, geen pseudo-domein-fallback."""
    dd = _dd(tmp_path)
    # OWNER (creator_of_shoes) heeft géén governance-domein → policy geweigerd
    nxt, msg = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [OWNER], "kind": ["policy"], "title": ["X"], "next": ["/"]}, username="guest")
    assert "geen domein" in msg
    assert cockpit2._Stores(dd).att.list(OWNER, "policy") == []
    # ná een governance-domein-toewijzing mag het wél, met dat domein
    _give_domain(dd, CIRCLE, "Money")
    nxt, msg = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["Geld-regel"], "next": ["/"]}, username="guest")
    assert "toegevoegd" in msg
    p = cockpit2._Stores(dd).att.list(CIRCLE, "policy")[0]
    assert p.domain == "Money"                              # het écht toegewezen domein


# ── rendering: markdown in de artefact-body ──────────────────────────────────
def test_artefact_body_rendert_markdown(tmp_path):
    """De body-opmaak (uit een import/textarea, met CRLF) rendert als markdown: **vet**, '- '
    lijstjes en regelafbrekingen — niet als platte tekst met letterlijke sterretjes/muur."""
    from nooch_village.views import overview
    st = _stores(tmp_path)
    body = "Intro-zin.\r\n\r\n**Playful Rebellion**\r\nDe attitude.\r\nDo\r\n- We grow shoes.\r\n- Weird flex."
    a = st.att.add(OWNER, "note", title="Tone of Voice", body=body,
                   actor_id="alice", actor_type="person")
    html = overview._artefact_own_card(a, "", False)
    assert "<strong>Playful Rebellion</strong>" in html      # **vet** gerenderd
    assert "**" not in html                                  # geen letterlijke sterretjes meer
    assert "<li>We grow shoes." in html and "<ul" in html    # '- ' → lijst
    assert "<br>" in html                                    # newlines behouden
    assert "\r" not in html                                  # geen losse CRLF-resten
