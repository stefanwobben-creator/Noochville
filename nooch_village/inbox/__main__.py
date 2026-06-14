"""CLI voor de human inbox — het geauthenticeerde lokale approval-oppervlak.

Gebruik:
    python -m nooch_village.inbox          # toon pending items
    python -m nooch_village.inbox list     # idem
    python -m nooch_village.inbox all      # toon alle items incl. gesloten
    python -m nooch_village.inbox show <id>

    python -m nooch_village.inbox approve <id> [reden]
    python -m nooch_village.inbox reject  <id> [reden]
    python -m nooch_village.inbox amend   <id> <tekst>
    python -m nooch_village.inbox defer   <id> [reden]

Beveiligingsgrens:
    Approvals en activaties mogen UITSLUITEND op dit geauthenticeerde lokale
    oppervlak bevestigd worden. Geen extern of ongeauthenticeerd kanaal mag
    een approval triggeren — notificaties zijn altijd alleen een heads-up.
"""
from __future__ import annotations
import os, sys, time
from datetime import datetime


def _data_dir() -> str:
    # __file__ = .../nooch_village/inbox/__main__.py → project root is two levels up
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))


def _inbox_only():
    """Laad HumanInbox direct uit JSON — geen Village, geen sync_unmanned."""
    from nooch_village.human_inbox import HumanInbox
    return HumanInbox(os.path.join(_data_dir(), "human_inbox.json"))


def _records_only():
    """Laad Records direct — voor archiveren bij reject activation."""
    from nooch_village.governance import Records
    return Records(os.path.join(_data_dir(), "governance_records.json"))


def _fmt_ts(ts) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")


def _status_icon(status: str) -> str:
    return {"pending": "⏳", "approved": "✅", "rejected": "❌",
            "amended": "✏️ ", "deferred": "⏸️ "}.get(status, "?")


def _type_icon(typ: str) -> str:
    return {"escalation": "🏛️", "activation": "🔧", "keyword": "📚"}.get(typ, "?")


def _print_item_summary(item: dict) -> None:
    icon   = _type_icon(item["type"])
    status = _status_icon(item["status"])
    print(f"  {item['id']}  {icon} {item['type']:<11} {status} {item['status']:<10} "
          f"{item['subject']:<22} {_fmt_ts(item['created_at'])}")


