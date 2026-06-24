"""GscReportSkill — genereert een markdown GSC-nota vanuit GSC-performance-resultaten."""
from __future__ import annotations
import os
from datetime import date
from nooch_village.skills import Skill
from nooch_village.util import atomic_write_json


class GscReportSkill(Skill):
    name = "gsc_report"
    cost = "free"
    required_env = ("GSC_TOKEN_PATH", "GSC_SITE")
    description = "Genereert een markdown GSC-nota vanuit GSC-performance-resultaten"

    def run(self, payload: dict, context) -> dict:
        """payload: het directe resultaat van GscPerformanceSkill.run().

        Geeft terug: {"path": str, "today": str} of {"error": str}.
        """
        result = payload if payload.get("rows") is not None else payload.get("result", payload)
        if "error" in result:
            return {"error": result["error"]}

        today  = date.today().isoformat()
        period = result.get("period", "onbekend")
        total  = result.get("total", 0)
        counts = result.get("bucket_counts", {})
        rows   = result.get("rows", [])

        page1       = sorted([r for r in rows if r["bucket"] == "page1"],
                             key=lambda r: r["clicks"], reverse=True)[:10]
        high_pot    = sorted([r for r in rows if r["bucket"] == "high_potential"],
                             key=lambda r: r["impressions"], reverse=True)[:10]
        low_ranking = sorted([r for r in rows if r["bucket"] == "low_ranking"],
                             key=lambda r: r["impressions"], reverse=True)[:10]
        content_gap = sorted([r for r in rows if r["bucket"] == "content_gap"],
                             key=lambda r: r["impressions"], reverse=True)[:10]

        def tabel(rijen: list[dict]) -> str:
            if not rijen:
                return "  (geen)\n"
            lines = [f"  {'Zoekopdracht':<45} {'Imp':>6} {'Klikken':>8} {'Positie':>8}",
                     "  " + "-" * 71]
            for r in rijen:
                lines.append(f"  {r['query']:<45} {r['impressions']:>6} "
                              f"{r['clicks']:>8} {r['position']:>8.1f}")
            return "\n".join(lines) + "\n"

        body_parts = [
            f"# GSC-nota {today}",
            f"Periode: {period} | {total} zoekopdrachten geanalyseerd\n",
            "## Verdeling buckets",
            f"- Pagina 1 (positie 1–10):    {counts.get('page1', 0):>4}",
            f"- High potential (pos 11–20):  {counts.get('high_potential', 0):>4}",
            f"- Low ranking (pos 21–50):     {counts.get('low_ranking', 0):>4}",
            f"- Content gap (pos 50+):       {counts.get('content_gap', 0):>4}\n",
            "## Pagina 1 — meeste klikken",
            tabel(page1),
            "## High potential — meeste impressies, net buiten top 10",
            tabel(high_pot),
            "## Low ranking — kansen met veel impressies",
            tabel(low_ranking),
        ]
        if content_gap:
            body_parts += ["## Content gap — veel gezocht, nauwelijks aanwezig",
                           tabel(content_gap)]

        body = "\n".join(body_parts)
        data_dir = getattr(context, "data_dir", "data")
        out_dir  = os.path.join(data_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"gsc_nota_{today}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return {"path": path, "today": today}
