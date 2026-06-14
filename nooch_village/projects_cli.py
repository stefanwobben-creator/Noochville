"""CLI voor het project-grootboek.

    python -m nooch_village.projects_cli          # open projecten
    python -m nooch_village.projects_cli list
    python -m nooch_village.projects_cli all
    python -m nooch_village.projects_cli show <id>
    python -m nooch_village.projects_cli create <owner> <scope...>
"""
from __future__ import annotations
import sys
from datetime import datetime


def _fmt_ts(ts) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")


def _status_icon(s: str) -> str:
    return {"queued": "⏳", "running": "▶️ ", "blocked": "🔒", "done": "✅"}.get(s, "?")


def _print_summary(p: dict) -> None:
    scope = p["scope"] if isinstance(p["scope"], str) else str(p["scope"])[:40]
    print(f"  {p['id']:<14} {_status_icon(p['status'])} {p['status']:<9} "
          f"{p['owner']:<16} {scope:<42} {_fmt_ts(p['created_at'])}")


def _print_full(p: dict) -> None:
    print(f"\n{'─'*65}")
    print(f"▶  PROJECT  [{p['id']}]")
    print(f"{'─'*65}")
    print(f"Status    : {_status_icon(p['status'])} {p['status']}")
    print(f"Owner     : {p['owner']}")
    print(f"Trigger   : {p['trigger']}")
    print(f"Scope     : {p['scope']}")
    if p.get("blocked_on"):
        print(f"Geblokkeerd door: {p['blocked_on']}")
    print(f"Aangemaakt: {_fmt_ts(p['created_at'])}")
    print(f"Bijgewerkt: {_fmt_ts(p['updated_at'])}")
    if p.get("outcome"):
        print(f"Outcome   : {p['outcome']}")
    print()


def _load():
    from nooch_village.village import Village
    v = Village(heartbeat_seconds=86400)
    return v.context.projects


def human_create(ledger, owner: str, scope: str) -> str:
    """Maak een project met trigger 'human'. Los van argv zodat tests 'm direct aanroepen."""
    return ledger.create(owner, scope, trigger="human")


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "list"

    if cmd in ("list", "open"):
        ledger = _load()
        items = ledger.open()
        print(f"\n📂 Projecten — {len(items)} open\n")
        if not items:
            print("  (leeg)\n")
        else:
            print(f"  {'ID':<14} {'Status':<11} {'Owner':<16} {'Scope':<42} Aangemaakt")
            print("  " + "─" * 90)
            for p in sorted(items, key=lambda x: x["created_at"]):
                _print_summary(p)
            print()

    elif cmd == "all":
        ledger = _load()
        items = ledger.all()
        print(f"\n📋 Projecten — alle {len(items)}\n")
        if not items:
            print("  (leeg)\n")
        else:
            print(f"  {'ID':<14} {'Status':<11} {'Owner':<16} {'Scope':<42} Aangemaakt")
            print("  " + "─" * 90)
            for p in sorted(items, key=lambda x: x["created_at"]):
                _print_summary(p)
            print()

    elif cmd == "show":
        if len(argv) < 2:
            print("Gebruik: projects_cli show <id>"); sys.exit(1)
        ledger = _load()
        p = ledger.get(argv[1])
        if p is None:
            print(f"Project '{argv[1]}' niet gevonden."); sys.exit(1)
        _print_full(p)

    elif cmd == "create":
        if len(argv) < 3:
            print("Gebruik: projects_cli create <owner> <scope...>"); sys.exit(1)
        ledger = _load()
        owner  = argv[1]
        scope  = " ".join(argv[2:])
        pid    = human_create(ledger, owner, scope)
        print(f"✅ Project aangemaakt: {pid}  (owner={owner}, trigger=human)")

    else:
        print(f"Onbekend commando: '{cmd}'")
        print("Gebruik: list | all | show <id> | create <owner> <scope...>")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