def _print_item_full(item: dict) -> None:
    icon = _type_icon(item["type"])
    print(f"\n{'─'*65}")
    print(f"{icon}  {item['type'].upper()}  [{item['id']}]")
    print(f"{'─'*65}")
    print(f"Status    : {_status_icon(item['status'])} {item['status']}")
    print(f"Subject   : {item['subject']}")
    print(f"Aangemaakt: {_fmt_ts(item['created_at'])}")

    ctx = item.get("context", {})

    if item["type"] == "escalation":
        print(f"\n── Voorstel ──")
        print(f"Voorstel-ID : {ctx.get('proposal_id')}")
        print(f"Proposer    : {ctx.get('proposer_role')}")
        print(f"Change-kind : {ctx.get('change_kind')}")
        purpose = ctx.get("purpose")
        if purpose:
            print(f"Purpose     : {purpose[:80]}")
        accs = ctx.get("add_accountabilities", [])
        if accs:
            print(f"Accountabilities ({len(accs)}):")
            for a in accs:
                print(f"  · {a[:80]}")
        doms = ctx.get("add_domains", [])
        if doms:
            print(f"Domeinen    : {doms}")
        tension = ctx.get("tension")
        if tension:
            print(f"\nTension  : {tension[:120]}")
        trigger = ctx.get("trigger_example")
        if trigger:
            print(f"Trigger  : {trigger[:120]}")
        rationale = ctx.get("rationale")
        if rationale:
            print(f"Rationale: {rationale[:120]}")
        print(f"\n── Gate-uitkomst ──")
        print(f"Poort    : {ctx.get('gate')}")
        print(f"Reden    : {ctx.get('gate_reason')}")
        print(f"\n── Acties ──")
        print(f"  approve <id> [reden]   → governance_verdict approve → Secretary adopteert")
        print(f"  reject  <id> [reden]   → afgewezen, gesloten")
        print(f"  amend   <id> <tekst>   → gewijzigd voorstel opnieuw door de poort")
        print(f"  defer   <id> [reden]   → uitgesteld, blijft geregistreerd")

    elif item["type"] == "activation":
        print(f"\n── Rol ──")
        print(f"Source    : {ctx.get('source')}")
        print(f"Purpose   : {ctx.get('purpose','')[:100]}")
        accs = ctx.get("accountabilities", [])
        if accs:
            print(f"Accountabilities ({len(accs)}):")
            for a in accs:
                print(f"  · {a[:80]}")
        doms = ctx.get("domains", [])
        if doms:
            print(f"Domeinen  : {doms}")
        skills_now = ctx.get("current_skills", [])
        print(f"Skills nu : {skills_now or '(geen — nog te schrijven)'}")

        plan = ctx.get("activation_plan", {})
        if plan:
            print(f"\n── Activatieplan (beschrijving; code schrijf je daarna per hand) ──")
            print(f"Klasse-naam  : {plan.get('class_name')}")
            print(f"Klasse-bestand: {plan.get('class_file')}")
            skills_to_write = plan.get("skills_to_write", [])
            if skills_to_write:
                print(f"Skills te schrijven ({len(skills_to_write)}):")
                for s in skills_to_write:
                    print(f"  · {s['label']:<32} → {s['file']}")
                    print(f"    klasse: {s['class_name']}")
            else:
                print("Skills te schrijven: (geen externe API's gevonden in accountabilities)")
            print(f"CLASS_MAP-entry : {plan.get('class_map_entry')}")
            print(f"\n⚠  {plan.get('note','')}")

        print(f"\n── Acties ──")
        print(f"  approve <id> [reden]   → green-light; code daarna handmatig + code-review")
        print(f"  reject  <id> [reden]   → niet implementeren, gesloten")
        print(f"  amend   <id> <tekst>   → plan aanpassen, item bijwerken")
        print(f"  defer   <id> [reden]   → uitstellen, blijft geregistreerd")

    elif item["type"] == "means_gap":
        print(f"\n── Capaciteitsgrens ──")
        print(f"Gap-key     : {ctx.get('gap_key', item['subject'])}")
        desc = ctx.get("description", "")
        if desc:
            print(f"Beschrijving: {desc}")

    elif item["type"] == "keyword":
        ctx = item.get("context", {})
        demand = ctx.get("demand", {})
        src    = demand.get("source", "?")
        signal = demand.get("signal", "?")
        interest = demand.get("interest")
        print(f"\n── Woord ──")
        print(f"Woord     : {ctx.get('word')}")
        print(f"Bron      : {src}  |  Signaal: {signal}"
              + (f"  |  Interest: {interest}" if interest else ""))
        pos = demand.get("position")
        if pos:
            print(f"Positie   : {pos:.1f}  (bucket: {demand.get('bucket','?')})")
        locale = demand.get("locale")
        if locale:
            print(f"Locale    : {locale}")
        print(f"\n── Reden escalatie ──")
        print(f"{ctx.get('reason','')}")
        print(f"\n── Acties ──")
        print(f"  approve <id> [reden]   → goedkeuren → in bibliotheek als 'approved'")
        print(f"  reject  <id> [reden]   → verbieden → in bibliotheek als 'forbidden'")
        print(f"  amend   <id> <tekst>   → notitie toevoegen, opnieuw beoordelen")
        print(f"  defer   <id> [reden]   → uitstellen, blijft geregistreerd")

    res = item.get("resolution")
    if res:
        print(f"\n── Beslissing ──")
        print(f"Actie     : {res.get('action')}")
        if res.get("reason"):
            print(f"Reden     : {res['reason']}")
        if res.get("amendment"):
            print(f"Wijziging : {res['amendment']}")
        print(f"Opgelost  : {_fmt_ts(item.get('resolved_at'))}")
    print()


