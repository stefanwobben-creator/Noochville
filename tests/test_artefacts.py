"""Brok 1 — het artefact-model (note | policy | tool) bovenop de AttachmentStore.

Test de opslaglaag (mens-leesbare id, status/inherit/scope/url, versie-historie, archiveren)
en de domein-logica (`can_write_artefact`, `requires_governance_ref`, `own_and_inherited`).
Gebruikt een echte geboostrapte org zodat de rol-ids en de breadcrumb kloppen.
"""
from __future__ import annotations

import re
import threading

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
