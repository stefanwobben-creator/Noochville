"""wall-outcomes: een wall-comment routeren naar de vijf bestaande uitkomsten (mens-gestuurd).

Dekt: elke uitkomst landt op de juiste store met de juiste velden + herkomst; action-op-DONE
in de juiste volgorde (item eerst, dán reopen); note >4000 → weigering (geen truncatie);
server-side gate; systeem-entry op de wall.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2

_OWNER = "mother_earth__nooch__website_developer"


def _setup(tmp_path, comment="De originele comment-tekst"):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    src_pid = st.projects.create(_OWNER, "Bron-project", "human")
    eid = st.projects.add_feed_entry(src_pid, comment, kind="comment", author_type="human")["id"]
    return dd, src_pid, eid


def _form(**kw):
    return {k: [v] for k, v in kw.items()} | {"next": ["/"]}


def _log(dd, pid):
    return cockpit2._Stores(dd).projects.get(pid).get("log", [])


# ── elke uitkomst landt op de juiste plek ──────────────────────────────────────────

def test_project_lands_op_owner_met_herkomst(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    before = len(cockpit2._Stores(dd).projects.all())
    _, msg = cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="project", pid=src_pid, item=eid, owner=_OWNER,
              content="Nieuw project titel", toelichting="want nodig"), username="guest")
    assert "aangemaakt" in msg
    st = cockpit2._Stores(dd)
    assert len(st.projects.all()) == before + 1
    new = next(p for p in st.projects.all() if p["id"] != src_pid and p.get("scope") == "Nieuw project titel")
    assert new["owner"] == _OWNER
    # herkomst als eerste systeem-entry op het NIEUWE project (bron-pid)
    assert any(e.get("kind") == "system" and src_pid in e.get("text", "") for e in new.get("log", []))
    # systeem-entry op de BRON-wall (audittrail)
    assert any(e.get("kind") == "system" and "project aangemaakt" in e.get("text", "")
               for e in _log(dd, src_pid))


def test_action_checklist_item_met_herkomst(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    tgt = cockpit2._Stores(dd).projects.create(_OWNER, "Doel-project", "human")
    cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="action", pid=src_pid, item=eid, pid_link=tgt,
              content="Doe dit ding", toelichting="omdat het moet"), username="guest")
    p = cockpit2._Stores(dd).projects.get(tgt)
    cl = next(c for c in p.get("checklists", []) if c["title"] == "Acties uit overleg")
    assert any(i["text"] == "Doe dit ding" for i in cl["items"])
    assert any(e.get("kind") == "system" and src_pid in e.get("text", "") for e in p.get("log", []))


def test_note_op_rol_met_herkomst_in_change_note(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="note", pid=src_pid, item=eid, note_role=_OWNER,
              content="Kennis-notitie body", toelichting="vastleggen als kennis"), username="guest")
    notes = cockpit2._Stores(dd).att.list(_OWNER, kind="note")
    assert len(notes) == 1
    assert notes[0].body == "Kennis-notitie body"
    # herkomst reist mee in de change_note van versie 1
    assert src_pid in notes[0].versions[0]["change_note"]


def test_roloverleg_add_role_op_agenda(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="roloverleg", pid=src_pid, item=eid,
              content="Nieuwe rol nodig voor X", toelichting="terugkerend werk"), username="guest")
    items = cockpit2._Stores(dd).agenda.all()
    assert any(it["kind"] == "add_role" and src_pid in it.get("example", "") for it in items)


def test_info_notif_met_bron_in_payload(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    from nooch_village.views.feed import _mentionables
    _, by_name = _mentionables(cockpit2._Stores(dd))
    name = next(nm for nm in by_name)                       # een bestaande mentionable (rol of persoon)
    cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="info", pid=src_pid, item=eid,
              content=f"even melden @{name}", toelichting="fyi"), username="guest")
    notifs = cockpit2._Stores(dd).notif.all()
    assert any(n.get("project_id") == src_pid and n.get("entry_id") == eid for n in notifs)


# ── harde rand 1: action op DONE — item eerst, dán reopen ───────────────────────────

def test_action_op_done_item_voor_reopen(tmp_path, monkeypatch):
    dd, src_pid, eid = _setup(tmp_path)
    st0 = cockpit2._Stores(dd)
    tgt = st0.projects.create(_OWNER, "Doel-af", "human")
    st0.projects.complete(tgt)
    assert cockpit2._Stores(dd).projects.get(tgt)["status"] == "done"

    from nooch_village.projects import ProjectLedger
    order = []
    orig_check, orig_reopen = ProjectLedger.check_add, ProjectLedger.reopen

    def spy_check(self, *a, **k):
        order.append("check_add"); return orig_check(self, *a, **k)

    def spy_reopen(self, *a, **k):
        order.append("reopen"); return orig_reopen(self, *a, **k)

    monkeypatch.setattr(ProjectLedger, "check_add", spy_check)
    monkeypatch.setattr(ProjectLedger, "reopen", spy_reopen)
    cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="action", pid=src_pid, item=eid, pid_link=tgt,
              content="Nieuw actie-item", toelichting="volgorde-bewijs"), username="guest")

    # VOLGORDE: het checklist-item wordt toegevoegd VÓÓR reopen (nooit andersom).
    assert "check_add" in order and "reopen" in order
    assert order.index("check_add") < order.index("reopen")
    # eindstaat: project weer ACTIEF, outcome gewist, en de checklist is INCOMPLEET (het nieuwe
    # item is open) → een puls voltooit 'm niet vals met een project_completed-event.
    p = cockpit2._Stores(dd).projects.get(tgt)
    assert p["status"] == "running" and p["outcome"] is None
    items = [i for c in p.get("checklists", []) for i in c["items"]]
    assert any(i["text"] == "Nieuw actie-item" and not i["done"] for i in items)


# ── harde rand note: >4000 → weigering, geen truncatie ──────────────────────────────

def test_note_te_lang_weigert_zonder_truncatie(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    body = "x" * 4001
    _, msg = cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="note", pid=src_pid, item=eid, note_role=_OWNER,
              content=body, toelichting="te lang"), username="guest")
    assert "te lang" in msg and "4000" in msg
    # geen note aangemaakt (geen stille afkap naar 4000)
    assert cockpit2._Stores(dd).att.list(_OWNER, kind="note") == []


# ── server-side gate ────────────────────────────────────────────────────────────────

def test_gate_project_op_andermans_rol_geweigerd(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Buitenstaander", "buiten@x.nl")          # herkend, maar vult _OWNER niet en is geen Circle Lead
    before = len(cockpit2._Stores(dd).projects.all())
    _, msg = cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="project", pid=src_pid, item=eid, owner=_OWNER,
              content="Sneak project", toelichting="mag niet"), username="buiten@x.nl")
    assert "Geen toegang" in msg
    assert len(cockpit2._Stores(dd).projects.all()) == before   # niets aangemaakt


# ── herkomst verplicht ──────────────────────────────────────────────────────────────

def test_herkomst_verplicht_onbekende_bron(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    _, msg = cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="note", pid=src_pid, item="bestaat-niet", note_role=_OWNER,
              content="x", toelichting="y"), username="guest")
    assert "herkomst" in msg
    assert cockpit2._Stores(dd).att.list(_OWNER, kind="note") == []


# ── systeem-entry op de wall ────────────────────────────────────────────────────────

def test_systeem_entry_op_de_wall(tmp_path):
    dd, src_pid, eid = _setup(tmp_path)
    cockpit2.dispatch(dd, "wall_outcome",
        _form(otype="note", pid=src_pid, item=eid, note_role=_OWNER, content="body"), username="guest")
    sys_entries = [e for e in _log(dd, src_pid) if e.get("kind") == "system"]
    assert any("note aangemaakt" in e["text"] for e in sys_entries)