def _load():
    from nooch_village.village import Village
    v = Village(heartbeat_seconds=86400)
    return v.human_inbox, v


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "list"

    if cmd in ("list", "pending"):
        inbox = _inbox_only()
        items = inbox.pending()
        print(f"\n⏳ Human inbox — {len(items)} pending item(s)\n")
        if not items:
            print("  (leeg — geen beslissingen nodig)\n")
        else:
            print(f"  {'ID':<14} {'Type':<13} {'Status':<12} {'Subject':<24} Aangemaakt")
            print("  " + "─" * 72)
            for item in items:
                _print_item_summary(item)
            print()

    elif cmd == "all":
        inbox = _inbox_only()
        items = inbox.all()
        print(f"\n📋 Human inbox — alle {len(items)} item(s)\n")
        if not items:
            print("  (leeg)\n")
        else:
            print(f"  {'ID':<14} {'Type':<13} {'Status':<12} {'Subject':<24} Aangemaakt")
            print("  " + "─" * 72)
            for item in sorted(items, key=lambda x: x["created_at"]):
                _print_item_summary(item)
            print()

    elif cmd == "show":
        if len(argv) < 2:
            print("Gebruik: inbox show <id>"); sys.exit(1)
        inbox = _inbox_only()
        item = inbox.get(argv[1])
        if item is None:
            print(f"Item '{argv[1]}' niet gevonden."); sys.exit(1)
        _print_item_full(item)

    elif cmd == "approve":
        if len(argv) < 2:
            print("Gebruik: inbox approve <id> [reden]"); sys.exit(1)
        iid    = argv[1]
        reason = " ".join(argv[2:])

        # Lees item zonder Village (geen sync_unmanned side-effect)
        inbox = _inbox_only()
        item = inbox.get(iid)
        if item is None:
            print(f"Item '{iid}' niet gevonden."); sys.exit(1)
        if item["status"] != "pending":
            print(f"Item '{iid}' is al '{item['status']}', niet pending."); sys.exit(1)

        if item["type"] == "escalation":
            # Escalatie vereist de bus (governance_verdict-event)
            from nooch_village.event_bus import Event
            _, v = _load()
            v.start()
            time.sleep(0.1)
            ok = v.approve_escalation(iid, reason=reason)
            time.sleep(0.5)
            v.stop()
            if ok:
                print(f"✅ Escalatie {iid} goedgekeurd → governance_verdict approve gestuurd.")
                pid = item["context"].get("proposal_id")
                rec = v.records.get(pid.split(":")[0] if pid and ":" in pid else item["subject"])
                if rec:
                    print(f"   Record v{rec.version} opgeslagen voor '{rec.id}'.")
            else:
                print(f"✘ Kon escalatie {iid} niet goedkeuren (item niet pending of niet gevonden).")

        elif item["type"] == "activation":
            inbox.resolve(iid, "approved", reason=reason)
            plan = item["context"].get("activation_plan", {})
            print(f"✅ Activatie '{item['subject']}' green-light gegeven [{iid}].")
            print(f"\nVolgende stappen (handmatig, volgorde telt):")
            for i, s in enumerate(plan.get("skills_to_write", []), 1):
                print(f"  {i}. Schrijf {s['file']}")
                print(f"     klasse: {s['class_name']}, skill_id: {s['skill_id']}")
            n = len(plan.get("skills_to_write", []))
            print(f"  {n+1}. Schrijf klasse {plan.get('class_name')} in {plan.get('class_file')}")
            print(f"  {n+2}. Registreer skills in Village.__init__")
            print(f"  {n+3}. Voeg toe aan CLASS_MAP: {plan.get('class_map_entry')}")
            print(f"\n⚠  Approval green-light de implementatie.")
            print(f"   Iedere stap hierboven passeert daarna nog de normale per-edit code-review.")

        elif item["type"] == "keyword":
            # Keyword vereist de bibliotheek via Village-context
            _, v = _load()
            word = item["context"].get("word", item["subject"])
            inbox.resolve(iid, "approved", reason=reason)
            v.context.library.curate(word, "approved",
                                     rationale=reason or "menselijke goedkeuring via inbox",
                                     by="human")
            print(f"✅ '{word}' goedgekeurd → in bibliotheek als 'approved'.")

    elif cmd == "reject":
        if len(argv) < 2:
            print("Gebruik: inbox reject <id> [reden]"); sys.exit(1)
        iid    = argv[1]
        reason = " ".join(argv[2:])

        # Lees item zonder Village (geen sync_unmanned side-effect)
        inbox = _inbox_only()
        item = inbox.get(iid)
        if item is None:
            print(f"Item '{iid}' niet gevonden."); sys.exit(1)
        if item["status"] != "pending":
            print(f"Item '{iid}' is al '{item['status']}'."); sys.exit(1)

        if item["type"] == "escalation":
            # Escalatie vereist de bus (governance_verdict-event)
            from nooch_village.event_bus import Event
            pid = item["context"].get("proposal_id")
            _, v = _load()
            v.start()
            time.sleep(0.1)
            inbox.resolve(iid, "rejected", reason=reason)
            v.bus.publish(Event(
                "governance_verdict",
                {"proposal_id": pid, "decision": "reject", "reason": reason},
                "human"))
            time.sleep(0.3)
            v.stop()
            print(f"❌ Item {iid} afgewezen. Reden: {reason or '(geen)'}")

        elif item["type"] == "activation":
            # Archiveer het onderliggende sensed record zodat sync_unmanned het niet opnieuw oppervlakt
            records = _records_only()
            inbox.resolve(iid, "rejected", reason=reason)
            role_id = item["subject"]
            rec = records.get(role_id)
            if rec and rec.source == "sensed" and not rec.archived:
                rec.archived = True
                rec.version += 1
                records.put(rec)
                print(f"❌ Activatie '{role_id}' afgewezen en gearchiveerd (v{rec.version}). "
                      f"Reden: {reason or '(geen)'}")
            else:
                print(f"❌ Activatie '{role_id}' afgewezen. Reden: {reason or '(geen)'}")

        elif item["type"] == "keyword":
            # Keyword vereist de bibliotheek via Village-context
            _, v = _load()
            word = item["context"].get("word", item["subject"])
            inbox.resolve(iid, "rejected", reason=reason)
            v.context.library.curate(word, "forbidden",
                                     rationale=reason or "menselijk besluit via inbox",
                                     by="human")
            print(f"❌ '{word}' verboden → in bibliotheek als 'forbidden'.")

        else:
            inbox.resolve(iid, "rejected", reason=reason)
            print(f"❌ Item {iid} afgewezen. Reden: {reason or '(geen)'}")

    elif cmd == "amend":
        if len(argv) < 3:
            print("Gebruik: inbox amend <id> <wijziging-tekst>"); sys.exit(1)
        iid       = argv[1]
        amendment = " ".join(argv[2:])
        inbox     = _inbox_only()
        item = inbox.get(iid)
        if item is None:
            print(f"Item '{iid}' niet gevonden."); sys.exit(1)
        if item["status"] != "pending":
            print(f"Item '{iid}' is al '{item['status']}'."); sys.exit(1)
        inbox.resolve(iid, "amended", amendment=amendment)
        print(f"✏️  Item {iid} gemarkeerd als amended.")
        print(f"   Wijziging: {amendment}")
        if item["type"] == "escalation":
            print(f"\nVolgende stap: pas het voorstel aan en dien het opnieuw in via")
            print(f"  Village.submit_proposal() met de wijziging verwerkt.")
        elif item["type"] == "activation":
            print(f"\nVolgende stap: werk de rol-definitie bij en dien opnieuw in via")
            print(f"  inbox.add_activation() na aanpassing van het governance-record.")

    elif cmd == "defer":
        if len(argv) < 2:
            print("Gebruik: inbox defer <id> [reden]"); sys.exit(1)
        iid    = argv[1]
        reason = " ".join(argv[2:])
        inbox  = _inbox_only()
        item = inbox.get(iid)
        if item is None:
            print(f"Item '{iid}' niet gevonden."); sys.exit(1)
        if item["status"] != "pending":
            print(f"Item '{iid}' is al '{item['status']}'."); sys.exit(1)
        inbox.resolve(iid, "deferred", reason=reason)
        print(f"⏸️  Item {iid} uitgesteld. Reden: {reason or '(geen)'}")
        print(f"   Item blijft geregistreerd in data/human_inbox.json.")

    else:
        print(f"Onbekend commando: '{cmd}'")
        print("Gebruik: list | all | show <id> | approve | reject | amend | defer")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
