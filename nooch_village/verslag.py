"""Noochie's tweewekelijkse verslag — een woordelijk verslag in Noochie's warme ENFP-stem dat de
databron-bevindingen én de agent-output over 2 weken samenweeft tot lopende tekst.

LLM-synthese, maar GEGROND: Noochie duidt en vertelt, maar elk getal komt uit de deterministisch
verzamelde feiten (de observatie-roll-up + de gedateerde Field Notes + de system_log-activiteit). De
prompt verbiedt verzonnen cijfers/gebeurtenissen; wat een bron niet gaf, wordt eerlijk benoemd. Geen
LLM (geen key/rate-limit) → geen verslag (fail-closed), nooit een verzonnen tekst.

De feitelijke ruggengraat is `biweekly_report.build_biweekly_report`; dit is de narratieve laag erbovenop.
"""
from __future__ import annotations
import collections
import datetime
import glob
import json
import os

from nooch_village.biweekly_report import build_biweekly_report

_FN_PREFIX, _FN_SUFFIX = "field_note_", ".md"
_VERSLAG_MAX_TOKENS = 2200      # ruim genoeg voor een verhalend verslag van 5 secties (default reason = 700)


def _read_field_notes(data_dir: str, start: str, end: str) -> list[tuple[str, str]]:
    """Field Notes met datum in [start, end] — gedateerd via de bestandsnaam (betrouwbaar periode-venster)."""
    out = []
    for p in sorted(glob.glob(os.path.join(data_dir, "output", f"{_FN_PREFIX}*{_FN_SUFFIX}"))):
        d = os.path.basename(p)[len(_FN_PREFIX):-len(_FN_SUFFIX)]
        if start <= d <= end:
            try:
                out.append((d, open(p, encoding="utf-8").read().strip()))
            except OSError:
                pass
    return out


def _activity_summary(data_dir: str) -> dict:
    """Samenvatting van system_log: event-type × bewoner-tellingen. LET OP: system_log heeft géén
    per-regel-tijdstempel, dus dit is de RECENTE cumulatieve activiteit, geen strak periode-venster —
    de prompt benoemt dat expliciet zodat Noochie er geen periode-claim aan hangt."""
    path = os.path.join(data_dir, "system_log.jsonl")
    by_event, by_agent, total = collections.Counter(), collections.Counter(), 0
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            total += 1
            by_event[e.get("event", "?")] += 1
            if e.get("by"):
                by_agent[e["by"]] += 1
    return {"total": total, "by_event": by_event.most_common(12), "by_agent": by_agent.most_common(10)}


def gather_facts(st, data_dir: str, today: datetime.date, window_days: int = 14) -> dict:
    end = today.isoformat()
    start = (today - datetime.timedelta(days=window_days)).isoformat()
    return {"start": start, "end": end, "window_days": window_days,
            "data_rollup": build_biweekly_report(st, today, window_days),
            "field_notes": _read_field_notes(data_dir, start, end),
            "activity": _activity_summary(data_dir)}


def _build_prompt(facts: dict) -> str:
    fn = "\n\n".join(f"[Field Note {d}]\n{t}" for d, t in facts["field_notes"]) \
        or "(geen Field Notes in deze periode)"
    act = facts["activity"]
    if act["total"]:
        act_txt = (f"Totaal {act['total']} gelogde gebeurtenissen (cumulatief; system_log heeft geen tijdstempel "
                   f"per regel, dus dit is niet strikt deze periode). Meest voorkomend: "
                   + ", ".join(f"{n}×{ev}" for ev, n in act["by_event"]) + ". Actiefste bewoners: "
                   + ", ".join(f"{a} ({n})" for a, n in act["by_agent"]) + ".")
    else:
        act_txt = "(geen gelogde agent-activiteit beschikbaar)"
    return f"""You are Noochie, the warm, energetic ENFP voice of the village NoochVille (around the \
sustainable shoe brand Nooch.earth). Write a NARRATIVE two-weekly report for the founder about the period \
{facts['start']} → {facts['end']}, in English, in running text — warm and human, but concrete.

STRICT RULE: use ONLY the facts below. Invent NO figures, trends or events. \
Where a source gave nothing, say so honestly (e.g. the news-tone source gave no data) — fill in nothing. \
New sources with a single data point are not a trend yet; say it that way.

Write in flowing paragraphs (NO tables), along this thread:
1. A warm opening: where does the village stand these two weeks.
2. What the data told us — visitors/traffic, search interest, market, news tone — with the real figures.
3. What the inhabitants did (from the Field Notes and the activity).
4. What stands out: worries and opportunities.
5. The next step.

=== FACT 1 — DATA ROLL-UP (the figures; copy these exactly) ===
{facts['data_rollup']}

=== FACT 2 — DAILY FIELD NOTES IN THIS PERIOD ===
{fn}

=== FACT 3 — AGENT ACTIVITY ===
{act_txt}

Now write Noochie's report."""


def build_noochie_verslag(st, data_dir: str, today: datetime.date, window_days: int = 14, *, reason=None):
    """Geeft (markdown, facts). markdown is None als de LLM niets teruggaf (fail-closed: nooit verzinnen)."""
    facts = gather_facts(st, data_dir, today, window_days)
    if reason is None:
        import functools
        from nooch_village import llm
        # Een verhalend verslag van 5 secties past niet in de default 700 tokens → ruimer vragen.
        reason = functools.partial(llm.reason, max_tokens=_VERSLAG_MAX_TOKENS,
                                    call_site="field_note_narrative")
    narrative = (reason(_build_prompt(facts)) or "").strip()
    if not narrative:
        return None, facts
    header = f"# Noochie's tweewekelijkse verslag — {facts['start']} → {facts['end']}\n\n"
    footer = (f"\n\n---\n*Noochie schreef dit op {facts['end']}, gegrond op de observatie-roll-up, "
              f"{len(facts['field_notes'])} Field Note(s) en {facts['activity']['total']} gelogde gebeurtenissen. "
              f"Geen cijfer is verzonnen; wat een bron niet gaf, staat als 'geen data'.*")
    return header + narrative + footer, facts


def write_noochie_verslag(st, data_dir: str, today: datetime.date, window_days: int = 14, *, reason=None):
    """Schrijf naar data/output/verslag_<datum>.md; None als er geen verslag is (geen LLM)."""
    md, _ = build_noochie_verslag(st, data_dir, today, window_days, reason=reason)
    if md is None:
        return None
    out_dir = os.path.join(data_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"verslag_{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path
