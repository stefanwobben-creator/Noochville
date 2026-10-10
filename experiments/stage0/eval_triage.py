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
3. **Elke precision krijgt een Wilson-95%-CI.** Bij ~90 dismisses (20% van 450) is een punt-
   schatting van 90% niet scherp genoeg om als poort te dienen. Lees een run als richting.

DE INVOER IS DE RUWE KOP (vervolg, 10 oktober 2026). `content` én `rationale` in de gelabelde set
zijn geschreven door de Gemini-ladder (`news_distill`, vóór 19 september 2026). Een filter dat vóór
die ladder draait, ziet alleen feed, domein en kop — die haalt `haal_titels.py` terug via de link
(lokaal, `titels.jsonl`). Runs op de modeltekst blijven in het rapport als "lekkage / bovengrens".

Per model twee eerlijke prompts: de oude 0-100 (basis) en ja/nee met de kans op "ja" uit de
logprobs (fijnere schaal). Plus per run een combinatie met het lexicale filter (rang-gemiddelde,
weging alleen op de afstel-set gekozen).

Elke run schrijft (gitignored — interne radartekst):
    rapport_<datum>_vervolg.md   alle runs naast elkaar, ook zonder Legal & Green Claims, per feed
    misses_<datum>_vervolg.md    per run de goedgekeurde items onder de drempel

Regels die je niet stilletjes moet omdraaien:
* **Holdout:** de rijen in `holdout_ids.txt` blijven buiten het afstellen, en worden ÉÉN keer
  gemeten — alleen met `HOLDOUT=1`, voor de ene configuratie die op de afstel-set het beste is.
* **EXCLUDE_FEEDS** (standaard `Projecten`) haalt rijen uit de hele meting, ook uit `WITH_GEMINI=1`.
* **FILTER_FEEDS** (komma-lijst, leeg = alle) bepaalt op welke feeds het filter mag draaien.
* **Modellen uit `ollama list`** onder min(16 GB, RAM − 4 GB).

Gebruik (lokaal, Ollama op localhost:11434):
    RADAR=<kopie prod radar.json> python3 experiments/stage0/haal_titels.py
    python3 experiments/stage0/eval_triage.py                 # afstel-set, alle passende modellen
    HOLDOUT=1 python3 experiments/stage0/eval_triage.py       # de eindrun, één holdout-meting
    OLLAMA_MODELS=gemma2:2b FILTER_FEEDS="Material Innovation" python3 experiments/stage0/eval_triage.py

Scores worden gecachet in `scores_cache.jsonl` (per model + exacte prompt).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

_HIER = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HIER))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# Reference, don't copy: de missietekst leeft op één gezaghebbende plek (mission.py) en wordt
# hier geïmporteerd, niet overgetypt. Verandert de missie, dan verandert deze prompt mee.
from nooch_village.mission import ANCHOR_PURPOSE, strategie_relevantie  # noqa: E402
# Het Wilson-interval leeft op één plek (nooch_village/stats.py) — dezelfde poort-statistiek die
# de Founder Flow gebruikt om een taak te promoveren. Reference, don't copy.
from nooch_village.stats import Z95 as Z, wilson  # noqa: E402,F401

_env = os.environ.get
EVALSET = _env("EVALSET", os.path.join(_HIER, "evalset.jsonl"))
RADAR = _env("RADAR", os.path.join(_REPO, "data", "live_radar.json"))
OLLAMA_BASE = _env("OLLAMA_BASE", "http://localhost:11434")
OFFLOAD_POINTS = [float(x) for x in _env("OFFLOADS", "0.10,0.20,0.30").split(",")]
#: Het werkpunt: hier wordt de drempel gekozen, de holdout gemeten en de misses-lijst gemaakt.
WERKPUNT = float(_env("WERKPUNT", "0.20"))
SEED = int(_env("SEED", "20261010"))
HOLDOUT_N = int(_env("HOLDOUT_N", "100"))
HOLDOUT_FILE = _env("HOLDOUT_FILE", os.path.join(_HIER, "holdout_ids.txt"))
CACHE_FILE = _env("CACHE_FILE", os.path.join(_HIER, "scores_cache.jsonl"))
EXCLUDE_FEEDS = [f.strip() for f in _env("EXCLUDE_FEEDS", "Projecten").split(",") if f.strip()]
STEEKPROEF_N = 30
#: Een model mag hoogstens zo groot zijn — en past daarnaast in het geheugen min deze marge.
MAX_MODEL_BYTES = 16 * 1024 ** 3
RAM_MARGE_BYTES = 4 * 1024 ** 3

