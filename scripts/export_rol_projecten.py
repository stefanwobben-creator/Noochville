"""Exporteer de volledige inhoud van alle projecten van één rol naar een .txt-bestand.

Gebruik:
    ./venv/bin/python scripts/export_rol_projecten.py harry_hemp
    ./venv/bin/python scripts/export_rol_projecten.py harry_hemp data/exports/sid.txt

Leest de ProjectLedger-store (data/projects.json) en de persona-/people-stores voor de namen.
Niets wordt weggelaten: onbekende velden komen als JSON-rest onderaan elk project mee, zodat
een modelwijziging in de store niet stil uit de export verdwijnt.
"""
from __future__ import annotations
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str, default):
    try:
        with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _ts(v) -> str:
    if not v:
        return "—"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(v)))
    except Exception:
        return str(v)


def _naam(actor_id: str, personas: dict, people: dict) -> str:
    if not actor_id:
        return "—"
    for store in (personas, people):
        rec = store.get(actor_id) or {}
        if rec.get("name"):
            return f"{rec['name']} ({actor_id})"
    return actor_id


# Velden die de renderer expliciet behandelt; de rest gaat naar "OVERIGE VELDEN".
_GERENDERD = {
    "id", "owner", "person", "agent", "scope", "status", "blocked_on", "waiting_on",
    "trigger", "origin", "created_at", "updated_at", "last_tended", "due", "label",
    "cluster", "parent", "keyword", "missie_impact", "business_impact", "effort",
    "private", "archived", "formalized", "worked", "executions", "review_raised",
    "description", "hypothesis", "dod_outcome", "done_when", "goes_to", "outcome",
    "progress", "links", "business_case", "checklist", "checklists", "attachments",
    "comments", "log",
}


