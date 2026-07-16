"""atomic_insights — Zettelkasten-synthese (Ahrens): ruwe onderzoeksdata → atomaire inzichten.

De ontbrekende stap tussen ruwe projectdata en de curate-poort. Curate maakt van fuzzy input
goedgevormde kaartjes, maar cureert wat er STAAT (datapunten). Deze skill destilleert eerst de
patronen ÁCHTER de datapunten (Ahrens: literature note → permanent note): geen samenvatting,
geen "merk X zegt Y", maar de algemene, bronvrij leesbare inzichten, elk met een fact/hypothesis-
status naar de kwaliteit van het bewijs eronder. De output is bewust ruwe input voor curate:
de Librarian blijft domein-eigenaar en curate blijft de enige schrijfweg naar de NotesStore.

Pure helpers + injecteerbare reason_fn (testbaar zonder netwerk); fail-closed zonder LLM.
"""
from __future__ import annotations
import json
import re

from nooch_village.skills import Skill

_VALID_STATUS = {"fact", "hypothesis"}


def build_insights_prompt(data: str, mission: str = "") -> str:
    """Bouw de synthese-prompt. Harde regels: Engels, patronen (geen datapunten), één idee
    per inzicht, status naar bewijskwaliteit, JSON-output."""
    mission_line = f"Mission context: {mission}\n\n" if mission else ""
    return (
        "You are the Librarian of Nooch.earth. Apply Sönke Ahrens' Zettelkasten method "
        "(How to Take Smart Notes): the input below is RAW RESEARCH DATA (a literature note). "
        "Distill the PATTERNS behind the data points — permanent notes, not summaries.\n\n"
        f"{mission_line}"
        "HARD RULES:\n"
        "- ENGLISH ONLY. Translate any non-English input.\n"
        "- An insight is a GENERAL statement that survives without the source project. "
        "'Brand X says Y' is data, not an insight; 'claims without a test standard are "
        "unverifiable' is an insight of which brand X is merely an instance.\n"
        "- ONE idea per insight. If it needs 'and', split it into two.\n"
        "- Hunt for: what the outliers share; what ABSENCE signals (no claim, no evidence, "
        "no response); contradictions between data points and what explains them; whether "
        "the conclusion would hold in another industry (if yes, it is general enough).\n"
        "- status: 'fact' only when the evidence beneath it is solid; 'hypothesis' when it "
        "rests on a single study or weak/ambiguous data. When in doubt: 'hypothesis' — "
        "false certainty pollutes a knowledge base worse than a gap.\n"
        "- grounds: the evidence or reasoning in your own words, no pasted quotes.\n\n"
        f"Raw research data (may be fuzzy or non-English):\n\"\"\"{data}\"\"\"\n\n"
        "Return ONLY a JSON array, no prose, no code fences. Each object:\n"
        '{"insight": "<one general claim in English>", "status": "fact|hypothesis", '
        '"grounds": "<evidence or reasoning in English>"}'
    )


def parse_insights(text: str | None) -> list[dict]:
    """Haal de JSON-array met inzichten uit de LLM-output. Fail-closed: geen/onparseerbaar → []."""
    if not text:
        return []
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(cleaned[start:end + 1])
    except (ValueError, TypeError):
        return []
    return [d for d in data if isinstance(d, dict)]


def validate_insight(d: dict) -> bool:
    """Deterministische poort: insight en grounds gevuld, status uit de vaste set."""
    def filled(k):
        return isinstance(d.get(k), str) and d[k].strip() != ""
    return filled("insight") and filled("grounds") and d.get("status") in _VALID_STATUS


def to_fuzzy(insights: list[dict]) -> str:
    """Zet de inzichten om naar ruwe curate-input, één inzicht per regel. De status reist mee
    in de tekst zodat curate hem in de grounds kan verwerken."""
    lines = []
    for d in insights:
        lines.append(f"INSIGHT ({d['status']}): {d['insight'].strip()} "
                     f"GROUNDS: {d['grounds'].strip()}")
    return "\n".join(lines)


def synthesize_insights(data: str, *, mission: str = "", reason_fn=None) -> list[dict]:
    """Ruwe data → lijst gevalideerde inzicht-dicts ({insight, status, grounds}).

    Roept de LLM aan (reason_fn, default llm.reason), parseert en valideert.
    Fail-closed op elke stap: geen LLM/onparseerbaar/ongeldig → die inzichten vervallen.
    """
    if reason_fn is None:
        import functools
        from nooch_village.llm import reason
        reason_fn = functools.partial(reason, call_site="skill_atomic_insights")
    out = reason_fn(build_insights_prompt(data, mission))
    return [{"insight": d["insight"].strip(), "status": d["status"],
             "grounds": d["grounds"].strip()}
            for d in parse_insights(out) if validate_insight(d)]


class AtomicInsightsSkill(Skill):
    name = "atomic_insights"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd (zelfde keuze als curate)
    side_effect_free = True
    description = (
        "Zettelkasten-synthese (Ahrens): destilleert uit ruwe onderzoeksdata de patronen achter "
        "de datapunten tot atomaire, algemene inzichten met fact/hypothesis-status. Geen "
        "samenvatting: 'merk X zegt Y' is data, het patroon erachter is het inzicht. De output "
        "(fuzzy) is klaar als input voor de curate-poort."
    )
    input_schema = "data: str (verplicht — ruwe onderzoeksdata, rapport of literature note), source: str (optioneel herkomstlabel)"
    required_payload = ("data",)
    output_schema = ("insights: list[{insight, status(fact|hypothesis), grounds}], "
                     "fuzzy: str (klaar voor curate) | error")

    def run(self, payload: dict, context) -> dict:
        data = (payload.get("data") or payload.get("text") or "").strip()
        if not data:
            return {"error": "geen data om te synthetiseren"}
        mission = getattr(getattr(context, "mission", None), "purpose", "") or ""
        insights = synthesize_insights(data, mission=mission)
        if not insights:
            return {"error": "geen LLM beschikbaar of geen valide inzichten (fail-closed)"}
        return {"insights": insights, "fuzzy": to_fuzzy(insights)}
