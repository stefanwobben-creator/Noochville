"""Projecten waarvan de trekker geen gebruiker is (16 oktober 2026, besluit Stefan).

Op het projectenbord stonden de rijen "Sid the Science Kid (AI)" en "stefan@nooch.earth". Het bord
maakt een rij per waarde van `project.person` / `project.agent`, en geen van beide was een mens met
een people-record:

- `person = stefan@nooch.earth` — de aannameroute van projectvoorstellen (verwijderd in #530, 21
  september 2026) zette `person=username`, en dat is het LOGIN-E-MAILADRES, niet het people-id;
- `agent = <persona>` — sinds "AI is instrument, geen rol" trekt een AI geen project meer.

Dit zet ze recht, met een dry-run als standaard:

- open projecten: een `person` die geen people-id is, wordt leeg ("No owner") — of, met
  `email_naar_persoon`, het people-id van de mens met dat e-mailadres; elke `agent` wordt leeg;
- gearchiveerde projecten blijven ongemoeid, BEHALVE met `email_naar_persoon`: dan krijgt ook een
  gearchiveerd project met een e-mailadres als `person` het people-id (dezelfde fout, dezelfde mens);
- historie (`log`), `geclaimd_door`, `gelegd_door` en rollen raakt dit niet.

Idempotent: na het toepassen is het plan leeg."""
from __future__ import annotations


def plan(ledger, people, personas=None, *, email_naar_persoon: bool = False) -> list[dict]:
    """[{pid, titel, status, gearchiveerd, wijzigingen: [{veld, van, naar, reden}]}], gesorteerd.
    `naar` is "" voor leeg ("No owner"). Puur: schrijft niets."""
    uit = []
    for p in ledger.all():
        arch = bool(p.get("archived"))
        wijz = []
        persoon = str(p.get("person") or "")
        if persoon and people.get(persoon) is None:
            mens = people.by_email(persoon) if email_naar_persoon else None
            if mens is not None:
                wijz.append({"veld": "person", "van": persoon, "naar": mens.id,
                             "reden": f"login e-mail → people-id of {mens.name}"})
            elif not arch:
                wijz.append({"veld": "person", "van": persoon, "naar": "",
                             "reden": "not a user (no people record)"})
        agent = str(p.get("agent") or "")
        if agent and not arch:
            pa = personas.get(agent) if personas is not None else None
            naam = getattr(pa, "name", "") or agent
            wijz.append({"veld": "agent", "van": agent, "naar": "",
                         "reden": f"AI persona '{naam}' is not a user"})
        if wijz:
            uit.append({"pid": p["id"], "titel": _titel(p), "status": p.get("status") or "",
                        "gearchiveerd": arch, "wijzigingen": wijz})
    return sorted(uit, key=lambda r: (r["gearchiveerd"], r["titel"].lower()))


def toepassen(ledger, plan_: list[dict]) -> int:
    """Schrijft het plan. Alleen `person`/`agent` (en `updated_at`); geen status, geen log."""
    n = 0
    for r in plan_:
        velden = {w["veld"]: w["naar"] for w in r["wijzigingen"]}
        if ledger.edit(r["pid"], person=velden.get("person"), agent=velden.get("agent"),
                       allow_done=True):
            n += 1
    return n


def tekst(plan_: list[dict], people=None) -> str:
    if not plan_:
        return "Nothing to change: every project owner is a user or empty."
    regels = [f"{len(plan_)} project(s):"]
    for r in plan_:
        arch = " · archived" if r["gearchiveerd"] else ""
        regels.append(f"\n  {r['pid']}  [{r['status']}{arch}]  {r['titel']}")
        for w in r["wijzigingen"]:
            naar = w["naar"] or "(empty → No owner)"
            if w["naar"] and people is not None and people.get(w["naar"]) is not None:
                naar = f"{w['naar']} ({people.get(w['naar']).name})"
            regels.append(f"      {w['veld']}: {w['van']} → {naar}   — {w['reden']}")
    return "\n".join(regels)


def _titel(p: dict) -> str:
    s = p.get("scope")
    if isinstance(s, dict):
        s = " · ".join(f"{k}: {v}" for k, v in s.items())
    return " ".join(str(s or p.get("id") or "").split())[:90]
