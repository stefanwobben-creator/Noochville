"""Groei-puls demo — één eerlijke dag.

Levenscyclus:
  1. Village start met heartbeat_seconds=0 (kalender-cadans): TimeKeeper vuurt
     automatisch één dag_begint af op zijn eerste tick; geen tweede ring tot morgen.
  2. Join op alle drie pulsen: pulse_completed, gsc_pulse_completed,
     tijdgeest_pulse_completed (max 180 s).
  3. Eén dag_eindigt handmatig → Ronnie's _on_dag_eindigt schrijft het bulletin
     met alle events die de dag binnenkwamen.
  4. Wacht op bulletin_geschreven (max 30 s) en pas dan v.stop().
"""
from __future__ import annotations
import os, time
from nooch_village.event_bus import Event
from nooch_village.village import Village


def demo():
    v = Village(heartbeat_seconds=0)   # kalender-cadans: één ring, geen dag_eindigt-storm
    pulse: dict = {}
    gsc: dict = {}
    tijdgeest: dict = {}
    keyword_log: list = []
    bulletin: dict = {}

    v.bus.subscribe("pulse_completed",
                    lambda e: pulse.update(e.data))
    v.bus.subscribe("gsc_pulse_completed",
                    lambda e: gsc.update(e.data))
    v.bus.subscribe("tijdgeest_pulse_completed",
                    lambda e: tijdgeest.update(e.data))
    v.bus.subscribe("keyword_decided",
                    lambda e: keyword_log.append({**e.data, "_event": "decided"}))
    v.bus.subscribe("human_decision_needed",
                    lambda e: keyword_log.append({**e.data, "status": "escalated",
                                                   "_event": "escalated"}))
    v.bus.subscribe("bulletin_geschreven",
                    lambda e: bulletin.update(e.data))

    v.start()
    # TimeKeeper vuurt op zijn eerste tick dag_begint af (_last_day=None → nieuw).
    # Geen handmatige publicatie nodig; geen tweede ring gedurende de demo.
    print("\n================ DEMO: de groei-puls draait zichzelf ================\n")

    for _ in range(1800):          # join op alle drie pulsen, max 180 s
        if pulse and gsc and tijdgeest:
            break
        time.sleep(0.1)

    # Sluit de dag: één dag_eindigt → Ronnie verzamelt alle events en schrijft bulletin
    v.bus.publish(Event("dag_eindigt", {"label": "demo-einde"}, "demo"))

    for _ in range(300):           # wacht op bulletin_geschreven, max 30 s
        if bulletin:
            break
        time.sleep(0.1)

    v.stop()

    note_path = pulse.get("note_path")
    print(f"\n>> pulse_completed | tension={pulse.get('tension')} | note={note_path}\n")
    if note_path and os.path.exists(note_path):
        print("---------------- inhoud Field Note ----------------")
        print(open(note_path).read())
        print("---------------------------------------------------")

    print(f"\n>> gsc_pulse_completed | ok={gsc.get('ok')} | "
          f"queries={gsc.get('total', '-')} | "
          f"buckets={gsc.get('bucket_counts', gsc.get('error', '-'))}")

    if keyword_log:
        lib = v.context.library
        print(f"\n{'Bron':<28} {'Woord':<35} {'Status':<11} Reden")
        print("-" * 90)
        for kw in keyword_log:
            word = kw.get("word", "")
            demand = kw.get("demand") or (lib.status(word) or {}).get("evidence") or {}
            src = demand.get("source", "?") if isinstance(demand, dict) else "?"
            print(f"{src:<28} {word:<35} {kw.get('status', '?'):<11} "
                  f"{kw.get('reason', '')[:35]}")

    print("\n================ einde demo ================")
