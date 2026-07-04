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

def test_mint_id_menstig_per_soort_en_oplopend(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "policy", title="Merkstem")
    b = st.att.add(OWNER, "policy", title="Tweede")
    assert re.fullmatch(r"POL-[A-Z0-9]{1,6}-001", a.id), a.id
    assert b.id.endswith("-002")
    assert st.att.add(OWNER, "note").id.startswith("NOTE-")
    assert st.att.add(OWNER, "tool").id.startswith("TOOL-")
    # niet-artefact soorten houden een opake uuid
    m = st.att.add(OWNER, "metric", title="volume")
    assert re.fullmatch(r"[0-9a-f]{12}", m.id)


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
    # eigen policy op de rol
    st.att.add(OWNER, "policy", title="Eigen")
    # cirkel-policy die erft + een die NIET erft
    st.att.add(CIRCLE, "policy", title="Cirkel-erft", inherit=True)
    st.att.add(CIRCLE, "policy", title="Cirkel-privé", inherit=False)
    # anchor-policy die erft
    st.att.add(ANCHOR, "policy", title="Anchor-erft", inherit=True)

    res = artefacts.own_and_inherited(OWNER, "policy", st.records, st.att)
    assert [a.title for a in res["own"]] == ["Eigen"]
    titles = {i["artefact"].title for i in res["inherited"]}
    assert titles == {"Cirkel-erft", "Anchor-erft"}       # inherit=False valt weg
    origins = {i["artefact"].title: i["origin_id"] for i in res["inherited"]}
    assert origins["Cirkel-erft"] == CIRCLE
    assert origins["Anchor-erft"] == ANCHOR


def test_gearchiveerd_erft_niet(tmp_path):
    st = _stores(tmp_path)
    p = st.att.add(CIRCLE, "policy", title="Cirkel-erft", inherit=True)
    st.att.archive(p.id)
    res = artefacts.own_and_inherited(OWNER, "policy", st.records, st.att)
    assert res["inherited"] == []


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


def test_route_anchor_zonder_governance_ref_faalt_met_403(tmp_path):
    dd = _dd(tmp_path)
    # guest passeert de vervuller-poort, maar de anchor eist een governance_ref
    with pytest.raises(cockpit2.Forbidden) as exc:
        cockpit2.dispatch(dd, "artefact_add",
            {"owner": [ANCHOR], "kind": ["policy"], "title": ["Missie-policy"], "next": ["/"]},
            username="guest")
    assert "governance_ref" in str(exc.value)
    assert cockpit2._Stores(dd).att.list(ANCHOR, "policy") == []
    # mét governance_ref lukt het wél
    nxt, msg = cockpit2.dispatch(dd, "artefact_add",
        {"owner": [ANCHOR], "kind": ["policy"], "title": ["Missie-policy"],
         "governance_ref": ["GOV-2026-07"], "next": ["/"]}, username="guest")
    assert "toegevoegd" in msg
    stored = cockpit2._Stores(dd).att.list(ANCHOR, "policy")
    assert stored and stored[0].versions[-1]["governance_ref"] == "GOV-2026-07"


def test_route_edit_en_archive_via_dispatch(tmp_path):
    dd = _dd(tmp_path)
    a = cockpit2._Stores(dd).att.add(OWNER, "policy", title="v1", body="oud")
    cockpit2.dispatch(dd, "artefact_edit",
        {"aid": [a.id], "body": ["nieuw"], "change_note": ["verscherpt"], "next": ["/"]},
        username="guest")
    cockpit2.dispatch(dd, "artefact_archive", {"aid": [a.id], "next": ["/"]}, username="guest")
    fresh = cockpit2._Stores(dd).att
    assert fresh.list(OWNER, "policy") == []                 # gearchiveerd → uit de lijst
    hist = fresh.get(a.id)
    assert hist.status == "archived"
    assert [v["change_note"] for v in hist.versions] == ["aangemaakt", "verscherpt", "gearchiveerd"]
    actions = [e["action"] for e in _changelog(dd)]
    assert actions == ["edit", "archive"]                    # de directe add ging niet via een route


def test_route_changelog_erfketen_bevat_nazaten(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "artefact_add",
        {"owner": [CIRCLE], "kind": ["policy"], "title": ["Cirkelbreed"],
         "inherit": ["1"], "next": ["/"]}, username="guest")
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
    assert [p["title"] for p in inh] == ["Cirkelbreed"]
    assert inh[0]["origin_path"] == "via Nooch"           # circle name = "Nooch"
    assert inh[0]["editable"] is False


def test_context_anchor_governance_policy_readonly(tmp_path):
    st = _stores(tmp_path)
    # _bootstrap zet een transparantie-policy op de anchor (definition.policies)
    ctx = artefacts.serialize_context(OWNER, st.records, st.att)
    gov = ctx["policies"]["governance"]
    assert gov, "governance-policy van de anchor ontbreekt in de context"
    tp = next(p for p in gov if "transparant" in p["body"].lower())
    assert tp["editable"] is False and tp["mutation_path"] == "governance"
    assert tp["origin_path"] == "via Mother Earth"


def test_context_markdown_valide(tmp_path):
    st = _stores(tmp_path)
    st.att.add(OWNER, "policy", title="Eigen", body="doe dit")
    st.att.add(CIRCLE, "note", title="Cirkel-note", inherit=True)
    md = artefacts.render_context_markdown(
        artefacts.serialize_context(OWNER, st.records, st.att))
    assert md.startswith("# Rol-context: Creator of Shoes")
    for header in ("## Overzicht", "## Policies", "## Notes", "## Tools"):
        assert header in md
    assert "Governance-policies (read-only" in md
    assert "via Nooch" in md                               # geërfde cirkel-note draagt herkomst
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
