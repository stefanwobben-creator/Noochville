"""Scope 60 — Librarian._reflect(): periodieke bewaking van de semantische laag. Thread-vrij.

AANLEIDING (`data_opsporing_kwaliteit.md`, bevinding 1). `semantiek_status()` bestaat al sinds de
storing van 29 augustus, maar draaide tot 13 september alleen via het handmatige commando
`village keys`. `_meld_terugval` waarschuwt wél tijdens gebruik zodra `_rangschik` 'stil'
tegenkomt, maar hooguit ÉÉN keer per index per proces — precies waarom die storing maandenlang
onopgemerkt bleef: de melding bij opstart verdwijnt in de logs, en daarna is het stil totdat een
mens het zelf opvraagt.

Dit bestand toetst de nieuwe, periodieke aanvulling: de Librarian (domein-eigenaar van de
kennislaag) vraagt de status zelf op via zijn bestaande wekelijkse `_reflect`-cadans, en blijft dat
HERHALEN zolang de storing duurt — geen eenmalige melding die na de eerste keer verstomt. Vijf
scenario's:

1. oordeel='stil' → precies één `sense_tension`, operationeel, zonder 'accountability:' (dus geen
   governance-route — dit is een signaal, geen voorstel voor een rol of bevoegdheid).
2. Gezonde of opwarmende toestanden ('actief', 'uit', 'deels') → stil, geen `sense_tension`.
3. DE KERNTEST: twee reflecties op rij terwijl 'stil' aanhoudt → TWEE keer `sense_tension` (geen
   eenmalige melding die daarna verstomt, zoals `_meld_terugval` dat wél doet).
4. Een hersteld 'actief' ná een storing → de herinnering stopt vanzelf.
5. `semantiek_status()` faalt (exception) → fail-soft: geen crash, geen `sense_tension`.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.event_bus import EventBus
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.notes_store import NotesStore
from nooch_village.roles import Librarian
from nooch_village.skills import SkillRegistry


def _librarian(tmp_path):
    """Zelfde constructiepatroon als `test_librarian_curate.py` — geen thread, geen skills nodig
    voor `_reflect` zelf."""
    bus = EventBus(name="t")
    registry = SkillRegistry()
    notes = NotesStore(str(tmp_path / "notes.json"))
    rec = Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                definition=RoleDefinition(purpose="t"), source="seed")
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path), records=None,
                          library=SimpleNamespace(status=lambda w: None),
                          lexicon=SimpleNamespace(concept_for_word=lambda w: None),
                          notes=notes)
    return Librarian(rec, bus, registry, ctx)


def _status(oordeel: str, *, model: str = "gemini-embedding-001") -> dict:
    """Een statusdict in dezelfde vorm als de echte `semantiek_status()` (kennis_context.py)."""
    dekking = {"stil": 0, "deels": 3, "actief": 8}.get(oordeel, 0)
    levend = 0 if oordeel == "uit" else 8
    return {"sleutel": oordeel != "uit", "model": model, "oordeel": oordeel,
            "indexen": [{"index": "kennisbank_embeddings.json", "levend": levend,
                        "geindexeerd": dekking, "dekking": 0.0, "oordeel": oordeel}]}


# ── 1. 'stil' → precies één operationele spanning, geen governance-route ──────────────────────

def test_stil_senst_precies_een_operationele_spanning(tmp_path):
    lib = _librarian(tmp_path)
    with patch("nooch_village.kennis_context.semantiek_status", return_value=_status("stil")):
        with patch.object(lib, "sense_tension") as st:
            lib._reflect()
    st.assert_called_once()
    (beschrijving,), kwargs = st.call_args
    assert kwargs.get("kind") == "operational"
    assert "stil" in beschrijving.lower()
    assert "gemini-embedding-001" in beschrijving
    assert "accountability:" not in beschrijving.lower(), (
        "geen governance-route: dit is een operationeel signaal, geen voorstel voor een nieuwe "
        "rol of bevoegdheid (HARDE REGEL 10)")


# ── 2. gezonde of opwarmende toestanden → stil ─────────────────────────────────────────────────

@pytest.mark.parametrize("oordeel", ["actief", "uit", "deels"])
def test_gezonde_of_opwarmende_toestand_senst_niets(tmp_path, oordeel):
    lib = _librarian(tmp_path)
    with patch("nooch_village.kennis_context.semantiek_status", return_value=_status(oordeel)):
        with patch.object(lib, "sense_tension") as st:
            lib._reflect()
    st.assert_not_called()


# ── 3. DE KERNTEST: blijft herhalen zolang de storing duurt ────────────────────────────────────

def test_stil_blijft_herhalen_zolang_de_storing_duurt(tmp_path):
    """`_meld_terugval` meldt hooguit één keer per proces — precies waarom de storing van 29
    augustus maandenlang onopgemerkt bleef. Deze wekelijkse aanvulling moet WÉL herhalen zolang
    'stil' aanhoudt: zonder een 'accountability:'-frase in de tekst reset `_sense_gap`'s
    dedup-check (`_extract_acc_text` geeft "") bij elke aanroep opnieuw, dus elke reflectie meldt
    opnieuw zolang de toestand niet verandert."""
    lib = _librarian(tmp_path)
    with patch("nooch_village.kennis_context.semantiek_status", return_value=_status("stil")):
        with patch.object(lib, "sense_tension") as st:
            lib._reflect()
            lib._reflect()
    assert st.call_count == 2, "een aanhoudende storing moet bij elke reflectie opnieuw melden"


# ── 4. Herstel stopt de herinnering vanzelf ────────────────────────────────────────────────────

def test_hersteld_actief_stopt_de_herinnering(tmp_path):
    lib = _librarian(tmp_path)
    with patch.object(lib, "sense_tension") as st:
        with patch("nooch_village.kennis_context.semantiek_status", return_value=_status("stil")):
            lib._reflect()
        with patch("nooch_village.kennis_context.semantiek_status",
                   return_value=_status("actief")):
            lib._reflect()
    assert st.call_count == 1, "een hersteld 'actief' hoort niets meer te melden"


# ── 5. Fail-soft: reflectie mag nooit breken ───────────────────────────────────────────────────

def test_status_opvragen_faalt_fail_soft(tmp_path):
    lib = _librarian(tmp_path)
    with patch("nooch_village.kennis_context.semantiek_status",
               side_effect=RuntimeError("kapot")):
        with patch.object(lib, "sense_tension") as st:
            lib._reflect()                              # mag niet crashen
    st.assert_not_called()