# ── De prompt is bewust NEUTRAAL. Geen "when in doubt, keep" — dat duwde het model naar keep
# terwijl we offload eisen, en dat is tegen elkaar in optimaliseren. Het model rangschikt; de
# drempel maakt het conservatief. ──────────────────────────────────────────────────────────────
_TASK = (
    "A radar surfaces external signals (trends, competitors, materials, news) for this brand. "
    "A human then KEEPS the ones worth acting on and DISMISSES the rest. Many signals look "
    "topically related but are still not worth keeping.\n\n"
    "Rate how worth-keeping this signal is on a scale of 0 to 100, where 0 means certainly not "
    "worth keeping and 100 means certainly worth keeping. Use the full range; do not cluster "
    "your answers around one value.\n\n"
)


def prompt_for(row: dict, met_rationale: bool = True) -> str:
    """De prompt. `met_rationale=False` laat de regel weg waarom de radar het signaal opwierp — de
    toets of het model zelf oordeelt of alleen dat eerdere oordeel napraat."""
    waarom = f"WHY IT WAS SURFACED: {row['rationale']}\n" if met_rationale else ""
    return (
        f"{ANCHOR_PURPOSE}\n\n"
        f"{_TASK}"
        f"FEED: {row['feed']}\n"
        f"SIGNAL: {row['content']}\n"
        f"{waarom}\n"
        'Answer ONLY with JSON: {"score": <integer 0-100>}'
    )


#: Het eerlijke ja/nee-format (stap 2, 10 oktober 2026): één woord, en de score is de kans op "ja"
#: uit de logprobs — een fijne schaal i.p.v. de 8 à 13 waarden van de 0-100-prompt.
_JANEE = ("A radar surfaces external signals (trends, competitors, materials, news) for this brand. "
          "A human then KEEPS the ones worth acting on and DISMISSES the rest. Many signals look "
          "topically related but are still not worth keeping.\n\n")


def _signaal(row: dict, t: dict) -> str:
    """Wat een filter VÓÓR de Gemini-ladder ziet: de feed, het domein en de kop van het artikel —
    niet de `content` en `rationale` die de ladder zelf schreef (zie `haal_titels.py`)."""
    return f"FEED: {row['feed']}\nSOURCE: {t.get('source', '')}\nHEADLINE: {t['titel']}\n"


def prompt_titel(row: dict, t: dict) -> str:
    """De oude 0-100-prompt, maar op de eerlijke invoer: de basis om het ja/nee-verschil aan af te zetten."""
    return (f"{ANCHOR_PURPOSE}\n\n{_TASK}{_signaal(row, t)}\n"
            'Answer ONLY with JSON: {"score": <integer 0-100>}')


def prompt_janee(row: dict, t: dict) -> str:
    return (f"{ANCHOR_PURPOSE}\n\n{_JANEE}{_signaal(row, t)}\n"
            "Is this signal worth keeping? Answer with one word: Yes or No.")


# ── Eval-set laden ────────────────────────────────────────────────────────────────────────────
def row_id(row: dict) -> str:
    """Een stabiel id uit feed + content. De eval-set draagt geen radar-id (alleen feed, content,
    rationale, label), en hetzelfde signaal moet run na run hetzelfde id houden."""
    return hashlib.sha1(f"{row['feed']}\x00{row['content']}".encode("utf-8")).hexdigest()[:12]


def load_rows() -> list[dict]:
    """evalset.jsonl als die er is, anders afgeleid uit de live radar (goedgekeurd/afgewezen)."""
    if os.path.exists(EVALSET):
        rows = [json.loads(line) for line in open(EVALSET, encoding="utf-8") if line.strip()]
        print(f"eval-set: {EVALSET} ({len(rows)} items)")
    else:
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
    for r in rows:
        r["id"] = row_id(r)
    return rows


