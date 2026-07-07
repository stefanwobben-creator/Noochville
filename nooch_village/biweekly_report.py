"""Bi-weekly bevindingen-rapport — een deterministische 2-weken-roll-up van de observatie-store.

'Data + inzichten', maar alleen wat de data DRAAGT: per bron de nieuwe observaties, de delta t.o.v. de
vorige periode en de richting. Geen verzonnen/geïnterpoleerde duiding; te weinig punten → expliciet
'nulmeting/te weinig voor een trend'; fail-closende bronnen (geen data) worden benoemd, niet weggelaten.

Bewust géén LLM: de cijfers spreken. (Een narratieve LLM-laag zoals de Field Note kan later bovenop.)
"""
from __future__ import annotations
import collections
import datetime

# Leesbare bron-namen (bron-id → label). Onbekende bronnen vallen terug op de id.
_BRON_LABEL = {
    "plausible": "Web-analytics (Plausible)",
    "alphavantage": "Markt — index-ETF's (Alpha Vantage)",
    "trends_categorie": "Zoekinteresse (Google Trends)",
    "gdelt_tone": "Nieuwstoon (GDELT)",
    "gsc": "Zoekprestaties (Search Console)",
    "openalex": "Academische tellers (OpenAlex)",
    "semanticscholar": "Academische tellers (Semantic Scholar)",
    "keywordseverywhere": "Zoekvolume (Keywords Everywhere)",
    "trends": "Zoekinteresse anker-ratio (Trends)",
    "werkoverleg": "Werkoverleg",
}
# Bronnen die we in het rapport verwachten (zodat 'geen data' opvalt).
_VERWACHT = ["plausible", "alphavantage", "trends_categorie", "gsc", "openalex", "gdelt_tone"]


def _num(v):
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", ".") if v != int(v) else f"{int(v):,}".replace(",", ".")
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return str(v)


def _rows_in(rows, start, end):
    return sorted((r for r in rows if start <= (r.get("datum") or "") <= end), key=lambda r: r["datum"])


def build_biweekly_report(st, today: datetime.date, window_days: int = 14) -> str:
    """Markdown-rapport over [today-window, today]. `st` = _Stores (observations)."""
    end = today.isoformat()
    start_d = today - datetime.timedelta(days=window_days)
    start = start_d.isoformat()
    prev_start = (today - datetime.timedelta(days=2 * window_days)).isoformat()

    allrows = st.observations._read_all()
    by_bron = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in allrows:
        b, m = r.get("bron"), r.get("metric")
        if b and m:
            by_bron[b][m].append(r)

    L = [f"# Bi-weekly bevindingen — NoochVille",
         f"",
         f"**Periode:** {start} → {end} ({window_days} dagen). Deterministische roll-up uit de observatie-store; "
         f"alleen wat de data draagt (geen verzonnen duiding). Vergelijking met de vorige {window_days} dagen.",
         f""]

    bronnen = sorted(set(list(by_bron) + _VERWACHT), key=lambda b: (b not in _VERWACHT, b))
    for bron in bronnen:
        label = _BRON_LABEL.get(bron, bron)
        metrics = by_bron.get(bron, {})
        # observaties in het venster over alle metrics van deze bron
        wcount = sum(len(_rows_in(rs, start, end)) for rs in metrics.values())
        L.append(f"## {label}")
        if not metrics or wcount == 0:
            L.append(f"- _Geen observaties in deze periode_ (bron inactief, of fail-closed op een limiet/gate).")
            L.append("")
            continue
        L.append(f"- {wcount} observaties in de periode, over {len(metrics)} metric(s).")
        L.append("")
        L.append("| metric | laatste (datum) | vorige periode | Δ / richting |")
        L.append("|---|---|---|---|")
        for metric in sorted(metrics):
            win = _rows_in(metrics[metric], start, end)
            prev = _rows_in(metrics[metric], prev_start, start)
            if not win:
                continue
            last = win[-1]
            cur_v, cur_d = last.get("value"), last.get("datum")
            base = prev[-1].get("value") if prev else (win[0].get("value") if len(win) > 1 else None)
            if isinstance(cur_v, (int, float)) and isinstance(base, (int, float)):
                d = cur_v - base
                arrow = "▲" if d > 0 else ("▼" if d < 0 else "→")
                delta = f"{arrow} {_num(abs(round(d, 4)) if isinstance(d, float) else abs(d))}"
                pv = f"{_num(base)}"
            else:
                delta = "— (te weinig voor een trend)"
                pv = "—"
            L.append(f"| `{metric}` | {_num(cur_v)} ({cur_d}) | {pv} | {delta} |")
        L.append("")

    L.append("---")
    L.append(f"_Gegenereerd {end} · bron: data/observations.jsonl · append-only, geen normalisatie. "
             f"Δ = laatste waarde in de periode t.o.v. de laatste waarde in de vorige periode (of de eerste in de "
             f"periode). Een lege Δ betekent te weinig meetpunten voor een trend, geen nul._")
    return "\n".join(L)


def write_biweekly_report(st, data_dir: str, today: datetime.date, window_days: int = 14) -> str:
    """Schrijf het rapport naar data/output/bevindingen_<datum>.md en geef het pad terug."""
    import os
    md = build_biweekly_report(st, today, window_days)
    out_dir = os.path.join(data_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"bevindingen_{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path
