"""Gemenere Monte-Carlo: stress-test de guardrails uit ronde 1.
Stressoren: (A) circulaire dependencies, (B) een rol die uitvalt, (C) WIP-bij-hervatten aan/uit."""
from __future__ import annotations
import random

ROLE_SKILLS = {"harry": {"seed", "science"}, "trends": {"related"}, "scout": {"supplier", "competitor"},
               "librarian": {"review"}, "copywriter": {"copy"}, "watcher": {"businesscase"}}
ALL_TAGS = sorted({t for s in ROLE_SKILLS.values() for t in s})
DEPS_ACYCLIC = {"related": ["seed"], "supplier": ["science"], "copy": ["businesscase"],
                "businesscase": ["competitor"], "review": [], "seed": [], "science": [],
                "competitor": []}
# Gemeen: een echte cyclus (related vraagt seed, seed vraagt related) → kan eindeloos rondpompen.
DEPS_CYCLIC = dict(DEPS_ACYCLIC); DEPS_CYCLIC["seed"] = ["related"]; DEPS_CYCLIC["science"] = ["supplier"]


def run(pulses=300, seed=0, wip_role=3, wip_board=3, p_new=0.25, p_human=0.05, human_every=4,
        fallback=6, prevent_cycles=True, wip_on_resume=True, cyclic=False,
        drop_role=None, drop_at=10**9, maxdepth=8):
    rng = random.Random(seed); DEPS = DEPS_CYCLIC if cyclic else DEPS_ACYCLIC
    P = {}; nid = [0]; human_q = []
    m = {"done": 0, "human_max": 0, "wipv": 0, "esc": 0}
    act_hist = []
    def avail():                                   # rollen die nu kunnen werken (rol-uitval)
        return {r: s for r, s in ROLE_SKILLS.items() if not (r == drop_role and t >= drop_at)}
    def role_for(tag):
        return [r for r, s in avail().items() if tag in s]
    def new(tag, cluster=None, parent=None, depth=0, anc=()):
        nid[0] += 1; pid = f"p{nid[0]}"
        P[pid] = {"id": pid, "tag": tag, "owner": None, "status": "future", "cluster": cluster or pid,
                  "parent": parent, "depth": depth, "needs": None, "cycles": rng.randint(1, 3),
                  "born": t, "anc": set(anc) | {tag}}
        return pid
    def board_active():
        return sum(1 for p in P.values() if p["status"] == "active")
    def activate(p):                               # WIP-poort bij ELKE activering (ook hervatten)
        if wip_on_resume and wip_board and board_active() >= wip_board:
            p["status"] = "future"; return
        p["status"] = "active"

    for t in range(pulses):
        if rng.random() < p_new:
            new(rng.choice(ALL_TAGS))
        for role in rng.sample(list(avail()), len(avail())):
            while True:
                ra = sum(1 for p in P.values() if p["status"] == "active" and p["owner"] == role)
                if ra >= wip_role or (wip_board and board_active() >= wip_board):
                    break
                elig = [p for p in P.values() if p["status"] == "future" and p["tag"] in avail()[role]]
                if not elig:
                    break
                pick = min(elig, key=lambda p: p["born"]); pick["status"] = "active"; pick["owner"] = role
        for p in [p for p in P.values() if p["status"] == "active"]:
            r = rng.random()
            if p["depth"] < maxdepth and DEPS[p["tag"]] and r < 0.5 and p["needs"] is None:
                dep = DEPS[p["tag"]][0]
                if prevent_cycles and dep in p["anc"]:
                    pass
                else:
                    c = new(dep, p["cluster"], p["id"], p["depth"] + 1, p["anc"])
                    p["needs"] = c; p["status"] = "waiting"; continue
            if r > 1 - p_human:
                human_q.append(p["id"]); p["status"] = "waiting"; p["needs"] = "human"; continue
            p["cycles"] -= 1
            if p["cycles"] <= 0:
                p["status"] = "done"; m["done"] += 1
                par = P.get(p["parent"])
                if par and par.get("needs") == p["id"]:
                    par["needs"] = None; activate(par)
        if human_q and t % human_every == 0:
            pr = P.get(human_q.pop(0))
            if pr and pr["needs"] == "human":
                pr["needs"] = None; activate(pr)
        for p in P.values():
            if p["status"] == "future" and not role_for(p["tag"]) and t - p["born"] > fallback:
                human_q.append(p["id"]); p["status"] = "waiting"; p["needs"] = "human"; m["esc"] += 1
        m["human_max"] = max(m["human_max"], len(human_q))
        if wip_board and board_active() > wip_board:
            m["wipv"] += 1
        act_hist.append(board_active())

    waiting = [p for p in P.values() if p["status"] == "waiting"]
    def stuck(p, seen=None):
        seen = seen or set()
        if p["id"] in seen:
            return True                            # echte cyclus in de wachtketen
        seen.add(p["id"])
        if p["needs"] == "human":
            return False
        ch = P.get(p["needs"]) if p["needs"] else None
        return (p["status"] == "waiting") if ch is None else stuck(ch, seen)
    dead = sum(1 for p in waiting if p["needs"] and p["needs"] != "human" and stuck(p))
    return {"done": m["done"], "projects": len(P), "deadlocked": dead, "wipv": m["wipv"],
            "human_max": m["human_max"], "esc": m["esc"], "active_max": max(act_hist)}


def avg(rs, k): return round(sum(r[k] for r in rs) / len(rs), 1)
def tot(rs, k): return sum(r[k] for r in rs)
S = range(8)
print("=== A. Circulaire dependencies: ancestor-guard AAN vs UIT ===")
for prev in (True, False):
    rs = [run(seed=s, cyclic=True, prevent_cycles=prev) for s in S]
    print(f"  guard={prev!s:5} | deadlocks(tot)={tot(rs,'deadlocked'):3} | gem.projecten={avg(rs,'projects'):6} "
          f"| gem.done={avg(rs,'done'):6} | max actief={max(r['active_max'] for r in rs)}")
print("\n=== B. Rol valt uit (scout vanaf puls 50) — vangnet naar mens ===")
rs = [run(seed=s, drop_role="scout", drop_at=50) for s in S]
print(f"  gem.done={avg(rs,'done')} | naar-mens-geescaleerd(tot)={tot(rs,'esc')} | "
      f"deadlocks(tot)={tot(rs,'deadlocked')} | max mens-rij={max(r['human_max'] for r in rs)}")
print("\n=== C. WIP-bij-hervatten AAN vs UIT (wip_board=3) ===")
for wor in (True, False):
    rs = [run(seed=s, wip_on_resume=wor) for s in S]
    print(f"  wip_on_resume={wor!s:5} | WIP-overtredingen(tot)={tot(rs,'wipv'):3} | "
          f"max actief={max(r['active_max'] for r in rs)} | gem.done={avg(rs,'done')}")
