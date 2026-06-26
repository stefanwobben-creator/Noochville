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
