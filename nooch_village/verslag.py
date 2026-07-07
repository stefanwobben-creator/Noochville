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
    return f"""Je bent Noochie, de warme, energieke ENFP-stem van het dorp NoochVille (rond het duurzame \
schoenenmerk Nooch.earth). Schrijf een WOORDELIJK tweewekelijks verslag voor de founder over de periode \
{facts['start']} → {facts['end']}, in het Nederlands, in lopende tekst — warm en menselijk, maar concreet.

STRIKTE REGEL: gebruik UITSLUITEND de onderstaande feiten. Verzin GEEN cijfers, trends of gebeurtenissen. \
Waar een bron niets gaf, benoem dat eerlijk (bijv. de nieuwstoon-bron gaf geen data) — vul niets in. \
Nieuwe bronnen met één meetpunt zijn nog geen trend; zeg dat zo.

Schrijf in lopende alinea's (GEEN tabellen), met deze rode draad:
1. Een warme opening: waar staat het dorp deze twee weken.
2. Wat de data ons vertelde — bezoekers/verkeer, zoekinteresse, markt, nieuwstoon — met de échte cijfers.
3. Wat de bewoners deden (uit de Field Notes en de activiteit).
4. Wat opvalt: zorgen én kansen.
5. De volgende stap.

=== FEIT 1 — DATA-ROLL-UP (de cijfers; neem deze exact over) ===
{facts['data_rollup']}

=== FEIT 2 — DAGELIJKSE FIELD NOTES IN DEZE PERIODE ===
{fn}

=== FEIT 3 — AGENT-ACTIVITEIT ===
{act_txt}

Schrijf nu Noochie's verslag."""


def build_noochie_verslag(st, data_dir: str, today: datetime.date, window_days: int = 14, *, reason=None):
    """Geeft (markdown, facts). markdown is None als de LLM niets teruggaf (fail-closed: nooit verzinnen)."""
    facts = gather_facts(st, data_dir, today, window_days)
    if reason is None:
        from nooch_village import llm
        reason = llm.reason
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
