"""Brok 4 — discovery-rollen bedraad op het prikbord-Kanban-bord.

Discovery (zoekwoorden vinden) is geen los project maar een STAANDE ACCOUNTABILITY, uitgevoerd in
afgebakende projecten: één seed → één deliverable, waarvan de uitkomst automatisch de Librarian-
review in gaat. De brok-2 scheduler (board_loop) bepaalt het tempo (WIP + master-switch); deze laag
maakt de projecten, oogst de uitkomsten en routeert ze door.

Rolverdeling (docs/ONTWERP_prikbord_kanban.md §8):
- Harry_Hemp      → seed words (lange-termijn-trendblik)
- Trends          → related zoekwoorden per seed; spaced repetition over de seeds;
                    seeds op → verzoek aan Harry (briefje), ondertussen oudste seed opnieuw
- Concurrent_scout→ zoekwoorden van concurrenten
- Librarian       → reviewt elke binnenkomende uitkomst (gebeurt via de route-injectie)

PUUR & MENS-GATED: het echte term-vinden (`do_discovery`) en de review-routering (`route_review`)
worden geïnjecteerd. Deze laag schrijft GEEN nieuwe code, start GEEN threads en roept GEEN externe
API's aan buiten de geïnjecteerde functies — identiek aan de geboren-versus-bemenst-grens.
"""
from __future__ import annotations

from nooch_village.board_loop import activate_pulse

DISCOVERY_ROOT = "discovery"          # vaste cluster-root (master-switch voor alle discovery)
# Canonieke owner-keys = de echte rol-ids (zodat het bord de juiste eigenaar toont).
TAG = {"harry_hemp": "seed", "trends": "related", "concurrent_scout": "competitor"}


def ensure_root(projects) -> str:
    """Zorg dat de discovery-cluster-root bestaat (de master-switch). De mens zet hem op
    'running' om alle discovery te laten lopen; standaard 'future' (gepauzeerd). Idempotent."""
    root = projects.get(DISCOVERY_ROOT)
    if root is None:
        # Vaste id zodat de root herkenbaar en idempotent is (geen dubbele roots).
        projects.create("the_source", "Discovery — zoekwoorden vinden (staande accountability)",
                        "human", status="future")
        # create() genereert een random id; we willen een vaste root-id. Schrijf 'm expliciet.
        last = max(projects.all(), key=lambda p: p.get("created_at", 0))
        projects._projects.pop(last["id"], None)
        last["id"] = DISCOVERY_ROOT
        last["cluster"] = DISCOVERY_ROOT
        projects._projects[DISCOVERY_ROOT] = last
        projects._save()
    return DISCOVERY_ROOT


def seeds_from_library(library) -> list[str]:
    """Approved 'volg'-woorden zijn de seeds voor de radar."""
    out = []
    for w, e in (library.all() or {}).items():
        if e.get("status") == "approved" and \
                (e.get("function") == "volg" or library.function_of(w) == "volg"):
            out.append(w)
    return sorted(out)


def _open_scope(projects, owner: str, scope: str) -> bool:
    """Heeft deze rol al een niet-afgerond discovery-project met deze scope? (dedup)."""
    sl = scope.strip().lower()
    return any(p.get("owner") == owner and str(p.get("scope", "")).strip().lower() == sl
               and p.get("status") != "done" for p in projects.all())


def make_discovery_project(projects, owner: str, scope: str, *, goes_to: str = "librarian") -> str | None:
    """Maak één afgebakend discovery-project (future) onder de root. Dedup op (owner, scope).
    Geeft het nieuwe pid, of None als het al bestond."""
    if _open_scope(projects, owner, scope):
        return None
    ensure_root(projects)
    pid = projects.create(
        owner, scope, "human", status="future", origin="discovery",
        dod_outcome=f"Lijst kandidaat-zoekwoorden uit: {scope}",
        done_when="≥1 nieuwe term met onderbouwing, of expliciet 'geen nieuwe gevonden'",
        goes_to=goes_to, parent=DISCOVERY_ROOT)
    return pid


def spaced_seed(seeds: list[str], state: dict) -> str | None:
    """Spaced repetition: kies de seed die het langst geleden is gedraaid (ongeziene eerst).
    `state` = {seed: laatste_run_ts}. Geeft None bij lege seedlijst."""
    if not seeds:
        return None
    return min(seeds, key=lambda s: state.get(s, 0.0))


