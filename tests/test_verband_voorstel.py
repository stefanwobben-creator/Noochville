from __future__ import annotations
import logging
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.verband_voorstel import VerbandVoorstelSkill
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


_KAART_A = {"word": "vegan running shoes", "claim": "Vegan schoenen zijn plasticvrij."}
_KAART_B = {"word": "vegan trail shoes",   "claim": "Trail schoenen mijden synthetisch materiaal."}
_KAART_C = {"word": "leather boots",       "claim": "Leren laarzen zijn duurzaam."}


def _run(kaart_a, kaart_b, reason_return):
    skill = VerbandVoorstelSkill()
    with patch("nooch_village.llm.reason", return_value=reason_return):
        return skill.run({"kaart_a": kaart_a, "kaart_b": kaart_b}, context=None)


# Scope 57 (skill-review 12-09-2026): drie oorzaken, drie antwoorden. Deze tests legden vast dat
# geen model, rommel én een echt nee hetzelfde `{"verband": False}` gaven — waardoor LLM-uitval op
# de wall als "geen verband" las. Het contract is nu Engels (CONNECTION: yes|no); de Nederlandse
# vorm blijft als overgangs-tolerantie herkend.

def test_verband_ja_geeft_claim():
    """LLM bevestigt verband → verband True, claim gevuld."""
    uitslag = _run(_KAART_A, _KAART_B,
                   "CONNECTION: yes | CLAIM: Both cards are about plastic-free shoe material.")
    assert uitslag["verband"] is True
    assert uitslag["claim"] == "Both cards are about plastic-free shoe material."


def test_verband_nederlands_antwoord_blijft_herkend():
    uitslag = _run(_KAART_A, _KAART_B,
                   "VERBAND: ja | CLAIM: Beide kaarten gaan over plasticvrij schoenmateriaal.")
    assert uitslag["verband"] is True


def test_verband_nee_is_no_data_met_reden():
    """LLM zegt nee → een echt antwoord: verband False, `no_data` (📭 op de wall), geen claim."""
    uitslag = _run(_KAART_A, _KAART_C, "CONNECTION: no")
    assert uitslag["verband"] is False and uitslag["no_data"] is True and uitslag["reason"]
    assert "claim" not in uitslag and "error" not in uitslag
    assert _run(_KAART_A, _KAART_C, "VERBAND: nee | CLAIM: geen")["verband"] is False




def test_verband_onparseerbaar_is_een_fout():
    """Rommel-output van LLM → `error` (niet 'geen verband'), geen claim."""
    uitslag = _run(_KAART_A, _KAART_B, "Dit is totaal onleesbare output zonder formaat.")
    assert "error" in uitslag and not uitslag.get("verband")
    assert "claim" not in uitslag


# ── Librarian _on_dag_eindigt integratietest ────────────────────────────────



def _dag_eindigt_event():
    from nooch_village.event_bus import Event
    return Event("dag_eindigt", {"label": "2026-06-22"}, "facilitator")






