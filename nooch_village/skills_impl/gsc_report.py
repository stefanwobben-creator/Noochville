"""GscReportSkill — schrijft de markdown GSC-nota (`data/output/gsc_nota_<datum>.md`) uit een
gsc_performance-resultaat dat als payload wordt meegegeven.

Dit is een puls-hulpje van TrendsWorker (`roles.py: _maybe_write_nota`), geen planner-skill: de
planner kan hem nooit van een `rows`-payload voorzien, en daarom staat hij sinds scope 53 niet meer
in de rugzak 'schrijven'. Tot scope 58 accepteerde `run` élke payload en schreef hij dan een lege nota
("Periode: onbekend | 0 zoekopdrachten") met een pad als antwoord — zes van die bestanden stonden in
data/output, geschreven door de declaratie-sweep in de tests (skill-review 12-09-2026). Nu: geen
`rows` → `error`, lege `rows` → `no_data` en geen bestand.
"""
from __future__ import annotations
import os
from datetime import date
from nooch_village.skills import Skill
from nooch_village.skills_impl.gsc import BUCKET_GRENZEN, BUCKET_LABEL, bucket_bereik


class GscReportSkill(Skill):
    name = "gsc_report"
    cost = "free"
    side_effect_free = False          # schrijft data/output/gsc_nota_<datum>.md
    required_env = ("GSC_TOKEN_PATH", "GSC_SITE")
    required_payload = ("rows",)
    description = ("Writes the weekly search-traffic note (markdown, data/output/gsc_nota_<date>.md) from a "
                   "gsc_performance result: bucket counts and the top queries per bucket. Needs that result "
                   "as payload (rows); it does not fetch anything itself.")
    input_schema = ("the gsc_performance result: rows: list[{query, clicks, impressions, position, bucket}] "
                    "(required), bucket_counts: dict (optional), period: str (optional), total: int (optional)")
    output_schema = "path, today, total | no_data + reason (empty rows) | error (no rows list)"

    def run(self, payload: dict, context) -> dict:
        """payload: het directe resultaat van GscPerformanceSkill.run() (of {"result": …}).

        Geeft terug: {"path": str, "today": str, "total": int}, {"no_data": True, "reason": …} of
        {"error": str}.
        """
        payload = payload if isinstance(payload, dict) else {}
        result = payload if payload.get("rows") is not None else payload.get("result", payload)
        if not isinstance(result, dict):
            return {"error": "gsc_report needs the gsc_performance result as payload (rows)"}
        if "error" in result:
            return {"error": result["error"]}
        rows = result.get("rows")
        if not isinstance(rows, list):
            # Zonder rijen valt er niets te schrijven; een pad teruggeven zou 'niets gedaan' als
            # succes boeken (en het item afvinken).
            return {"error": "gsc_report needs the gsc_performance result as payload (rows)"}
        if not rows:
            return {"no_data": True,
                    "reason": (str(result.get("reason") or "").strip() or
                               "gsc_performance returned 0 rows; no note written")}

        today  = date.today().isoformat()
        period = result.get("period", "onbekend")
        total  = result.get("total") or len(rows)
        counts = result.get("bucket_counts") or {}
        if not counts:
            for r in rows:
                counts[r.get("bucket", "?")] = counts.get(r.get("bucket", "?"), 0) + 1

        def selectie(bucket: str, sleutel: str) -> list[dict]:
            return sorted([r for r in rows if r.get("bucket") == bucket],
                          key=lambda r: r.get(sleutel, 0), reverse=True)[:10]

        page1       = selectie("page1", "clicks")
        high_pot    = selectie("high_potential", "impressions")
        low_ranking = selectie("low_ranking", "impressions")
        content_gap = selectie("content_gap", "impressions")

        def tabel(rijen: list[dict]) -> str:
            if not rijen:
                return "  (geen)\n"
            lines = [f"  {'Zoekopdracht':<45} {'Imp':>6} {'Klikken':>8} {'Positie':>8}",
                     "  " + "-" * 71]
            for r in rijen:
                lines.append(f"  {str(r.get('query', ''))[:45]:<45} {int(r.get('impressions', 0)):>6} "
                              f"{int(r.get('clicks', 0)):>8} {float(r.get('position', 0.0)):>8.1f}")
            return "\n".join(lines) + "\n"

        # De koppen lezen de banden uit gsc.BUCKET_GRENZEN: één definitie, geen tweede waarheid.
        def kop(bucket: str) -> str:
            return f"{BUCKET_LABEL[bucket].capitalize()} ({bucket_bereik(bucket)})"

        body_parts = [
            f"# GSC-nota {today}",
            f"Periode: {period} | {total} zoekopdrachten geanalyseerd\n",
            "## Verdeling buckets",
            f"- {kop('page1')}:    {counts.get('page1', 0):>4}",
            f"- {kop('high_potential')}:  {counts.get('high_potential', 0):>4}",
            f"- {kop('low_ranking')}:     {counts.get('low_ranking', 0):>4}",
            f"- {kop('content_gap')}:       {counts.get('content_gap', 0):>4}\n",
            f"## {kop('page1')} — meeste klikken",
            tabel(page1),
            f"## {kop('high_potential')} — meeste impressies, net buiten de top {BUCKET_GRENZEN['page1'][1]}",
            tabel(high_pot),
            f"## {kop('low_ranking')} — kansen met veel impressies",
            tabel(low_ranking),
        ]
        if content_gap:
            body_parts += [f"## {kop('content_gap')} — veel gezocht, nauwelijks aanwezig",
                           tabel(content_gap)]

        body = "\n".join(body_parts)
        data_dir = getattr(context, "data_dir", None) or "data"
        out_dir  = os.path.join(data_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"gsc_nota_{today}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return {"path": path, "today": today, "total": total,
                "text": f"search-traffic note written for {total} queries ({period}) -> {path}"}
