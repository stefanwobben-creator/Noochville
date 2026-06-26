"""Brok 4 — discovery-rollen bedraad op het bord (b → a via 'stollen').

Discovery (zoekwoorden vinden) is geen los project maar een STAANDE ACCOUNTABILITY. Maar in
NoochVille mag iets pas een accountability worden als het zich BEWEZEN heeft als terugkerend
(rijpheidspoort, CLAUDE.md G0). Daarom loopt het in twee fasen:

  b) Elke discovery-rol heeft één STAAND EXPERIMENT-project (origin="experiment") onder de
     discovery-cluster-root (master-switch). Elke puls voert de rol het uit: dat telt +1 op de
     `executions`-teller (record_progress), hangt de uitkomst als briefje op het prikbord en
     routeert nieuwe termen naar de Librarian-review.
  a) Zodra een experiment ≥3× is uitgevoerd, draagt `roloverleg.formalize_ripe_experiments`
     (draait al mee in cockpit.gather) het AUTOMATISCH voor als rol-specifieke accountability op
     de roloverleg-agenda. De spanning is dan letterlijk: "ik heb dit 3× gedaan, dit hoort bij mij."

Optie 1 (gekozen): tellen PER ROL → scherpe, rol-specifieke accountabilities (Trends krijgt
'vindt gerelateerde zoekwoorden', Harry 'levert seed-woorden', Scout 'oogst concurrent-woorden').

Master-switch: de discovery-cluster-root staat standaard 'future' (gepauzeerd). De mens zet hem
op 'running' (cockpit /prikbord of `village discovery aan`) om de rollen te laten draaien.

PUUR & MENS-GATED: het echte term-vinden (`do_discovery`) en de review-routering (`route_review`)
worden geïnjecteerd. Deze laag schrijft GEEN code, start GEEN threads en roept GEEN externe API's
aan buiten de geïnjecteerde functies.
"""
from __future__ import annotations
import time

DISCOVERY_ROOT = "discovery"          # vaste cluster-root (master-switch voor alle discovery)
# Canonieke owner-keys = de echte rol-ids; tag = prikbord-categorie; scope = accountability-zin.
TAG = {"harry_hemp": "seed", "trends": "related", "concurrent_scout": "competitor"}
STANDING_SCOPE = {
    "harry_hemp": "levert doorlopend nieuwe seed-woorden vanuit lange-termijn-trends",
    "trends": "vindt doorlopend gerelateerde zoekwoorden bij de seeds",
    "concurrent_scout": "oogst doorlopend zoekwoorden van gevolgde concurrenten",
}


def ensure_root(projects) -> str:
    """Zorg dat de discovery-cluster-root bestaat (de master-switch). Idempotent, vaste id."""
    root = projects.get(DISCOVERY_ROOT)
    if root is None:
        projects.create("the_source", "Discovery — zoekwoorden vinden (staande accountability)",
                        "human", status="future")
        # create() geeft een random id; we forceren de vaste root-id zodat hij herkenbaar blijft.
        last = max(projects.all(), key=lambda p: p.get("created_at", 0))
        projects._projects.pop(last["id"], None)
        last["id"] = DISCOVERY_ROOT
        last["cluster"] = DISCOVERY_ROOT
        projects._projects[DISCOVERY_ROOT] = last
        projects._save()
    return DISCOVERY_ROOT


def root_active(projects) -> bool:
    """Master-switch aan? (root op 'running')."""
    r = projects.get(DISCOVERY_ROOT)
    return bool(r and r["status"] == "running")


def seeds_from_library(library) -> list[str]:
    """Approved 'volg'-woorden zijn de seeds voor de radar."""
    out = []
    for w, e in (library.all() or {}).items():
        if e.get("status") == "approved" and \
                (e.get("function") == "volg" or library.function_of(w) == "volg"):
            out.append(w)
    return sorted(out)


def ensure_experiment(projects, owner: str) -> str:
    """Maak/hergebruik het ENE staande discovery-experiment voor deze rol (origin='experiment',
    onder de master-switch-root). Eén per rol (dedup op owner). De scope is de accountability-zin
    die later stolt. Geeft het pid."""
    ensure_root(projects)
    scope = STANDING_SCOPE.get(owner, f"voert doorlopend discovery uit ({owner})")
    for p in projects.all():
        if (p.get("origin") == "experiment" and p.get("owner") == owner
                and p.get("parent") == DISCOVERY_ROOT and p.get("status") != "done"):
            return p["id"]
    return projects.create(
        owner, scope, "human", status="future", origin="experiment",
        dod_outcome="Doorlopend nieuwe kandidaat-zoekwoorden voor de Librarian-review",
        done_when="staand werk (stolt na 3× tot accountability); per puls ≥0 termen",
        goes_to="librarian", parent=DISCOVERY_ROOT)


