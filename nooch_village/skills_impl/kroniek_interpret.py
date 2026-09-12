"""kroniek_interpret — De Kroniek interpreteren (fase 2).

Leest het bewijsregister (EvidenceLedger) en rolt het voor één onderwerp op tot een geïnterpreteerde
bevinding: wat is bevestigd (met bron), wat is leeg (kennisgaten), wat faalde (bronfouten), plus een
gegronde conclusie. Fail-closed (harry_hemp's waarheidslat): de conclusie leunt alleen op bevestigd
bewijs; geen bevestigd record → geen conclusie. Zuiver leesbaar, geen LLM, deterministisch.

Eigenaarschap: de Librarian is hoeder/curator van de Kroniek — deze skill hoort in haar rugzak.
De skill schrijft niets; interpreteren is lezen.

SCOPE 57 (skill-review 12-09-2026): nul records las als 'gelukt' — de conclusiezin "GEEN bevestigd
bewijs … 0 kennisgat(en), 0 bronfout(en)" was tekst en dus inhoud, en het item werd afgevinkt met
'niets' als antwoord (live: 20 items, 19 afgevinkt, 0 leeg). Nu is nul treffers `no_data` (📭 met
leeg-markering), en de leeswijzer `text` zegt in het Engels wat het register wél weet. De
onderwerpen die de planner schreef waren lange frasen ("Green Claims Directive prohibited terms");
de match is een substring op de query, dus het schema vraagt nu om één term van 1-2 woorden.
"""
from __future__ import annotations

import os

from nooch_village.skills import Skill


class KroniekInterpretSkill(Skill):
    name = "kroniek_interpret"
    cost = "free"                  # lokale I/O + deterministische rollup, geen externe call
    side_effect_free = True        # leest de ledger, schrijft niets
    description = ("Read the Chronicle (the village's evidence register) for one topic: what earlier "
                   "runs CONFIRMED (with source), where they found NOTHING (knowledge gaps) and where "
                   "a source FAILED, with a grounded conclusion. Deterministic, no model.")
    input_schema = ("onderwerp: str (required — ONE short term of 1-2 words as it appeared in earlier "
                    "queries, e.g. 'barefoot' or 'PHA'; the match is a substring of the recorded "
                    "query, so a long phrase never matches)")
    required_payload = ("onderwerp",)
    output_schema = ("ok: bool, text (summary), bevestigd/leeg/fout: list[{skill, query, source, "
                     "bewijs, ts}], conclusie: str | no_data+reason (no record mentions the topic) | error")

    def _ledger(self, context):
        led = getattr(context, "evidence_ledger", None)
        if led is not None:
            return led
        from nooch_village.evidence_ledger import EvidenceLedger
        return EvidenceLedger(os.path.join(getattr(context, "data_dir", "."), "evidence_ledger.jsonl"))

    def run(self, payload: dict, context=None) -> dict:
        topic = ((payload or {}).get("onderwerp") or "").strip()
        if not topic:
            return {"ok": False, "error": "geef een onderwerp om te interpreteren"}
        from nooch_village.evidence_ledger import interpret
        res = interpret(self._ledger(context), topic)
        bevestigd, leeg, fout = res.get("bevestigd") or [], res.get("leeg") or [], res.get("fout") or []
        if not (bevestigd or leeg or fout):
            # Nul records = het register kent dit onderwerp niet. Dat is een antwoord ("nooit
            # onderzocht"), geen conclusie — en zeker geen afgevinkt 'gelukt'.
            return {"ok": True, "no_data": True, "_onderwerp": topic,
                    "reason": (f"no record in the Chronicle mentions '{topic}' — the village never "
                               f"investigated this term (try a shorter term as it appeared in a query)"),
                    "conclusie": res.get("conclusie", "")}
        bronnen = sorted({e.get("source") for e in bevestigd if e.get("source")})
        if bevestigd:
            text = (f"{len(bevestigd)} confirmed record(s) for '{topic}'"
                    + (f" (sources: {', '.join(bronnen)[:200]})" if bronnen else "")
                    + (f"; {len(leeg)} knowledge gap(s) and {len(fout)} source failure(s) besides"
                       if (leeg or fout) else ""))
        else:
            text = (f"NO confirmed evidence for '{topic}' in the Chronicle: {len(leeg)} run(s) found "
                    f"nothing and {len(fout)} source(s) failed — no conclusion possible")
        # `text` als leeswijzer (Engels, met de kerncijfers); `conclusie` blijft de Nederlandse
        # zin van `interpret` (die lezen kennis_context en project_proposals ook).
        return {"ok": True, "text": text, **res}
