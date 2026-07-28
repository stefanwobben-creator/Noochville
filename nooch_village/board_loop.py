"""Brok 2 — de autonome pull-scheduler van het prikbord-Kanban-dorp.

Pure, deterministische beslislaag (geen LLM): bepaalt WELKE projecten actief worden, hervat, of
naar de mens escaleren. Het echte werk (tekst opleveren) doet work_projects; dit bepaalt het ritme.

De vier sim-gevalideerde guardrails (docs/ONTWERP_prikbord_kanban.md §7):
1. WIP wordt bij ELKE activering getoetst (ook hervatten uit 'waiting').
2. Master-switch: een cluster-lid activeert alleen als de cluster-root 'running' (actief) staat.
3. Fallback: een future-lid met een onbemande eigenaar escaleert naar de mens (blijft niet liggen).
4. Prioritering: hoogste business-value eerst (dan oudste).
"""
from __future__ import annotations

import json
import logging
import os
import time

from nooch_village.business_case import business_value


def _root(projects, p: dict) -> dict | None:
    return projects.get(p.get("cluster") or p["id"])


def _root_active(projects, p: dict) -> bool:
    """Master-switch: een lid (parent != None) mag alleen draaien als zijn cluster-root actief is.
    Standalone/root-projecten (parent is None) zijn mens-gestuurd en worden hier NIET auto-geactiveerd."""
    if not p.get("parent"):
        return False
    root = _root(projects, p)
    return bool(root and root["status"] == "running")


def activate_pulse(projects, available_roles, *, wip: dict | None = None) -> dict:
    """Eén scheduler-puls. `available_roles` = bemenste, beschikbare rol-ids. `wip` = {board, roles}.
    Geeft {activated, resumed, escalated} (lijsten met project-ids)."""
    wip = wip or {"board": 3, "roles": {}}
    board_cap = int(wip.get("board", 3))
    role_cap = dict(wip.get("roles", {}))
    avail = set(available_roles)
    out = {"activated": [], "resumed": [], "escalated": []}

    def board_active() -> int:
        return sum(1 for p in projects.all() if p["status"] == "running")

    def role_active(r: str) -> int:
        return sum(1 for p in projects.all() if p["status"] == "running" and p.get("owner") == r)

    def has_room(r: str) -> bool:
        cap_r = int(role_cap.get(r, board_cap))
        return board_active() < board_cap and role_active(r) < cap_r

    # 1) Hervat geblokkeerde leden waarvan de blokkade (waiting_on) klaar is — WIP-gated.
    for p in sorted([x for x in projects.all() if x["status"] == "blocked"],
                    key=lambda x: x.get("created_at", 0)):
        wo = p.get("waiting_on")
        dep = projects.get(wo) if wo else None
        if dep is not None and dep["status"] == "done" and _root_active(projects, p):
            if has_room(p.get("owner")):
                projects.start(p["id"])
                out["resumed"].append(p["id"])

    # 2) Fallback: future-leden met een onbemande eigenaar → naar de mens (blijven niet liggen).
    for p in [x for x in projects.all() if x["status"] == "future" and _root_active(projects, x)]:
        owner = p.get("owner")
        if owner and owner not in avail:
            projects.block(p["id"], f"mens: rol '{owner}' is onbemand")
            out["escalated"].append(p["id"])

    # 3) Activeer future-leden per WIP, master-switch en prioriteit (business-value, dan oudste).
    for r in available_roles:
        while has_room(r):
            cands = [p for p in projects.all() if p["status"] == "future"
                     and p.get("owner") == r and _root_active(projects, p)]
            if not cands:
                break
            pick = max(cands, key=lambda p: (business_value(p.get("business_case")),
                                             -p.get("created_at", 0)))
            projects.start(pick["id"])
            out["activated"].append(pick["id"])
    return out


# ── de bedrading: van pure beslislaag naar een echte, zichtbare puls ──────────────────────────

