#!/usr/bin/env python3
"""kennis_herformuleer — herschrijf de bestaande laag-2 inzichtkaartjes volgens de nieuwe spelregel
(founder 23 jul): zelfstandig leesbaar, kort en scherp, eenvoudige taal (geen jargon).

GEBATCHT: meerdere kaartjes per LLM-call, want de gratis Gemini-tier geeft maar ~20 generate-verzoeken
PER DAG per model. Met een batch van 6 doe je 21 kaartjes in ~4 calls i.p.v. 21 — ruim binnen de dagcap.

Volledig omkeerbaar (KennisbankStore.reformulate bumpt de versie, oude tekst gaat in `history`) en
idempotent: een al-herschreven kaartje (history-entry met by='herformuleer') wordt overgeslagen, dus je
kunt hem gerust nog eens draaien.

DRY BY DEFAULT: zonder 'apply' toont hij per kaartje VOOR → NA, wijzigt niets. Met 'apply' voert hij door.

Draaien op de server ALS DE APP-GEBRUIKER, met de .env geladen:
    cd /opt/noochville
    sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_herformuleer.py'          # dry
    sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_herformuleer.py apply'    # echt
Herstart daarna de village + cockpit (de daemon houdt kennisbank.json in geheugen).
"""
import os
import re
import sys

from nooch_village.kennisbank import KennisbankStore
from nooch_village.llm import reason

DATA = os.getenv("NOOCH_DATA_DIR", "data")
BATCH = int(os.getenv("KB_HERFORMULEER_BATCH", "6"))
LADDER = os.getenv("LLM_KB_HERFORMULEER_LADDER",
                   "gemini:gemini-2.5-flash-lite,gemini:gemini-2.5-flash,"
                   "mistral:mistral-small-latest,anthropic:claude-haiku-4-5-20251001")

_REGELS = (
    "Je herschrijft kennis-inzichten volgens strikte regels, ZONDER de betekenis te veranderen en "
    "ZONDER nieuwe feiten te verzinnen. Je maakt ze alleen beter leesbaar.\n"
    "REGELS per inzicht:\n"
    "- ZELFSTANDIG LEESBAAR: iemand zonder voorkennis (of de schrijver een jaar later) snapt uit de "
    "CLAIM alléén waar het over gaat. Benoem WAT het onderwerp of de speler IS in één adem — niet "
    "'X's additief' maar 'X's organische additief dat gewoon plastic door bacteriën laat afbreken'.\n"
    "- KORT EN SCHERP: één zelfstandig statement, geen verhaal, geen uitleg-alinea.\n"
    "- EENVOUDIGE, ALLEDAAGSE TAAL: schrijf alsof je het uitlegt aan een slimme vriend die geen "
    "vakspecialist is. Vermijd jargon (dus niet 'oxidatieve degradatie', 'mineraliseren', "
    "'polyolefine', 'microbiologisch'); moet een vakterm echt, zeg hem dan meteen in gewone woorden.\n")


def bouw_batch_prompt(kaarten: list[dict]) -> str:
    invoer = "\n\n".join(
        f"[[ID: {k['id']}]]\nCLAIM: {k.get('title', '')}\n"
        f"REFRAME: {k.get('reframe', '')}\nFALSIFIER: {k.get('falsifier', '')}"
        for k in kaarten)
    return (
        _REGELS +
        "\nHerschrijf ELK inzicht hieronder. Geef per inzicht EXACT dit blok terug, in dezelfde "
        "volgorde, en niets ertussen:\n"
        "[[ID: <de id>]]\nCLAIM: <herschreven>\nREFRAME: <herschreven>\nFALSIFIER: <herschreven>\n\n"
        f"INZICHTEN:\n{invoer}")


def _veld(body: str, naam: str) -> str:
    m = re.search(rf"^{naam}:\s*(.+)$", body, re.I | re.M)
    return m.group(1).strip() if m else ""


def parse_batch(out: str | None) -> dict:
    """LLM-output → {id: {title, reframe, falsifier}}. Split op de [[ID: ...]]-markers; fail-soft."""
    res: dict = {}
    if not out:
        return res
    delen = re.split(r"\[\[ID:\s*(kb_[0-9a-fA-F]+)\s*\]\]", out)
    for i in range(1, len(delen) - 1, 2):
        iid, body = delen[i], delen[i + 1]
        res[iid] = {"title": _veld(body, "CLAIM"),
                    "reframe": _veld(body, "REFRAME"),
                    "falsifier": _veld(body, "FALSIFIER")}
    return res


def _al_gedaan(k: dict) -> bool:
    return any((h.get("by") == "herformuleer") for h in (k.get("history") or []))


def main(argv) -> int:
    apply = "apply" in argv
    store = KennisbankStore(f"{DATA}/kennisbank.json")
    alle = store.all()
    todo = [k for k in alle if not _al_gedaan(k)]
    algedaan = len(alle) - len(todo)
    print(f"=== inzicht-herformulering [{'TOEPASSEN' if apply else 'DROOG'}] — {len(alle)} kaartjes "
          f"({algedaan} al eerder gedaan, {len(todo)} te doen, batch={BATCH}) ===\n")

    veranderd = mislukt = 0
    for i in range(0, len(todo), BATCH):
        groep = todo[i:i + BATCH]
        out = reason(bouw_batch_prompt(groep), ladder=LADDER, max_tokens=1800,
                     call_site="kb_herformuleer")
        parsed = parse_batch(out)
        for k in groep:
            iid = k.get("id")
            nieuw = parsed.get(iid) or {}
            n_title = (nieuw.get("title") or "").strip()
            n_ref = (nieuw.get("reframe") or "").strip()
            n_fal = (nieuw.get("falsifier") or "").strip()
            if not n_title:
                print(f"⚠ {iid}: geen bruikbare herschrijving (quota of onparseerbaar) — overgeslagen")
                mislukt += 1
                continue
            print(f"— {iid} —")
            print(f"  VOOR claim : {(k.get('title') or '')[:150]}")
            print(f"  NA   claim : {n_title[:150]}")
            if n_ref:
                print(f"  NA   reframe  : {n_ref[:120]}")
            if n_fal:
                print(f"  NA   falsifier: {n_fal[:120]}")
            print()
            if apply:
                store.reformulate(iid, title=n_title, reframe=n_ref, falsifier=n_fal, by="herformuleer")
            veranderd += 1

    print(f"=== klaar. {veranderd} herschreven, {algedaan} al eerder gedaan, {mislukt} overgeslagen "
          f"(meestal quota) ==="
          + ("" if apply else "  (droog — draai met 'apply' om door te voeren)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