def splits(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(afstellen, holdout). De holdout-ids komen uit `HOLDOUT_FILE` als die bestaat; anders wordt
    met een vaste seed getrokken en weggeschreven. Een id uit het bestand dat niet (meer) in de set
    zit, valt gewoon weg — de holdout wordt nooit stilletjes aangevuld."""
    if os.path.exists(HOLDOUT_FILE):
        ids = {l.strip() for l in open(HOLDOUT_FILE, encoding="utf-8") if l.strip()}
    else:
        alle = sorted(r["id"] for r in rows)
        ids = set(random.Random(SEED).sample(alle, min(HOLDOUT_N, len(alle))))
        with open(HOLDOUT_FILE, "w", encoding="utf-8") as f:
            f.write("".join(f"{i}\n" for i in sorted(ids)))
    return [r for r in rows if r["id"] not in ids], [r for r in rows if r["id"] in ids]


# ── Modellen ──────────────────────────────────────────────────────────────────────────────────
def ram_bytes() -> int:
    try:
        return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                  text=True, check=True).stdout.strip())
    except Exception:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def modellen() -> tuple[list[tuple[str, int]], int, list[tuple[str, int]]]:
    """(passend, grens, te_groot) uit `ollama list` (de /api/tags van dezelfde Ollama).

    De grens is de kleinste van 16 GB en het RAM min 4 GB marge (het systeem en de cockpit draaien
    ernaast). `OLLAMA_MODELS=a,b` beperkt de keuze tot die modellen."""
    with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=10) as r:
        tags = json.loads(r.read())["models"]
    grens = min(MAX_MODEL_BYTES, ram_bytes() - RAM_MARGE_BYTES)
    alle = sorted((m["name"], int(m.get("size", 0))) for m in tags)
    keuze = [m.strip() for m in _env("OLLAMA_MODELS", "").split(",") if m.strip()]
    if keuze:
        alle = [m for m in alle if m[0] in keuze]
    return [m for m in alle if m[1] < grens], grens, [m for m in alle if m[1] >= grens]


# ── Model-aanroep + cache ─────────────────────────────────────────────────────────────────────
def ask_ollama(prompt: str, model: str) -> str:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "format": "json", "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_BASE}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["response"]


def ask_janee(prompt: str, model: str) -> float | None:
    """100 × P(ja) uit de logprobs van het eerste antwoord-token (Ollama ≥ 0.12: `logprobs` +
    `top_logprobs`). Ja = 'yes', nee = 'no', hoofdletter- en spatie-ongevoelig; P(ja) wordt
    genormaliseerd over ja + nee. Staat geen van beide in de top: None (telt als skipped)."""
    import math
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "logprobs": True,
                       "top_logprobs": 10, "options": {"temperature": 0, "num_predict": 1}}).encode()
    req = urllib.request.Request(f"{OLLAMA_BASE}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        lp = json.loads(r.read()).get("logprobs") or []
    if not lp:
        return None
    ja = nee = 0.0
    for t in lp[0].get("top_logprobs") or []:
        w = str(t.get("token", "")).strip().lower()
        if w == "yes":
            ja += math.exp(t["logprob"])
        elif w == "no":
            nee += math.exp(t["logprob"])
    return 100 * ja / (ja + nee) if ja + nee > 0 else None


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


class Cache:
    """Scores per (model, exacte prompt). Een gewijzigde prompt is een nieuwe sleutel, dus een oude
    score kan nooit voor een nieuwe vraag doorgaan. Een None (fout) wordt niet bewaard."""

    def __init__(self, pad: str):
        self.pad, self.d = pad, {}
        if os.path.exists(pad):
            for line in open(pad, encoding="utf-8"):
                try:
                    e = json.loads(line)
                    self.d[e["k"]] = e["s"]
                except (ValueError, KeyError):
                    continue

    @staticmethod
    def sleutel(model: str, prompt: str) -> str:
        return f"{model}|{hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:16]}"

    def get(self, model: str, prompt: str):
        return self.d.get(self.sleutel(model, prompt))

    def put(self, model: str, prompt: str, score) -> None:
        if score is None:
            return
        k = self.sleutel(model, prompt)
        self.d[k] = score
        with open(self.pad, "a", encoding="utf-8") as f:
            f.write(json.dumps({"k": k, "s": score}) + "\n")


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


def at_offloads(scores: list[float], labels: list[int]) -> dict[float, dict]:
    """{offload: {k, prec, lo, hi, approx}} — dismiss-precision met Wilson-CI per offload-punt."""
    n, out = len(scores), {}
    for target in OFFLOAD_POINTS:
        k = int(round(target * n))
        tn, k = dismiss_precision_at_k(scores, labels, k)
        if k == 0:
            continue
        # Wilson eist hele successen; bij een gelijkspel-groep is `tn` een verwachting en dus
        # fractioneel. Dan ronden we voor het CI af en markeren dat met ~ — niet wegmoffelen.
        lo, hi = wilson(round(tn), k)
        out[target] = {"k": k, "prec": tn / k, "lo": lo, "hi": hi,
                       "approx": abs(tn - round(tn)) > 1e-9}
    return out


def drempel_voor(scores: list[float], target: float) -> float:
    """De score-drempel t (wegvegen = score < t) waarvan het aandeel weggeveegd het dichtst bij
    `target` ligt. Op de AFSTEL-set gekozen; de holdout krijgt hem ongewijzigd."""
    n = len(scores)
    kandidaten = sorted(set(scores)) + [max(scores) + 1]
    return min(kandidaten, key=lambda t: (abs(sum(1 for s in scores if s < t) - target * n), t))


def bij_drempel(scores: list[float], labels: list[int], t: float) -> dict:
    """Wat een vaste drempel doet: weggeveegd, precision + CI, en het aandeel keeps dat verloren gaat."""
    k = sum(1 for s in scores if s < t)
    tn = sum(1 for s, y in zip(scores, labels) if s < t and y == 0)
    keeps = sum(labels)
    lo, hi = wilson(tn, k) if k else (0.0, 0.0)
    return {"n": len(scores), "k": k, "offload": k / len(scores) if scores else 0.0,
            "prec": tn / k if k else None, "lo": lo, "hi": hi,
            "verloren": (k - tn) / keeps if keeps else 0.0, "verloren_n": k - tn}


def sweep_rijen(scores: list[float], labels: list[int]) -> list[tuple]:
    """Volledige drempel-curve: (drempel, offload, dismiss-precision, verloren kansen)."""
    n, keeps, uit, gezien = len(scores), sum(labels), [], set()
    for t in sorted(set(scores)):
        k = sum(1 for s in scores if s < t)
        if k == 0 or k in gezien:
            continue
        gezien.add(k)
        tn = sum(1 for s, y in zip(scores, labels) if s < t and y == 0)
        uit.append((t, k / n, tn / k, ((k - tn) / keeps) if keeps else 0.0))
    return uit


def kwantielen(xs: list[float]) -> str:
    s = sorted(xs)
    q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
    return f"{q(0.1):.0f} / {q(0.5):.0f} / {q(0.9):.0f}"


def spearman(a: list[float], b: list[float]) -> float | None:
    """Rangcorrelatie met gemiddelde rangen bij gelijkspel. None bij te weinig of constante data."""
    if len(a) < 3:
        return None

    def rang(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r, i = [0.0] * len(xs), 0
        while i < len(order):
            j = i
            while j < len(order) and xs[order[j]] == xs[order[i]]:
                j += 1
            for k in range(i, j):
                r[order[k]] = (i + j - 1) / 2
            i = j
        return r

    ra, rb = rang(a), rang(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else None


# ── Markdown ──────────────────────────────────────────────────────────────────────────────────
def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _tabel(kop: list[str], rijen: list[list]) -> list[str]:
    return (["| " + " | ".join(kop) + " |", "|" + "|".join("---" for _ in kop) + "|"]
            + ["| " + " | ".join(str(c) for c in r) + " |" for r in rijen])


def _cel(x: str, n: int = 220) -> str:
    """Tekst in een tabelcel: één regel, geen pipes, ingekort."""
    t = " ".join(str(x or "").split()).replace("|", "/")
    return t if len(t) <= n else t[:n - 1] + "…"


# ── Runs ──────────────────────────────────────────────────────────────────────────────────────
class Run:
    """Eén configuratie: model × prompt × invoer (of lexicaal, of een combinatie).

    `scores` = {rij-id: score} op de AFSTEL-rijen. De holdout wordt niet per run gescoord: die
    meten we één keer, voor de beste configuratie (`holdout_meting`).
    `lekkage` = de invoer kwam uit de Gemini-ladder (content/rationale) — een bovengrens, geen
    resultaat voor een filter dat vóór die ladder draait."""

    def __init__(self, naam: str, model: str, prompt: str, invoer: str, scores: dict,
                 seconden: float = 0.0, gevraagd: int = 0, lekkage: bool = False,
                 bouw=None, vraag=None, extra: dict | None = None):
        self.naam, self.model, self.prompt, self.invoer = naam, model, prompt, invoer
        self.scores, self.seconden, self.gevraagd, self.lekkage = scores, seconden, gevraagd, lekkage
        self.bouw, self.vraag, self.extra = bouw, vraag, extra or {}

    def op(self, rows: list[dict]) -> tuple[list[dict], list[float], list[int]]:
        paren = [(r, self.scores.get(r["id"])) for r in rows]
        paren = [(r, s) for r, s in paren if s is not None]
        return [r for r, _ in paren], [s for _, s in paren], [r["label"] for r, _ in paren]


def scoor(rows: list[dict], model: str, bouw, vraag, cache: Cache, label: str) -> tuple[dict, float, int]:
    """({id: score}, seconden, echt gevraagd). `bouw(row)` maakt de prompt, `vraag(prompt)` geeft
    een score of None. Gecachet per (model, exacte prompt)."""
    uit, t0, gevraagd = {}, time.time(), 0
    for i, r in enumerate(rows, 1):
        p = bouw(r)
        s = cache.get(model, p)
        if s is None:
            try:
                s = vraag(p)
            except Exception as e:
                print(f"  [{label} {i}] fout: {e}")
                s = None
            gevraagd += 1
            cache.put(model, p, s)
        uit[r["id"]] = s
        if i % 50 == 0:
            print(f"  {label}: {i}/{len(rows)} ({time.time() - t0:.0f}s)")
    return uit, time.time() - t0, gevraagd


def _cdf(ref: list[float]):
    """Score → percentiel-rang t.o.v. de AFSTEL-verdeling (gemiddelde rang bij gelijkspel). Zo
    blijft een drempel die op de afstel-set is gekozen ook op de holdout geldig."""
    s = sorted(ref)
    n = len(s)

    def f(x: float) -> float:
        import bisect
        lo, hi = bisect.bisect_left(s, x), bisect.bisect_right(s, x)
        return (lo + hi) / 2 / n
    return f


def combineer(model: Run, lex: Run, afstel: list[dict]) -> Run:
    """Rang-gemiddelde van modelscore en lexicale score: w·rang(model) + (1−w)·rang(lexicaal). De
    weging w ∈ {0, 0.1, …, 1} wordt ALLEEN op de afstel-set gekozen (beste precision bij het
    werkpunt). w=1 is het model alleen, w=0 het lexicale filter alleen."""
    _r, ms, _y = model.op(afstel)
    _r, ls, _y = lex.op(afstel)
    fm, fl = _cdf(ms), _cdf(ls)
    gedeeld = [r for r in afstel if model.scores.get(r["id"]) is not None
               and lex.scores.get(r["id"]) is not None]
    ys = [r["label"] for r in gedeeld]
    beste = None
    for w10 in range(11):
        w = w10 / 10
        sc = [w * fm(model.scores[r["id"]]) + (1 - w) * fl(lex.scores[r["id"]]) for r in gedeeld]
        tn, k = dismiss_precision_at_k(sc, ys, int(round(WERKPUNT * len(sc))))
        if k and (beste is None or tn / k > beste[0] + 1e-12):
            beste = (tn / k, w)
    w = beste[1] if beste else 1.0
    scores = {r["id"]: w * fm(model.scores[r["id"]]) + (1 - w) * fl(lex.scores[r["id"]]) for r in gedeeld}
    return Run(f"{model.naam} + lexicaal (w={w:.1f})", model.model, f"{model.prompt} + lexicaal",
               model.invoer, scores, extra={"w": w, "fm": fm, "fl": fl, "delen": (model, lex)})


# ── Rapport ───────────────────────────────────────────────────────────────────────────────────
def _werkpunt(run: Run, rows: list[dict]) -> dict | None:
    """Dismiss-precision bij precies WERKPUNT wegvegen (gelijkspel = verwachting over de groep),
    met Wilson-CI, plus wat een echte drempel op deze rijen doet en hoeveel unieke scores er zijn."""
    _r, ss, ys = run.op(rows)
    if not ss:
        return None
    k = int(round(WERKPUNT * len(ss)))
    tn, k = dismiss_precision_at_k(ss, ys, k)
    if not k:
        return None
    lo, hi = wilson(round(tn), k)
    t = drempel_voor(ss, WERKPUNT)
    echt = bij_drempel(ss, ys, t)
    return {"n": len(ss), "k": k, "prec": tn / k, "lo": lo, "hi": hi,
            "approx": abs(tn - round(tn)) > 1e-9, "uniek": len(set(ss)), "drempel": t,
            "echt_k": echt["k"], "echt_prec": echt["prec"], "vloer": 1 - sum(ys) / len(ys)}


def _kop_tabel(runs: list[Run], rows: list[dict], lex_titel: Run) -> list[str]:
    lw = _werkpunt(lex_titel, rows)
    rijen = []
    for run in runs:
        d = _werkpunt(run, rows)
        if d is None:
            continue
        rijen.append([
            run.naam + (" ⚠ lekkage / bovengrens" if run.lekkage else ""),
            run.prompt, run.invoer, d["n"], d["uniek"],
            f"{_pct(d['prec'])} {'~' if d['approx'] else ''}[{d['lo'] * 100:.0f}–{d['hi'] * 100:.0f}]",
            f"{(d['prec'] - d['vloer']) * 100:+.1f}pp",
            "" if lw is None or run is lex_titel else f"{(d['prec'] - lw['prec']) * 100:+.1f}pp",
            f"{d['echt_k']} ({d['echt_k'] / d['n'] * 100:.0f}%) · {_pct(d['echt_prec'])}",
            f"{run.seconden / 60:.1f} min" if run.seconden else ""])
    vloer = _werkpunt(lex_titel, rows)
    kop = ["run", "prompt", "invoer", "N", "unieke scores", f"precision @{WERKPUNT * 100:.0f}% [95%-CI]",
           "Δ blind", "Δ lexicaal (titel)", "echte drempel: weg · precision", "duur"]
    return (_tabel(kop, rijen)
            + ["", f"Blind wegvegen op deze rijen: {_pct(vloer['vloer']) if vloer else '—'}. "
               f"Lexicaal op de titel: {_pct(vloer['prec']) if vloer else '—'}. (Ter vergelijking, de "
               "eerste run op alle 450 rijen en de modeltekst: blind 50,2%, lexicaal 61,5%.)", ""])


def rapport(runs: list[Run], lex_titel: Run, afstel: list[dict], meta: dict, holdout: dict | None) -> str:
    L = [f"# Stage 0 — triage-evaluatie (vervolg), {meta['datum']}", ""]
    L += [f"- Eval-set: {meta['n_totaal']} rijen; uitgesloten feeds: "
          f"{', '.join(f'{f} ({n})' for f, n in meta['uitgesloten'].items())}.",
          f"- Eerlijke invoer = feed + domein + **ruwe kop** (`haal_titels.py`): {meta['met_titel']} "
          f"van {meta['in_meting']} rijen hebben er een; de rest valt weg ({meta['zonder_titel']}).",
          f"- Afstel-set met titel: {len(afstel)} rijen. FILTER_FEEDS: {', '.join(meta['filter_feeds'])}.",
          f"- Modellen: {', '.join(f'{m} ({b / 1024 ** 3:.1f} GB)' for m, b in meta['modellen'])}; "
          f"grens {meta['grens'] / 1024 ** 3:.1f} GB.",
          f"- Totale looptijd: {meta['duur'] / 60:.1f} min ({meta['gevraagd']} model-aanroepen; de "
          "rest uit de cache).", ""]
    L += ["## Waarom de invoer veranderde", "",
          "`rationale` én `content` in de gelabelde set zijn geschreven door de Gemini-ladder "
          "(`news_distill`, vóór 19 september 2026). Een filter dat vóór die ladder draait, ziet "
          "alleen de kop, het domein en de feed. De runs op `content`/`rationale` staan hieronder "
          "als **⚠ lekkage / bovengrens** — ter vergelijking, niet als resultaat. De set bevat "
          "bovendien alleen items die de ladder al doorliet (selectie-effect).", ""]

    def blok(titel: str, rows: list[dict]):
        feeds = sorted({r["feed"] for r in rows})
        return ([f"## {titel}", "", f"Feeds in deze tabel: {', '.join(feeds)} ({len(rows)} rijen).", ""]
                + _kop_tabel([lex_titel] + runs, rows, lex_titel))

    L += blok(f"Alle runs (afstel-set, FILTER_FEEDS)", afstel)
    zonder = [r for r in afstel if r["feed"] != "Legal & Green Claims"]
    L += blok("Zonder Legal & Green Claims", zonder)

    # Per feed
    feeds = sorted({r["feed"] for r in afstel})
    L += ["## Per feed (afstel-set)", "",
          f"Per feed: aantal, aandeel dismiss, en de dismiss-precision bij {WERKPUNT * 100:.0f}% wegvegen "
          "BINNEN die feed (de laagste scores van die feed).", ""]
    eerlijk = [lex_titel] + [r for r in runs if not r.lekkage]
    kop = ["feed", "N", "dismiss"] + [r.naam for r in eerlijk]
    rijen = []
    for f in feeds:
        fr = [r for r in afstel if r["feed"] == f]
        rij = [f, len(fr), _pct(1 - sum(r["label"] for r in fr) / len(fr))]
        for run in eerlijk:
            d = _werkpunt(run, fr)
            rij.append("—" if d is None else f"{_pct(d['prec'])} ({d['k']})")
        rijen.append(rij)
    L += _tabel(kop, rijen) + [""]

    # Met/zonder rationale (alleen de lekkage-runs hebben die tweedeling)
    L += ["## Scorespreiding", "", "Unieke scores per eerlijke run (meer = een drempel kan fijner).", ""]
    L += _tabel(["run", "unieke scores", "p10 / p50 / p90"],
                [[r.naam, len(set(r.op(afstel)[1])), kwantielen(r.op(afstel)[1])]
                 for r in eerlijk if r.op(afstel)[1]]) + [""]

    L += ["## Holdout (één meting, voor de beste configuratie)", ""]
    if holdout is None:
        L += ["Niet gemeten (zet HOLDOUT=1 voor de ene eindmeting).", ""]
    else:
        h = holdout
        L += [f"Beste configuratie op de afstel-set: **{h['naam']}** (drempel van de afstel-set, "
              "ongewijzigd toegepast).", "",
              f"- Holdout-rijen met titel: {h['n']}; weggeveegd: **{h['k']}**; terecht: {h['tn']}; "
              f"precision {_pct(h['prec'])} [{h['lo'] * 100:.0f}–{h['hi'] * 100:.0f}]; keeps verloren: "
              f"{h['k'] - h['tn']}.", ""]
        if h["k"] < 15:
            L += [f"**Geen uitspraak:** {h['k']} weggeveegde holdout-rijen is te weinig.", ""]
    return "\n".join(L)


def misses(runs: list[Run], afstel: list[dict], titels: dict, datum: str) -> str:
    L = [f"# Stage 0 — misses (vervolg), {datum}", "",
         f"Per eerlijke run: de goedgekeurde items onder de drempel bij {WERKPUNT * 100:.0f}% wegvegen "
         "(afstel-set). Dat zijn de fouten die ertoe doen. Interne tekst: niet committen.", ""]
    for run in runs:
        if run.lekkage:
            continue
        rows, ss, _ys = run.op(afstel)
        if not ss:
            continue
        t = drempel_voor(ss, WERKPUNT)
        fout = sorted([(r, s) for r, s in zip(rows, ss) if s < t and r["label"] == 1], key=lambda x: x[1])
        L += [f"## {run.naam} — drempel < {t:.3g} — {len(fout)} goedgekeurde items weggeveegd", ""]
        L += (_tabel(["score", "feed", "kop", "bron"],
                     [[f"{s:.3g}", r["feed"], _cel(titels[r["id"]]["titel"]),
                       _cel(titels[r["id"]].get("source", ""), 40)] for r, s in fout])
              if fout else ["Geen."]) + [""]
    return "\n".join(L)


def holdout_meting(run: Run, afstel: list[dict], holdout: list[dict], cache: Cache) -> dict:
    """Scoor de holdout voor ÉÉN configuratie en pas de drempel van de afstel-set toe."""
    _r, sa, _y = run.op(afstel)
    t = drempel_voor(sa, WERKPUNT)
    if "delen" in run.extra:                                   # combinatie: beide delen scoren
        m, lex = run.extra["delen"]
        ms, _s, _g = scoor(holdout, m.model, m.bouw, m.vraag, cache, f"holdout {m.naam}")
        w = run.extra["w"]
        hs = {i: w * run.extra["fm"](ms[i]) + (1 - w) * run.extra["fl"](lex.scores_h[i])
              for i in ms if ms[i] is not None and lex.scores_h.get(i) is not None}
    elif run.bouw is not None:
        hs, _s, _g = scoor(holdout, run.model, run.bouw, run.vraag, cache, f"holdout {run.naam}")
    else:                                                      # lexicaal
        hs = run.scores_h
    paren = [(hs[r["id"]], r["label"]) for r in holdout if hs.get(r["id"]) is not None]
    k = sum(1 for s, _y in paren if s < t)
    tn = sum(1 for s, y in paren if s < t and y == 0)
    lo, hi = wilson(tn, k) if k else (0.0, 0.0)
    return {"naam": run.naam, "n": len(paren), "k": k, "tn": tn, "prec": tn / k if k else None,
            "lo": lo, "hi": hi}


# ── Main ──────────────────────────────────────────────────────────────────────────────────────
TITELS_FILE = _env("TITELS_FILE", os.path.join(_HIER, "titels.jsonl"))
#: De feeds waarop het filter mag draaien. Leeg = alle feeds die niet uitgesloten zijn.
FILTER_FEEDS = [f.strip() for f in _env("FILTER_FEEDS", "").split(",") if f.strip()]


def main() -> None:
    t_start = time.time()
    datum = datetime.date.today().isoformat()
    alle = load_rows()
    uitgesloten = {f: sum(1 for r in alle if r["feed"] == f) for f in EXCLUDE_FEEDS}
    # EXCLUDE_FEEDS VÓÓR ALLES: een interne feed komt in geen enkele run (ook niet WITH_GEMINI).
    rows = [r for r in alle if r["feed"] not in EXCLUDE_FEEDS]
    if FILTER_FEEDS:
        rows = [r for r in rows if r["feed"] in FILTER_FEEDS]
    titels = {}
    if os.path.exists(TITELS_FILE):
        titels = {e["id"]: e for e in (json.loads(l) for l in open(TITELS_FILE, encoding="utf-8"))}
    in_meting = len(rows)
    afstel_alle, holdout_alle = splits(rows)                   # holdout_ids.txt blijft de bron
    met = lambda rs: [r for r in rs if titels.get(r["id"], {}).get("titel")]
    afstel, holdout = met(afstel_alle), met(holdout_alle)
    print(f"meting: {in_meting} rijen; met titel: afstel {len(afstel)}, holdout {len(holdout)}")

    cache = Cache(CACHE_FILE)
    lex_titel = Run("lexicaal", "", "trefwoorden", "titel",
                    {r["id"]: float(strategie_relevantie(titels[r["id"]]["titel"])[0]) for r in afstel})
    lex_titel.scores_h = {r["id"]: float(strategie_relevantie(titels[r["id"]]["titel"])[0])
                          for r in holdout}
    lex_lek = Run("lexicaal", "", "trefwoorden", "content + rationale",
                  {r["id"]: float(strategie_relevantie(f"{r['content']} {r['rationale']}")[0])
                   for r in afstel}, lekkage=True)
    runs: list[Run] = [lex_lek]
    passend, grens, _te_groot = modellen()
    gevraagd = 0
    for model, grootte in passend:
        # LEKKAGE-REFERENTIE op de modeltekst. "Met rationale" alleen voor de kleine modellen van de
        # eerste run (die staan in de cache); voor de grotere vroeg stap 1 alleen "zonder".
        for met_r in ((True, False) if grootte < 3 * 1024 ** 3 else (False,)):
            bouw = (lambda r, m=met_r: prompt_for(r, m))
            vraag = (lambda p, mo=model: parse_score(ask_ollama(p, mo)))
            sc, sec, n = scoor(afstel, model, bouw, vraag, cache,
                               f"{model} content{' + rationale' if met_r else ''}")
            gevraagd += n
            runs.append(Run(model, model, "0-100", "content" + (" + rationale" if met_r else ""),
                            sc, sec, n, lekkage=True))
        # EERLIJK: kop + domein + feed, 0-100 (basis) en ja/nee met logprobs.
        for prompt, bouw, vraag in (
                ("0-100", lambda r: prompt_titel(r, titels[r["id"]]),
                 lambda p, mo=model: parse_score(ask_ollama(p, mo))),
                ("ja/nee (logprob)", lambda r: prompt_janee(r, titels[r["id"]]),
                 lambda p, mo=model: ask_janee(p, mo))):
            sc, sec, n = scoor(afstel, model, bouw, vraag, cache, f"{model} titel {prompt}")
            gevraagd += n
            runs.append(Run(model, model, prompt, "titel", sc, sec, n, bouw=bouw, vraag=vraag))
    if _env("WITH_GEMINI"):
        # Kost quota; standaard UIT. Zelfde eerlijke invoer, en EXCLUDE_FEEDS is hierboven al
        # toegepast: er gaat niets van een interne feed naar een externe API.
        traag = float(_env("GEMINI_SLEEP", "1.0"))
        bouw = lambda r: prompt_titel(r, titels[r["id"]])
        vraag = lambda p: (time.sleep(traag), gemini_score(p))[1]
        sc, sec, n = scoor(afstel, "gemini", bouw, vraag, cache, "gemini titel 0-100")
        gevraagd += n
        runs.append(Run("Gemini (ladder-plafond)", "gemini", "0-100", "titel", sc, sec, n,
                        bouw=bouw, vraag=vraag))
    eerlijk = [r for r in runs if not r.lekkage]
    combis = [combineer(r, lex_titel, afstel) for r in eerlijk]
    runs += combis

    # DE HOLDOUT ÉÉN KEER: de eerlijke configuratie met de hoogste precision bij het werkpunt.
    kandidaten = [(d["prec"], r) for r in [lex_titel] + eerlijk + combis
                  if (d := _werkpunt(r, afstel)) is not None]
    beste = max(kandidaten, key=lambda x: x[0])[1] if kandidaten else None
    # ALLEEN MET HOLDOUT=1: een proefrun mag de holdout niet "even" bekijken — dan is hij geen
    # holdout meer. De eindrun zet hem aan, één keer.
    hold = (holdout_meting(beste, afstel, holdout, cache)
            if beste is not None and _env("HOLDOUT") == "1" else None)

    meta = {"datum": datum, "n_totaal": len(alle), "uitgesloten": uitgesloten,
            "in_meting": in_meting, "met_titel": len(afstel) + len(holdout),
            "zonder_titel": in_meting - len(afstel) - len(holdout),
            "filter_feeds": FILTER_FEEDS or sorted({r["feed"] for r in rows}),
            "modellen": passend, "grens": grens, "duur": time.time() - t_start, "gevraagd": gevraagd}
    pad_r = os.path.join(_HIER, f"rapport_{datum}_vervolg.md")
    pad_m = os.path.join(_HIER, f"misses_{datum}_vervolg.md")
    with open(pad_r, "w", encoding="utf-8") as f:
        f.write(rapport(runs, lex_titel, afstel, meta, hold))
    with open(pad_m, "w", encoding="utf-8") as f:
        f.write(misses([lex_titel] + runs, afstel, titels, datum))
    print(f"\nklaar in {meta['duur'] / 60:.1f} min → {pad_r}\n{' ' * 18}{pad_m}")


if __name__ == "__main__":
    main()
