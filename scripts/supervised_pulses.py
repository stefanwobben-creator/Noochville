#!/usr/bin/env python3
"""Draai N supervised once-pulsen en rapporteer de gap-tellers per puls.

Gebruik: python scripts/supervised_pulses.py [N]   (default N=4)
"""
import json, os, sys, time, logging
from pathlib import Path

# Zorg dat we de module kunnen vinden
sys.path.insert(0, str(Path(__file__).parent.parent))

from nooch_village.village import Village
from nooch_village.event_bus import Event

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s %(message)s",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TARGETS  = ["openlibrary_v2", "semscholar_no_key", "ngram_2019_cutoff", "nl_corpus_coverage"]
N_PULSEN = int(sys.argv[1]) if len(sys.argv) > 1 else 4


def _lees_gaps() -> dict:
    """Lees count + emitted voor de 4 doelgaten uit alle reflect-bestanden."""
    result = {}
    for f in Path(DATA_DIR).glob("reflect_*.json"):
        try:
            state = json.loads(f.read_text())
        except Exception:
            continue
        for key in TARGETS:
            if key in state:
                g = state[key]
                result[key] = {
                    "count":   g.get("count", 0),
                    "emitted": g.get("emitted"),
                    "acc":     (g.get("acc") or "")[:50],
                }
    return result


def _lees_inbox_open() -> list[str]:
    """Geef list van acc_text-substrings in open inbox-items."""
    path = os.path.join(DATA_DIR, "human_inbox.json")
    if not os.path.exists(path):
        return []
    try:
        inbox = json.loads(open(path).read())
        hits  = []
        for item in inbox.values():
            if item.get("status") == "open":
                raw = json.dumps(item, ensure_ascii=False)
                for key in TARGETS:
                    # We zoeken op de gap_key zelf als proxy voor de acc_text
                    if any(t in raw for t in [
                        "OpenLibrary voltekst",
                        "SEMANTIC_SCHOLAR_API_KEY",
                        "aanvullende recente bron",
                        "NL corpus dekking",
                    ]):
                        hits.append(item.get("id", "?"))
            hits = list(dict.fromkeys(hits))
        return hits
    except Exception:
        return []


def voer_puls_uit(puls_nr: int) -> dict:
    v    = Village(heartbeat_seconds=0)
    done = {}
    tijdgeest_done = {}

    v.bus.subscribe("pulse_completed",          lambda e: done.update(e.data or {"ok": True}))
    v.bus.subscribe("tijdgeest_pulse_completed", lambda e: tijdgeest_done.update(e.data or {"ok": True}))

    v.start()
    heeft_harry = "harry_hemp" in v.reconciler.live
    v.bus.publish(Event("dag_begint", {"label": f"supervised-{puls_nr}"}, "supervisor"))

    timeout = time.time() + 300  # 5 min max
    while time.time() < timeout:
        watcher_klaar = bool(done)
        harry_klaar   = bool(tijdgeest_done) or not heeft_harry
        if watcher_klaar and harry_klaar:
            break
        time.sleep(0.2)

    # Geef inwoners extra tijd voor _maybe_reflect via dag_begint
    time.sleep(2)
    v.stop()
    v.root.join(timeout=10)

    gaps   = _lees_gaps()
    inbox  = _lees_inbox_open()
    return {
        "gaps":              gaps,
        "inbox_items":       len(inbox),
        "website_watcher_ok": bool(done),
        "harry_hemp_ok":     bool(tijdgeest_done) or not heeft_harry,
    }


def main():
    print(f"\n=== Supervised {N_PULSEN} pulsen ===\n")
    # Starttoestand
    print("Begintoestand (vóór puls 1):")
    begin = _lees_gaps()
    for k in TARGETS:
        g = begin.get(k, {})
        print(f"  {k:30s}  count={g.get('count','?'):>3}  emitted={g.get('emitted')}")
    print()

    for i in range(1, N_PULSEN + 1):
        print(f"── Puls {i} ──────────────────────────────────────────")
        sys.stdout.flush()
        t0  = time.time()
        res = voer_puls_uit(i)
        dt  = time.time() - t0

        print(f"   website_watcher_ok={res['website_watcher_ok']}  harry_hemp_ok={res['harry_hemp_ok']}  "
              f"duur={dt:.1f}s  inbox_open_items={res['inbox_items']}")
        for k in TARGETS:
            g = res["gaps"].get(k, {})
            tag = ""
            if g.get("emitted") is True and (begin.get(k, {}).get("emitted") in (None, False)):
                tag = "← EERSTE EMIT"
            elif g.get("emitted") is True and (begin.get(k, {}).get("emitted") is True):
                tag = "onderdrukt (emitted stond al True)"
            print(f"   {k:30s}  count={g.get('count','?'):>3}  emitted={g.get('emitted')}  {tag}")
        print()
        begin = res["gaps"]


if __name__ == "__main__":
    main()