def render(p: dict, personas: dict, people: dict, nr: int, totaal: int) -> list[str]:
    L: list[str] = []
    add = L.append
    add("=" * 100)
    add(f"PROJECT {nr}/{totaal} — {p.get('scope') or '(geen scope)'}")
    add("=" * 100)
    add(f"id             : {p.get('id')}")
    add(f"rol (owner)    : {p.get('owner')}")
    add(f"uitvoerder     : {_naam(p.get('agent'), personas, people)}")
    if p.get("person"):
        add(f"persoon        : {_naam(p.get('person'), personas, people)}")
    status = p.get("status") or "—"
    if p.get("blocked_on"):
        status += f"  (geblokkeerd op: {p['blocked_on']})"
    if p.get("waiting_on"):
        status += f"  (wacht op: {p['waiting_on']})"
    add(f"status         : {status}")
    add(f"trigger        : {p.get('trigger') or '—'}"
        + (f"   origin: {p['origin']}" if p.get("origin") else ""))
    add(f"aangemaakt     : {_ts(p.get('created_at'))}")
    add(f"bijgewerkt     : {_ts(p.get('updated_at'))}")
    if p.get("last_tended"):
        add(f"laatst getend  : {_ts(p.get('last_tended'))}")
    if p.get("due"):
        add(f"deadline       : {p['due']}")
    meta = [
        ("label", p.get("label")), ("cluster", p.get("cluster")), ("parent", p.get("parent")),
        ("keyword", p.get("keyword")), ("missie-impact", p.get("missie_impact")),
        ("business-impact", p.get("business_impact")), ("effort", p.get("effort")),
    ]
    meta_txt = ", ".join(f"{k}={v}" for k, v in meta if v)
    if meta_txt:
        add(f"kenmerken      : {meta_txt}")
    vlaggen = [k for k in ("private", "archived", "formalized", "worked", "review_raised") if p.get(k)]
    add(f"vlaggen        : {', '.join(vlaggen) if vlaggen else '—'}"
        f"   | uitvoeringen: {p.get('executions', 0)}")

    for kop, veld in (("BESCHRIJVING", "description"), ("HYPOTHESE", "hypothesis"),
                      ("DEFINITION OF DONE (uitkomst)", "dod_outcome"),
                      ("KLAAR WANNEER", "done_when"), ("GAAT NAAR", "goes_to"),
                      ("UITKOMST", "outcome"), ("VOORTGANG (laatste regel)", "progress")):
        val = p.get(veld)
        if val:
            add("")
            add(f"— {kop} —")
            add(str(val).strip())

    if p.get("business_case"):
        add("")
        add("— BUSINESS CASE —")
        add(json.dumps(p["business_case"], ensure_ascii=False, indent=2))

    if p.get("links"):
        add("")
        add("— LINKS —")
        for u in p["links"]:
            add(f"  • {u}")

    losse = p.get("checklist") or []
    if losse:
        add("")
        add("— LOSSE CHECKLIST-ITEMS —")
        for it in losse:
            add(f"  [{'x' if (isinstance(it, dict) and it.get('done')) else ' '}] "
                f"{it.get('text') if isinstance(it, dict) else it}")

    for cl in (p.get("checklists") or []):
        items = cl.get("items") or []
        klaar = sum(1 for i in items if i.get("done"))
        add("")
        add(f"— CHECKLIST: {cl.get('title') or '(zonder titel)'} "
            f"({klaar}/{len(items)} klaar, id={cl.get('id')}) —")
        for i, it in enumerate(items, 1):
            add(f"  {i:>2}. [{'x' if it.get('done') else ' '}] {it.get('text', '')}")
            if it.get("skill"):
                add(f"        skill   : {it['skill']}")
            if it.get("reason"):
                add(f"        reden   : {it['reason']}")
            if it.get("payload"):
                add(f"        payload : {json.dumps(it['payload'], ensure_ascii=False)}")

    if p.get("attachments"):
        add("")
        add("— BIJLAGEN —")
        for a in p["attachments"]:
            add(f"  • [{a.get('kind', '?')}] {a.get('title') or '(zonder titel)'} — "
                f"{a.get('url', '')}  ({_ts(a.get('at'))})")

    if p.get("comments"):
        add("")
        add("— REACTIES —")
        for c in p["comments"]:
            add(f"  • {_ts(c.get('at'))} {c.get('who') or c.get('author') or '?'}: "
                f"{c.get('text', '')}")

    logs = p.get("log") or []
    if logs:
        add("")
        add(f"— LOGBOEK ({len(logs)} regels, oud → nieuw) —")
        for e in sorted(logs, key=lambda x: x.get("at") or 0):
            wie = e.get("who") or e.get("author") or "?"
            soort = f" [{e['kind']}]" if e.get("kind") else ""
            add(f"  ┌ {_ts(e.get('at'))} · {wie}{soort}")
            for regel in str(e.get("text", "")).splitlines() or [""]:
                add(f"  │ {regel}")
            if e.get("reactions"):
                add(f"  │ reacties: {json.dumps(e['reactions'], ensure_ascii=False)}")
            add("  └")

    rest = {k: v for k, v in p.items() if k not in _GERENDERD}
    if rest:
        add("")
        add("— OVERIGE VELDEN (rauw) —")
        add(json.dumps(rest, ensure_ascii=False, indent=2))
    add("")
    return L


def main() -> int:
    rol = sys.argv[1] if len(sys.argv) > 1 else "harry_hemp"
    projects = _read("projects.json", {})
    personas = _read("personas.json", {})
    people = _read("people.json", {})
    assignments = _read("assignments.json", {})

    vervullers = [_naam(e.get("id"), personas, people)
                  for e in (assignments.get(rol) or []) if e.get("id")]

    mijn = [p for p in projects.values() if p.get("owner") == rol]
    mijn.sort(key=lambda p: p.get("created_at") or 0)

    uit = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "data", "exports",
        f"projecten_{rol}_{time.strftime('%Y-%m-%d')}.txt")
    os.makedirs(os.path.dirname(uit), exist_ok=True)

    kop = [
        "NoochVillage — projectexport",
        f"rol            : {rol}",
        f"vervuld door   : {', '.join(vervullers) if vervullers else '—'}",
        f"aantal projecten: {len(mijn)} (van {len(projects)} in de store)",
        f"bron           : data/projects.json (gewijzigd {_ts(os.path.getmtime(os.path.join(ROOT, 'data', 'projects.json')))})",
        f"geëxporteerd   : {_ts(time.time())}",
        "",
        "INHOUD",
    ]
    for i, p in enumerate(mijn, 1):
        kop.append(f"  {i:>2}. [{p.get('status')}] {p.get('scope') or '(geen scope)'}")
    kop.append("")

    regels = list(kop)
    for i, p in enumerate(mijn, 1):
        regels += render(p, personas, people, i, len(mijn))

    with open(uit, "w", encoding="utf-8") as fh:
        fh.write("\n".join(regels))
    print(f"{len(mijn)} projecten → {uit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