def harvest(projects, pinboard, pid: str, terms: list[str], *,
            route_review, library=None) -> dict:
    """Rond een discovery-project af: markeer done, hang de uitkomst als briefje op het prikbord,
    en routeer elke nieuwe term naar de Librarian-review (via `route_review(term)->bool`).
    Dedup: een term die de bibliotheek al kent (élke status) wordt niet opnieuw gerouteerd."""
    p = projects.get(pid)
    if p is None:
        return {"ok": False, "error": "project niet gevonden"}
    owner = p.get("owner")
    tag = TAG.get(owner, "discovery")
    fresh = []
    for t in terms:
        t = (t or "").strip()
        if not t:
            continue
        if library is not None and library.status(t) is not None:
            continue                       # al bekend → niet opnieuw reviewen
        if route_review(t):
            fresh.append(t)
    summary = (f"{len(fresh)} nieuwe term(en): " + ", ".join(fresh[:8])) if fresh \
        else "geen nieuwe termen gevonden"
    projects.complete(pid, outcome=summary)
    bid = pinboard.post("outcome", tag, summary, by=owner, links=[pid])
    return {"ok": True, "pid": pid, "fresh": fresh, "briefje": bid}


def request_new_seeds(pinboard, *, by: str = "trends") -> str:
    """Trends is door de seeds heen → hang een verzoek-briefje op voor Harry (tag 'seed').
    Dedup zit in de Pinboard (zelfde verzoek nooit dubbel)."""
    return pinboard.post("request", TAG["harry_hemp"],
                         "Nieuwe seed-woorden nodig (related-radar is door de seeds heen)", by=by)


def run_discovery_pulse(projects, pinboard, library, available_roles, *,
                        wip=None, do_discovery, route_review, seeds_state=None) -> dict:
    """Eén discovery-puls, bord-gedreven:
      1. zorg dat er discovery-projecten klaarstaan (future) per staande accountability
      2. board_loop activeert ze binnen WIP + master-switch (root moet 'running' staan)
      3. voor elk geactiveerd discovery-project: do_discovery → harvest (done + briefje + review)
      4. Trends: spaced repetition; door de seeds heen → verzoek-briefje aan Harry

    `do_discovery(owner, scope) -> list[str]` en `route_review(term) -> bool` zijn geïnjecteerd
    (mens-gated capaciteit). `seeds_state` = {seed: ts} voor spaced repetition (in/uit)."""
    seeds_state = seeds_state if seeds_state is not None else {}
    avail = set(available_roles)
    seeds = seeds_from_library(library)
    out = {"created": [], "harvested": [], "requested_seeds": False, "activated": []}

    # 1) Klaarzetten — Trends krijgt de spaced-repetition-seed; geen seeds → verzoek aan Harry.
    if "trends" in avail:
        if seeds:
            seed = spaced_seed(seeds, seeds_state)
            pid = make_discovery_project(projects, "trends", f"related zoekwoorden bij '{seed}'")
            if pid:
                out["created"].append(pid)
        else:
            request_new_seeds(pinboard, by="trends")
            out["requested_seeds"] = True
    if "harry_hemp" in avail:
        pid = make_discovery_project(projects, "harry_hemp",
                                     "nieuwe seed-woorden (lange-termijn-trend)")
        if pid:
            out["created"].append(pid)
    if "concurrent_scout" in avail:
        pid = make_discovery_project(projects, "concurrent_scout",
                                     "zoekwoorden van gevolgde concurrenten")
        if pid:
            out["created"].append(pid)

    # 2) Scheduler activeert binnen WIP + master-switch (root 'running').
    res = activate_pulse(projects, available_roles, wip=wip)
    out["activated"] = res["activated"]

    # 3) Oogst elk net-geactiveerd discovery-project.
    import time as _t
    for pid in res["activated"]:
        p = projects.get(pid)
        if not p or p.get("origin") != "discovery":
            continue
        owner, scope = p.get("owner"), str(p.get("scope", ""))
        try:
            terms = list(do_discovery(owner, scope) or [])
        except Exception:
            terms = []
        h = harvest(projects, pinboard, pid, terms, route_review=route_review, library=library)
        out["harvested"].append(h)
        # spaced repetition: deze seed is nu gedraaid
        if owner == "trends" and scope.startswith("related zoekwoorden bij '"):
            seed = scope.split("'", 2)[1] if "'" in scope else scope
            seeds_state[seed] = _t.time()
    return out