def available_role_ids(records, data_dir: str, *, unmanned=None) -> list[str]:
    """De bemenste, beschikbare rol-ids voor `activate_pulse`.

    Bemenst = de rol heeft minstens één *filler* volgens `Assignments.fillers_of` (de gezaghebbende
    bezettings-bron; die telt de toegewezen lijst plus de legacy `held_by`/`persona_id` van het
    record mee — reference, don't copy). Beschikbaar = een levende, niet-gearchiveerde ROL: cirkels
    doen geen uitvoerend werk (harde regel 7) en een onbemande rol (`reconciler.unmanned`) heeft per
    definitie geen uitvoerder.

    Bewuste keuze: mens-bemande rollen tellen HIER wél mee als beschikbaar, anders zou guardrail 3
    hun future-leden wegzetten als "rol is onbemand" — feitelijk onwaar en pure ruis. Alleen een rol
    zonder énige vervuller escaleert. Fail-closed: zonder leesbare bron een lege lijst (dan activeert
    de puls niets, in plaats van blind alles)."""
    if records is None:
        return []
    try:
        from nooch_village import org
        from nooch_village.assignments import Assignments
        asg = Assignments(os.path.join(data_dir, "assignments.json"))
    except Exception:
        return []
    skip = set(unmanned or ())
    out = []
    for rec in records.all():
        if getattr(rec, "archived", False) or org.is_circle(rec) or rec.id in skip:
            continue
        try:
            if asg.fillers_of(rec.id, rec):
                out.append(rec.id)
        except Exception:
            continue
    return sorted(out)


def _feed(ledger, pid: str, text: str) -> None:
    """Eén neutrale audit-regel op de projectkaart. Fail-soft: een kale/oude ledger zonder feed
    mag de puls nooit breken."""
    try:
        ledger.add_feed_entry(pid, text, kind="system", author_type="role", author_id="board_pulse")
    except Exception:
        pass


def run_board_pulse(context, *, records=None, bus=None, unmanned=None,
                    available=None, wip=None) -> dict:
    """Eén bedrade bord-puls: bepaal de bemenste rollen en de WIP-limieten, draai `activate_pulse`,
    en maak de beweging zichtbaar.

    Zichtbaar op drie plekken, want een puls die niemand ziet is geen puls:
      1. per project een systeem-regel in de projectfeed (op de kaart zelf);
      2. `data/board_pulse.jsonl` — de eigen, compacte historie van elke puls (ook lege pulsen,
         zodat "er beweegt niets" een waarneming is en geen stilte);
      3. een `board_pulse_completed`-event op de bus → system_log + de dagelijkse observatie.

    Deterministisch en WIP-gated: herhaald draaien is veilig. Geeft
    {activated, resumed, escalated, available_roles, wip} terug."""
    ledger = getattr(context, "projects", None)
    if ledger is None:
        return {"activated": [], "resumed": [], "escalated": [],
                "available_roles": [], "wip": {}, "skipped": "geen projectgrootboek"}
    data_dir = context.data_dir
    if records is None:
        records = getattr(context, "records", None)
    if wip is None:
        from nooch_village.pinboard import read_wip
        wip = read_wip(data_dir)
    if available is None:
        available = available_role_ids(records, data_dir, unmanned=unmanned)

    out = activate_pulse(ledger, available, wip=wip)

    for pid in out["activated"]:
        _feed(ledger, pid, "🟢 board pulse: activated — WIP had room and the cluster root is active")
    for pid in out["resumed"]:
        _feed(ledger, pid, "▶️ board pulse: resumed — what this project was waiting on is done")
    for pid in out["escalated"]:
        p = ledger.get(pid) or {}
        _feed(ledger, pid, f"🙋 board pulse: escalated to a human — role '{p.get('owner') or '?'}' "
                           f"has no filler, so this member cannot start on its own")

    row = {"at": time.time(), **{k: out[k] for k in ("activated", "resumed", "escalated")},
           "counts": {k: len(out[k]) for k in ("activated", "resumed", "escalated")},
           "available_roles": len(available), "wip": wip}
    try:                                                    # append-only historie, ook bij 0/0/0
        with open(os.path.join(data_dir, "board_pulse.jsonl"), "a") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    logging.getLogger("village.board").info(
        "🔁 bord-puls: %d geactiveerd, %d hervat, %d geëscaleerd (%d bemenste rollen, WIP board=%s)",
        len(out["activated"]), len(out["resumed"]), len(out["escalated"]),
        len(available), wip.get("board"))
    if bus is not None:
        from nooch_village.event_bus import Event
        bus.publish(Event("board_pulse_completed", dict(row), "board_pulse"))
    return {**out, "available_roles": available, "wip": wip}
