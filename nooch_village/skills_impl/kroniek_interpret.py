"""kroniek_interpret — De Kroniek interpreteren (fase 2).

Leest het bewijsregister (EvidenceLedger) en rolt het voor één onderwerp op tot een geïnterpreteerde
bevinding: wat is bevestigd (met bron), wat is leeg (kennisgaten), wat faalde (bronfouten), plus een
gegronde conclusie. Fail-closed (harry_hemp's waarheidslat): de conclusie leunt alleen op bevestigd
bewijs; geen bevestigd record → geen conclusie. Zuiver leesbaar, geen LLM, deterministisch.

Eigenaarschap: de Librarian is hoeder/curator van de Kroniek — deze skill hoort in haar rugzak.
De skill schrijft niets; interpreteren is lezen.
"""
from __future__ import annotations

import os

from nooch_village.skills import Skill


class KroniekInterpretSkill(Skill):
    name = "kroniek_interpret"
    cost = "free"                  # lokale I/O + deterministische rollup, geen externe call
    side_effect_free = True        # leest de ledger, schrijft niets
    description = ("Interpreteert De Kroniek voor een onderwerp: rolt de bewijsregels op tot bevestigd, "
                  "leeg en fout, met een gegronde conclusie. Fail-closed, geen LLM, deterministisch.")
    input_schema = "onderwerp: str (verplicht — de term/het onderwerp om in het register te interpreteren)"
    required_payload = ("onderwerp",)
    output_schema = ("ok: bool, onderwerp: str, bevestigd/leeg/fout: list[{skill, query, source, bewijs, ts}], "
                     "conclusie: str | error")

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
        return {"ok": True, **res}
