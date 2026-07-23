#!/usr/bin/env python3
"""kennis_herformuleer — herschrijf de bestaande laag-2 inzichtkaartjes volgens de nieuwe spelregel
(founder 23 jul): zelfstandig leesbaar, kort en scherp, eenvoudige taal (geen jargon).

Voor elk standpunt in kennisbank.json vraagt dit de LLM om de claim (title), reframe en falsifier te
HERSCHRIJVEN zonder de betekenis te veranderen. Volledig omkeerbaar: KennisbankStore.reformulate bumpt
de versie en bewaart de vorige in `history`. Idempotent-vriendelijk: een kaartje dat al aan de regel
voldoet verandert nauwelijks.

DRY BY DEFAULT: zonder 'apply' toont hij per kaartje het VOOR → NA, wijzigt niets. Met 'apply' voert hij
de herformulering door.

Draaien op de server ALS DE APP-GEBRUIKER, met de .env geladen (sleutel + modelnaam):
    cd /opt/noochville
    sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_herformuleer.py'          # dry
    sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_herformuleer.py apply'    # echt
Herstart daarna de village + cockpit (de daemon houdt kennisbank.json in geheugen).
"""
import os
import sys

from nooch_village.kennisbank import KennisbankStore, parse_blok
from nooch_village.llm import reason

DATA = os.getenv("NOOCH_DATA_DIR", "data")

# flash-lite EERST: gemini-2.5-flash heeft op de gratis tier maar 20 verzoeken PER DAG (te weinig voor
# 21 kaartjes), flash-lite heeft een veel ruimere dagquota. flash blijft als kwaliteits-fallback erachter.
LADDER = os.getenv("LLM_KB_HERFORMULEER_LADDER",
                   "gemini:gemini-2.5-flash-lite,gemini:gemini-2.5-flash,"
                   "mistral:mistral-small-latest,anthropic:claude-haiku-4-5-20251001")


def bouw_prompt(k: dict) -> str:
    return (
        "Herschrijf dit inzicht volgens strikte regels, ZONDER de betekenis te veranderen en ZONDER "
        "nieuwe feiten te verzinnen. Je maakt het alleen beter leesbaar.\n\n"
        "REGELS:\n"
        "- ZELFSTANDIG LEESBAAR: iemand zonder voorkennis (of de schrijver een jaar later) snapt uit de "
        "CLAIM alléén waar het over gaat. Benoem WAT het onderwerp of de speler IS in één adem — niet "
        "'X's additief' maar 'X's organische additief dat gewoon plastic door bacteriën laat afbreken'.\n"
        "- KORT EN SCHERP: één zelfstandig statement, geen verhaal, geen uitleg-alinea.\n"
        "- EENVOUDIGE, ALLEDAAGSE TAAL: schrijf alsof je het uitlegt aan een slimme vriend die geen "
        "vakspecialist is. Vermijd jargon (dus niet 'oxidatieve degradatie', 'mineraliseren', "
        "'polyolefine', 'microbiologisch'); moet een vakterm echt, zeg hem dan meteen in gewone woorden.\n\n"
        f"HUIDIG INZICHT{(' (onderwerp: ' + k.get('subject', '') + ')') if k.get('subject') else ''}:\n"
        f"CLAIM: {k.get('title', '')}\n"
        f"REFRAME: {k.get('reframe', '')}\n"
        f"FALSIFIER: {k.get('falsifier', '')}\n\n"
        "Geef UITSLUITEND dit blok (geen uitleg eromheen):\n"
        "=== INZICHT ===\n"
        "TITEL: <de herschreven claim: zelfstandig leesbaar, kort en scherp, eenvoudige taal>\n"
        "REFRAME: <herschreven, 1 zin, eenvoudige taal>\n"
        "FALSIFIER: <herschreven, concreet en in eenvoudige taal>\n"
        "=== EINDE ===")


def main(argv) -> int:
    apply = "apply" in argv
    store = KennisbankStore(f"{DATA}/kennisbank.json")
    kaarten = store.all()
    print(f"=== inzicht-herformulering [{'TOEPASSEN' if apply else 'DROOG'}] — {len(kaarten)} kaartjes ===\n")

    veranderd = mislukt = ongewijzigd = 0
    for k in kaarten:
        iid = k.get("id")
        out = reason(bouw_prompt(k), ladder=LADDER, max_tokens=500, call_site="kb_herformuleer")
        nieuw = parse_blok(out or "")
        n_title = nieuw.get("title") or ""      # TITEL-regel = de herschreven claim
        n_ref = nieuw.get("reframe") or ""
        n_fal = nieuw.get("falsifier") or ""
        if not n_title:
            print(f"⚠ {iid}: geen bruikbare herschrijving (LLM weg of onparseerbaar) — overgeslagen\n")
            mislukt += 1
            continue
        if (n_title.strip() == (k.get("title") or "").strip()
                and n_ref.strip() == (k.get("reframe") or "").strip()
                and n_fal.strip() == (k.get("falsifier") or "").strip()):
            ongewijzigd += 1
            continue
        print(f"— {iid} —")
        print(f"  VOOR claim : {k.get('title', '')[:150]}")
        print(f"  NA   claim : {n_title[:150]}")
        if n_ref:
            print(f"  NA   reframe  : {n_ref[:120]}")
        if n_fal:
            print(f"  NA   falsifier: {n_fal[:120]}")
        print()
        if apply:
            store.reformulate(iid, title=n_title, reframe=n_ref, falsifier=n_fal, by="herformuleer")
        veranderd += 1

    print(f"=== klaar. {veranderd} herschreven, {ongewijzigd} al goed, {mislukt} overgeslagen ==="
          + ("" if apply else "  (droog — draai met 'apply' om door te voeren)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
