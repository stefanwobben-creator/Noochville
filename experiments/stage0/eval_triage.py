#!/usr/bin/env python3
"""Stage 0 — meet of een klein lokaal model de menselijke keep/dismiss-beslissing reproduceert.

Ruis is de dure fout, dus het model draait als conservatief wegveeg-filter vóór de Gemini-ladder.
De vraag die telt is NIET accuracy, maar: **veegt het model bij hetzelfde weegvolume schoner weg
dan het lexicale filter dat we al hebben?**

Drie ontwerpkeuzes volgen daaruit:

1. **Het model scoort, het script beslist.** De prompt is neutraal ("rate 0-100 how worth keeping");
   het conservatisme zit puur in waar de dismiss-drempel ligt. Eén threshold-sweep vervangt het
   herschrijven van de prompt per run.
2. **De baseline dismisst ook.** `mission.strategie_relevantie` (de lexicale STRATEGIE_THEMAS-
   heuristiek) krijgt dezelfde dismiss-actie, en wordt vergeleken bij GELIJKE offload — niet bij
   gelijke drempel. Alleen dan meet je of het model iets toevoegt.
3. **Elke precision krijgt een Wilson-95%-CI.** Bij ~48 dismisses (20% van 240) is een punt-
   schatting van 90% niet scherp genoeg om als poort te dienen. Lees de eerste run als richting.

Gebruik (op de inference-box, met Ollama):
    ollama pull qwen2.5:3b-instruct
    OLLAMA_MODEL=qwen2.5:3b-instruct python3 experiments/stage0/eval_triage.py

Zonder Ollama — alleen de lexicale baseline + de sweep-machinerie (voor lokaal sanity-checken):
    NO_LLM=1 python3 experiments/stage0/eval_triage.py

Met de Gemini-ladder erbij als plafond-referentie (kost quota, zelfde 0-100 prompt):
    WITH_GEMINI=1 python3 experiments/stage0/eval_triage.py

Eval-set: `evalset.jsonl` als die bestaat (gebouwd door build_evalset.py uit de volledige radar),
anders valt het script terug op `data/live_radar.json` — goedgekeurd=keep, afgewezen=dismiss.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# Reference, don't copy: de missietekst leeft op één gezaghebbende plek (mission.py) en wordt
# hier geïmporteerd, niet overgetypt. Verandert de missie, dan verandert deze prompt mee.
from nooch_village.mission import ANCHOR_PURPOSE, strategie_relevantie  # noqa: E402
# Het Wilson-interval leeft op één plek (nooch_village/stats.py) — dezelfde poort-statistiek die
# de Founder Flow gebruikt om een taak te promoveren. Reference, don't copy.
from nooch_village.stats import Z95 as Z, wilson  # noqa: E402,F401

EVALSET = os.environ.get("EVALSET", os.path.join(os.path.dirname(os.path.abspath(__file__)), "evalset.jsonl"))
RADAR = os.environ.get("RADAR", os.path.join(_REPO, "data", "live_radar.json"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b-instruct")
OFFLOAD_POINTS = [float(x) for x in os.environ.get("OFFLOADS", "0.10,0.20,0.30").split(",")]

# ── De prompt is bewust NEUTRAAL. Geen "when in doubt, keep" — dat duwde het model naar keep
# terwijl we offload eisen, en dat is tegen elkaar in optimaliseren. Het model rangschikt; de
# drempel hieronder maakt het conservatief. ───────────────────────────────────────────────────
_TASK = (
    "A radar surfaces external signals (trends, competitors, materials, news) for this brand. "
    "A human then KEEPS the ones worth acting on and DISMISSES the rest. Many signals look "
    "topically related but are still not worth keeping.\n\n"
    "Rate how worth-keeping this signal is on a scale of 0 to 100, where 0 means certainly not "
    "worth keeping and 100 means certainly worth keeping. Use the full range; do not cluster "
    "your answers around one value.\n\n"
)


def prompt_for(row: dict) -> str:
    return (
        f"{ANCHOR_PURPOSE}\n\n"
        f"{_TASK}"
        f"FEED: {row['feed']}\n"
        f"SIGNAL: {row['content']}\n"
        f"WHY IT WAS SURFACED: {row['rationale']}\n\n"
        'Answer ONLY with JSON: {"score": <integer 0-100>}'
    )


# ── Eval-set laden ────────────────────────────────────────────────────────────────────────────
def load_rows() -> list[dict]:
    """evalset.jsonl als die er is, anders afgeleid uit de live radar (goedgekeurd/afgewezen)."""
    if os.path.exists(EVALSET):
        rows = [json.loads(line) for line in open(EVALSET, encoding="utf-8") if line.strip()]
        print(f"eval-set: {EVALSET} ({len(rows)} items)")
        return rows
    raw = json.load(open(RADAR, encoding="utf-8"))
    items = raw.get("items", raw)
    items = list(items.values()) if isinstance(items, dict) else items
    rows = [
        {"feed": it.get("feed", ""), "content": it.get("content", ""),
         "rationale": it.get("rationale", ""),
         "label": 1 if it.get("status") == "goedgekeurd" else 0}
        for it in items
        if it.get("status") in ("goedgekeurd", "afgewezen")
    ]
    print(f"eval-set: {EVALSET} bestaat niet → afgeleid uit {RADAR} ({len(rows)} items)")
    return rows


# ── Model-aanroep ─────────────────────────────────────────────────────────────────────────────
def ask_ollama(prompt: str) -> str:
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "format": "json", "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["response"]


def parse_score(raw) -> float | None:
    """Haal een 0-100 keep-waardigheid uit het antwoord. None = onbruikbaar (telt als skipped)."""
    if raw is None:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw))
    m = re.search(r'"(?:score|keep_worthiness|rating)"\s*:\s*"?(-?\d+(?:\.\d+)?)"?', s, re.I)
    if not m:
        m = re.search(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)(?![\w.])", s)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    return min(100.0, max(0.0, val))


def gemini_score(prompt: str) -> float | None:
    from nooch_village.llm import reason
    return parse_score(reason(prompt, max_tokens=40, json_mode=True, call_site="stage0_eval"))


# ── Statistiek ────────────────────────────────────────────────────────────────────────────────
def dismiss_precision_at_k(scores: list[float], labels: list[int], k: int) -> tuple[float, int]:
    """Veeg de k laagst-scorende items weg; geef (verwacht aantal terecht weggeveegd, k).

    Belangrijk bij een grove scorer: de lexicale score is een integer 0-7, dus er zijn dikke
    gelijkspel-groepen. Welke items je binnen zo'n groep pakt is arbitrair, dus we rekenen de
    VERWACHTING over de groep uit (k_rest * dismisses / groepsgrootte) in plaats van een
    willekeurige ordening te laten meebeslissen. Voor een fijne scorer (0-100) is dit gelijk
    aan gewoon de onderste k nemen.
    """
    k = max(0, min(k, len(scores)))
    if k == 0:
        return (0.0, 0)
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    expected_tn, remaining, idx = 0.0, k, 0
    while remaining > 0 and idx < len(order):
        j = idx
        while j < len(order) and scores[order[j]] == scores[order[idx]]:
            j += 1
        group = order[idx:j]
        true_dismiss = sum(1 for i in group if labels[i] == 0)
        take = min(remaining, len(group))
        expected_tn += take * true_dismiss / len(group)
        remaining -= take
        idx = j
    return (expected_tn, k)


def report_at_offloads(name: str, scores: list[float], labels: list[int]) -> dict[float, float]:
    """Print dismiss-precision + Wilson-CI op de gevraagde offload-punten. Geeft {offload: precision}."""
    n = len(scores)
    out: dict[float, float] = {}
    print(f"\n  {name}")
    print(f"    {'offload':>8} {'weggeveegd':>11} {'dismiss-precision':>19} {'95%-CI (Wilson)':>20}")
    for target in OFFLOAD_POINTS:
        k = int(round(target * n))
        tn, k = dismiss_precision_at_k(scores, labels, k)
        if k == 0:
            continue
        prec = tn / k
        # Wilson eist hele successen; bij een gelijkspel-groep is `tn` een verwachting en dus
        # fractioneel. Dan ronden we voor het CI af en markeren dat met ~ — niet wegmoffelen.
        lo, hi = wilson(round(tn), k)
        approx = "~" if abs(tn - round(tn)) > 1e-9 else " "
        out[target] = prec
        print(f"    {k/n*100:7.1f}% {k:11d} {prec*100:18.1f}% "
              f"{approx}{'[%.1f%% – %.1f%%]' % (lo*100, hi*100):>19}")
    return out


def sweep(name: str, scores: list[float], labels: list[int]) -> None:
    """Volledige drempel-curve: bij welke score-drempel haal je welke offload/precision?"""
    n = len(scores)
    print(f"\n  drempel-sweep — {name}")
    print(f"    {'drempel':>8} {'offload':>8} {'dismiss-prec':>13} {'verloren kansen':>16}")
    seen = set()
    for t in sorted(set(scores)):
        k = sum(1 for s in scores if s < t)
        if k == 0 or k in seen:
            continue
        seen.add(k)
        tn = sum(1 for s, y in zip(scores, labels) if s < t and y == 0)
        fn = k - tn
        keeps = sum(1 for y in labels if y == 1)
        print(f"    {t:8.0f} {k/n*100:7.1f}% {tn/k*100:12.1f}% "
              f"{(fn/keeps*100 if keeps else 0):15.1f}%")


def summarise(name: str, scores: list[float | None], labels: list[int],
              lex_scores: list[float]) -> None:
    """Kern van de meting: model versus lexicaal filter bij GELIJKE offload."""
    pairs = [(s, y, lx) for s, y, lx in zip(scores, labels, lex_scores) if s is not None]
    skipped = len(labels) - len(pairs)
    if not pairs:
        print(f"\n=== {name} === geen geldige antwoorden ({skipped} skipped)")
        return
    ms = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    ls = [p[2] for p in pairs]
    base = sum(1 for y in ys if y == 0) / len(ys)

    print(f"\n{'=' * 78}\n=== {name} ===")
    print(f"  N geldig={len(ys)} (skipped={skipped})  |  aandeel echte dismiss={base*100:.1f}%")
    print(f"  score-spreiding: min={min(ms):.0f} p50={sorted(ms)[len(ms)//2]:.0f} max={max(ms):.0f} "
          f"unieke waarden={len(set(ms))}")
    if len(set(ms)) < 4:
        print("  LET OP: het model clustert op enkele waarden — een sweep heeft dan weinig te kiezen.")

    print("\n  -- de beslissende vergelijking: bij GELIJKE offload, wie veegt schoner weg? --")
    print(f"     (blind wegvegen levert per definitie {base*100:.1f}% precision — dát is de vloer)")
    mp = report_at_offloads(f"model: {name}", ms, ys)
    lp = report_at_offloads("lexicaal: mission.strategie_relevantie", ls, ys)

    print("\n  -- verdict per offload-punt --")
    for target in OFFLOAD_POINTS:
        if target not in mp or target not in lp:
            continue
        delta = (mp[target] - lp[target]) * 100
        winner = "model" if delta > 0 else ("gelijk" if abs(delta) < 1e-9 else "lexicaal")
        vs_floor = (mp[target] - base) * 100
        print(f"    offload {target*100:.0f}%: model {mp[target]*100:.1f}% vs lexicaal "
              f"{lp[target]*100:.1f}%  → {winner} ({delta:+.1f}pp), "
              f"t.o.v. blinde vloer {vs_floor:+.1f}pp")

    sweep(name, ms, ys)
    print("\n  Lees dit als RICHTING, niet als poort: bij deze N is een CI van ±8pp normaal. "
          "Promoveren pas als de ondergrens van het CI boven de lexicale bovengrens ligt.")


# ── Main ──────────────────────────────────────────────────────────────────────────────────────
def main() -> None:
    rows = load_rows()
    limit = int(os.environ.get("LIMIT", "0")) or len(rows)
    rows = rows[:limit]
    labels = [r["label"] for r in rows]
    lex = [float(strategie_relevantie(f"{r['content']} {r['rationale']}")[0]) for r in rows]

    print(f"model: {MODEL}  |  {OLLAMA_URL}  |  offload-punten: "
          f"{', '.join(f'{p*100:.0f}%' for p in OFFLOAD_POINTS)}")

    if os.environ.get("NO_LLM"):
        print("\nNO_LLM=1 → alleen de lexicale baseline (sanity-check van de machinerie).")
        summarise("lexicaal (als stand-in voor het model)", list(lex), labels, lex)
        return

    scores: list[float | None] = []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        try:
            scores.append(parse_score(ask_ollama(prompt_for(r))))
        except Exception as e:
            print(f"  [{i}] fout: {e}")
            scores.append(None)
        if i % 20 == 0:
            print(f"  {i}/{len(rows)}  ({(time.time() - t0) / i:.1f}s/item)")
    summarise(f"Ollama {MODEL}", scores, labels, lex)

    if os.environ.get("WITH_GEMINI"):
        gs: list[float | None] = []
        for i, r in enumerate(rows, 1):
            try:
                gs.append(gemini_score(prompt_for(r)))
            except Exception as e:
                print(f"  gemini[{i}] fout: {e}")
                gs.append(None)
            time.sleep(float(os.environ.get("GEMINI_SLEEP", "1.0")))
        summarise("Gemini (ladder-plafond)", gs, labels, lex)


if __name__ == "__main__":
    main()