def spaced_seed(seeds: list[str], state: dict) -> str | None:
    """Spaced repetition: kies de seed die het langst geleden is gedraaid (ongeziene eerst).
    `state` = {seed: laatste_run_ts}. Geeft None bij lege seedlijst."""
    if not seeds:
        return None
    return min(seeds, key=lambda s: state.get(s, 0.0))


def run_role(projects, pinboard, owner: str, pid: str, terms: list[str], *,
             route_review, library=None, note: str = "") -> dict:
    """Voer het staande experiment van een rol UIT voor deze puls: tel +1 (record_progress),
    hang de uitkomst als briefje op het prikbord, en routeer elke nieuwe term naar de review.
    Het experiment wordt NIET afgerond (het is staand werk dat na 3× stolt). Dedup: een term die
    de bibliotheek al kent (élke status) wordt niet opnieuw gerouteerd."""
    p = projects.get(pid)
    if p is None:
        return {"ok": False, "error": "experiment niet gevonden"}
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
    # record_progress telt +1 op de executions-teller (de motor van 'stollen na 3×').
    projects.record_progress(pid, (note + " — " if note else "") + summary)
    bid = pinboard.post("outcome", tag, summary, by=owner, links=[pid])
    return {"ok": True, "pid": pid, "fresh": fresh, "briefje": bid,
            "executions": int(projects.get(pid).get("executions", 0))}


def request_new_seeds(pinboard, *, by: str = "trends") -> str:
    """Trends is door de seeds heen → hang een verzoek-briefje op voor Harry (tag 'seed').
    Dedup zit in de Pinboard (zelfde verzoek nooit dubbel)."""
    return pinboard.post("request", TAG["harry_hemp"],
                         "Nieuwe seed-woorden nodig (related-radar is door de seeds heen)", by=by)


def run_discovery_pulse(projects, pinboard, library, available_roles, *,
                        do_discovery, route_review, seeds_state=None) -> dict:
    """Eén discovery-puls (staande-accountability-model):
      1. zorg dat elke beschikbare rol zijn staande experiment heeft (future, onder de root)
      2. master-switch UIT (root != running) → alleen klaarzetten, niets uitvoeren
      3. master-switch AAN → voer elk experiment uit: do_discovery → run_role (+1 + briefje + review)
      4. Trends: spaced repetition over de seeds; door de seeds heen → verzoek-briefje aan Harry

    `do_discovery(owner, scope) -> list[str]` en `route_review(term) -> bool` zijn geïnjecteerd
    (mens-gated). `seeds_state` = {seed: ts} voor spaced repetition (in/uit). Geen WIP-poort:
    discovery is een STAANDE baan, geen ad-hoc marktplaats (dat is board_loop)."""
    seeds_state = seeds_state if seeds_state is not None else {}
    avail = [r for r in available_roles if r in STANDING_SCOPE]
    out = {"ensured": [], "ran": [], "requested_seeds": False}

    # 1) Klaarzetten — één staand experiment per beschikbare discovery-rol.
    for owner in avail:
        out["ensured"].append(ensure_experiment(projects, owner))

    # 2) Master-switch uit → niets uitvoeren (de rollen staan klaar op het bord).
    if not root_active(projects):
        return out

    # 3) Uitvoeren per rol.
    seeds = seeds_from_library(library)
    for owner in avail:
        pid = ensure_experiment(projects, owner)
        note = ""
        if owner == "trends":
            if not seeds:
                request_new_seeds(pinboard, by="trends")
                out["requested_seeds"] = True
                # geen seeds → toch de oudste opnieuw is onmogelijk; sla uitvoeren over
                continue
            seed = spaced_seed(seeds, seeds_state)
            note = f"seed '{seed}'"
            scope_arg = f"related zoekwoorden bij '{seed}'"
            seeds_state[seed] = time.time()       # spaced repetition: nu gedraaid
        else:
            scope_arg = STANDING_SCOPE[owner]
        try:
            terms = list(do_discovery(owner, scope_arg) or [])
        except Exception:
            terms = []
        out["ran"].append(run_role(projects, pinboard, owner, pid, terms,
                                   route_review=route_review, library=library, note=note))
    return out
